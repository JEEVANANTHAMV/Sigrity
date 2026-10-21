---
name: sigrity-footprint
description: Create Allegro PCB package symbols (footprints) FROM SCRATCH and place them on boards, 100% headless (no GUI). Authors a .dra -> compiles to .psm (ball/array packages, N pins, exact geometry) and places it into a .brd via a generated run_tool_pipeline-free SKILL. Use when a part has NO existing .psm/.olb/.pdra footprint and you must build the footprint from a ball-map/pin-list (BGA, CSP, ODICSP, QFN, custom array), then place it on a new or existing board. Verified live on SPB_22.1.
---

# Sigrity Footprint domain — build packages from scratch, headless

Companion to `sigrity-cad`. `sigrity-cad` covers a board that ALREADY has footprints
(report/DRC/autoroute/Gerber). This one covers the case where the part has **no existing
footprint at all** — you must **author the package symbol** (`.dra` → `.psm`) and then
**place** it. Everything runs headless via `allegro.exe -nograph -s <script> <file>`
(see the `sigrity` parent skill for the non-blocking `*run_session`/`wait_for_job` contract;
here the job is a direct `allegro.exe` subprocess — see "Runner contract" below).

SPB_22.1 at `C:\cadence\SPB_22.1` (set `$env:CDS_INST_DIR` to this before every call).
`board.brd` units = `mil` (1 ball-map/OLB source unit == 1 mil).

## The ONE command that unblocks everything: `axlDBChangeDesignExtents`

A **fresh, empty** symbol drawing (`.dra`) and a **fresh, empty** board (`.brd`) both have
**nil / zero extents**. Until you set a canvas extent, **every** `axlDBCreatePin` /
`axlDBCreateOpenShape` is rejected with `SPMHA1-70: Pin is outside of the extents` (or
`SPMHA1-68: Line segments are outside of the extents`), no matter what you do.

```
axlDBChangeDesignExtents (list -EXT:-EXT EXT:EXT)  -> t/nil
```
- Extent box MUST be **larger than your geometry** (it's checked at creation).
- Use it FIRST in both the `.dra` authoring script AND the `.brd` placement script.
- This is the single most-missed step. If you see "outside of the extents", you forgot it
  (or the box is too small).

## The hard domain boundary (don't fight it)

These two APIs are in **opposite domains** — a package *cannot* be built in one context:

| API | Only works in | Refuses with |
|---|---|---|
| `axlDBCreatePin` | symbol editor (`.dra`) | "can only be applied to symbol drawings" in `.brd` |
| `axlDBCreateSymDefSkeleton` (sets extents + pins) | layout (`.brd`) | "can only be applied to layout drawings" in `.dra` |

**The working split** (this is the verified pipeline):
1. **`.dra` (symbol editor)** — `axlDBChangeDesignExtents` + `axlDBCreatePadStack` +
   body boundary shape + **N × `axlDBCreatePin`** + refdes **text** → `axlCompileSymbol` → `.psm`.
   (`axlDBCreateSymDefSkeleton` is the *layout* equivalent — do NOT call it in a `.dra`.)
2. **`.brd` (layout)** — `axlSetVariable` PSMPATH + `axlDBChangeDesignExtents` +
   **recreate the padstack** + `axlDBCreateSymbol (list "<name>" "PACKAGE")` → `axlSaveDesign`.

You never try to build the pins in the `.brd` and you never try to build the extents-skeleton
in the `.dra`. The `.psm` is the bridge.

## Quick start — the tool (do this first)

This skill ships `gen_footprint.py`. Give it a part spec (JSON), it emits the exact
SKILL scripts + two `.bat` runners. **This is the path of least resistance.**

```
cd <project>/.forjinn/skills/sigrity-footprint
python gen_footprint.py --example part.json          # writes an AR0830-style 59-ball example
python gen_footprint.py part.json --outdir work --spb-root "C:\cadence\SPB_22.1" \
       --psmpath "<abs path to work dir holding the .psm>"
# -> work\author_<name>.il/.scr   (build .psm)
# -> work\place_<name>.il/.scr    (place on board)
# -> work\run_pack.bat, work\run_place.bat
```

Spec schema (all geometry in **mil**, origin-centered, y-down positive):
```json
{ "name":"ar0830", "type":"package", "units":"mil",
  "body_w":252.6, "body_h":154.1, "ball_dia":8, "refdes_prefix":"U",
  "pins":[ {"num":1,"x":-80,"y":50,"signal":"TEST"}, {"num":2,"x":-72,"y":50,"signal":"VDD"} ] }
```
`name` must be **lowercase** (it's the `.psm` filename and the `axlDBCreateSymbol` name).
Then run (each kills stale `allegro.exe` + `*.lck` first — required):
```
work\run_pack.bat                 # -> builds work\<name>.psm  (watch for "OK: <name>.psm created")
work\run_place.bat board.brd      # -> places <name> at origin in board.brd, saves
```

## Run pack — build the `.psm` (the authoring script, step by step)

What `run_pack.bat` is (the exact SKILL, `author_<name>.il`), in order — **order matters**:
```
(progn
  (axlDBChangeDesignExtents (list -E:-E E:E))          ; (1) canvas FIRST (E ~ body/2 + margin)
  (set 'PS (axlDBFindByName 'padstack "<name>_ball"))
  (unless PS (set 'PS (axlDBCreatePadStack "<name>_ball" nil
     (cons (make_axlPadStackPad ?layer "TOP" ?type 'REGULAR ?figure 'CIRCLE ?figureSize <d:d>) nil) t)))
  (axlDBCreateOpenShape (axlPathStart (list -bw:-bh bw:-bh bw:bh -bw:bh -bw:-bh)) t "PACKAGE GEOMETRY/PLACE_BOUND_TOP")
  (axlDBCreateCloseShape OP t)
  (if (axlDBCreatePin "<name>_ball" <x:y>
       (make_axlPinText ?number "<n>" ?offset 0:12
         ?text (make_axlTextOrientation ?textBlock "2" ?rotation 0.0 ?mirrored nil ?justify "center")))
       (set 'PINS (1+ PINS))) ...   ; (2..N) per pin
  (axlDBCreateText "U*" 0:0 (make_axlTextOrientation ?textBlock "1" ...) "REF DES/ASSEMBLY_TOP" nil) ; refdes TEXT
  (axlCompileSymbol ?symbol "<name>" ?type "package" ?silent t ?silentOnOverwrite t)
  (axlSaveDesign))
```
Run as: `allegro.exe -symbol package -nograph -s author_<name>.scr <dir>\<name>.dra`
(`-symbol package` opens a symbol-editor context; the `.dra` is auto-created if absent).

**Verified** (SPB_22.1, this session): AR0830 59-ball ODCSP, body 6.417×3.914 mm, ball Ø0.204 mm.
`ar0830.psm` 29,996 B, journal shows `EXTENTS OK / PADSTACK OK / BODY OK / REFDES-TEXT OK /
COMPILE OK`, `ar0830.log` = "Create symbol completed." Read `ar0830.log` and the journal, not rc.

## Run place — put the `.psm` into a board

What `run_place.bat board.brd` is (`place_<name>.il`), in order:
```
(progn
  (axlSetVariable "PSMPATH" "<dir with .psm>;%PSMPATH%")   ; forward slashes, keep existing entries
  (axlDBChangeDesignExtents (list -2000:-2000 2000:2000))  ; board is likely empty/small -> expand
  (set 'PS (axlDBFindByName 'padstack "<name>_ball"))
  (unless PS (set 'PS (axlDBCreatePadStack "<name>_ball" nil (cons (make_axlPadStackPad ?layer "TOP" ...) nil) t)))
  (set 'INST (axlDBCreateSymbol (list "<name>" "PACKAGE") 0:0))   ; l_symbolData form
  (axlSaveDesign))
```
Run as: `allegro.exe -nograph -s place_<name>.scr <path>\board.brd`.
**Verified**: empty `board.brd` 237,412 B → **269,352 B** after placement, journal
`extents OK / padstack OK / place OK / BOARD SAVED`, no `SPMHA1`/`SPMHSY`.

## Gotchas (each cost many rounds; do NOT rediscover)

1. **"outside of the extents" (`SPMHA1-70`/`SPMHA1-68`)** → `axlDBChangeDesignExtents`
   missing or box too small. Set it FIRST, make it bigger than the geometry.
2. **`SPMHCS-1: Symbol is missing a refdes`** at `axlCompileSymbol` → the refdes is a
   **text object on `REF DES/ASSEMBLY_TOP`** (NOT a pin, NOT a property).
   `axlDBCreateText "U*" 0:0 <orient> "REF DES/ASSEMBLY_TOP" nil`. Proven by Cadence's own
   `examples/skill/file/axltdesign2.il:37` (refdes text immediately precedes `axlCompileSymbol`).
3. **`SPMHSY-24: '<NAME>_BALL' not found in search path`** at place → the compiled `.psm`
   references the padstack by name. `axlDBCreatePadStack` is **session-only (no save-to-file
   flag)**, so the place script must **recreate the padstack** *before* `axlDBCreateSymbol`.
4. **`axlDBCreateSymDefSkeleton` "can only be applied to layout drawings"** → it's the layout
   (`.brd`) extents+pin API. In a `.dra` use `axlDBChangeDesignExtents` + `axlDBCreatePin` instead.
5. **`axlDBCreatePin ... "can only be applied to symbol drawings"`** → it's symbol-editor-only.
   In a `.brd` you *place* the compiled symbol; you don't create pins.
6. **SKILL reader quirk**: `(axlDBCreatePin ... (make_axlPinText ?number "1" ...))` — the
   pin-text orientation must be passed as `?text (make_axlTextOrientation ...)`, i.e. the
   `?text` **keyword is mandatory**; a positional 3rd arg → `iliMakeDefstruct: illegal argument list`.
   Field order for `axlTextOrientation`: `?textBlock <str> ?rotation <float> ?mirrored t/nil ?justify "center"`.
   `?number` takes a **string** (`"1"`, not `1`). `?offset` takes a point (`0:12`).
7. **`axlDBChangeSymbol`/`axlDBChangeName` do not exist**; to rename a placed instance you set
   `->refdes`, and the `l_symbolData` form `axlDBCreateSymbol (list "<name>" "PACKAGE")`
   auto-assigns a refdes (the symbol name). Placing with the bare-string form
   `axlDBCreateSymbol "U1" 0:0` gives `Refdes not found` — use the list form.
8. **Windows backslashes in SKILL strings break the reader** (`\U`/`\S` parse as escapes).
   The `PSMPATH` value and every file path inside the `.il`/`.scr` must use **forward slashes**.
   The generated loaders use absolute forward-slash paths — a relative `load "work/x.il"` fails
   silently when Allegro's CWD ≠ the script dir.
9. **`axlDBCreateShape`** needs an `axlPathStart(...)` object, not a raw point list.
   A package body boundary goes on `PACKAGE GEOMETRY/PLACE_BOUND_TOP` (class name has a SPACE,
   subclass has an UNDERSCORE) and must be **solid filled** (`t`, not `nil`) — unfilled gives
   `SPMHDB-184: Unfilled SHAPE may not exist on layer ...`.
10. **`axlMsgPut` integer/list rendering is unreliable** in 22.1 headless (mixed lists print
    blank). Judge success by the **artifact** (`.psm` exists, board byte-size grew) and by
    `ar0830.log`/`allegro.jrl`, not by trusting a `pins=` journal line. To read a count reliably,
    `sprintf` into a buffer var: `(set 'b "") (set 'b (sprintf b "n %d" PC)) (axlMsgPut b)`.

## Runner contract (headless hygiene — DO this around every allegro.exe call)

A second Allegro instance clobbers the journal to 0 bytes and races for locks. Around EVERY
run:
```
taskkill /F /IM allegro.exe      # kill stale
timeout 2                        # let it die
del *.lck, master.tag            # release locks  (also in the CWD and the file's dir)
# ... run allegro.exe -nograph -s <scr> <file> ...
timeout 2; taskkill /F /IM allegro.exe; del *.lck
```
Set `$env:CDS_INST_DIR = 'C:\cadence\SPB_22.1'` first. The journal is `allegro.jrl` in the CWD;
the compile log is `<name>.log`. Read both.

## Creating a fresh board from scratch

`board.brd` may already exist (your Sigrity board). To start a brand-new empty board, Allegro
auto-creates it the first time you open a non-existent `.brd` — just point the place script at
a new path (e.g. `newboard.brd`); Allegro creates it, `axlDBChangeDesignExtents` sizes it, and
placement works (verified: a never-before-seen `.brd` path opened with "Design opened" then
took the placed package). No separate "new board" tool is needed — placement on a fresh path
IS board creation in this headless flow.

## File map (what this skill ships + where outputs land)

```
.forjinn/skills/sigrity-footprint/
  SKILL.md            <- this file
  gen_footprint.py    <- the generator: spec.json -> author_*/place_*/run_*.bat
  work/               <- generated + built artifacts (author_*, place_*, run_*.bat,
                         <name>.dra, <name>.psm, <name>.log, test_place.brd)
```
`gen_footprint.py --example part.json` writes a ready AR0830-style spec to edit.
Edit `part.json` (the real ball positions from your `.csv`/OLB pin map), re-run the two
`python` lines, then `run_pack.bat` + `run_place.bat`.
