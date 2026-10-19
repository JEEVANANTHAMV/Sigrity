# CAD Domain — Failed / Known-Blocked Tools: Full Reference

> **UPDATE (2026-10-18) — Section 1 (OrCAD Capture, 12 tools) below is now FULLY
> SUPERSEDED for everything those tools actually exist to accomplish.** The stated root
> cause ("Machine-level defect in Capture's `Open <project>` path") was incomplete: the
> real cause of the hang is an embedded Start Page widget making a blocking network call
> through the system proxy at startup, fixed via `ENABLE_CAPTURE_AUTOMATION=TRUE` (now
> applied automatically to every Capture launch). More importantly, the complete
> read-author-netlist-import pipeline these 12 tools were meant to cover is now solved
> end to end by a different, Capture.exe-free mechanism — `tclsh.exe` loading Capture's
> own database DLL directly (`sigrity_mcp/domains/cad/capture_headless_tools.py`):
> `extract_capture_netlist_headless` (read an existing `.dsn`), `author_capture_
> schematic_headless` (create a new design, place real parts, draw wires, AND assign
> real, persistent reference designators via a second occurrence-level pass), and
> `generate_capture_pcb_netlist` (wraps `pstswp.exe`, a separate real executable, to
> produce a PCB netlist directly from the `.dsn` — closing the last gap, Capture's own
> GUI-only "Create Netlist" menu command). CONFIRMED LIVE end to end: an authored-from-
> nothing design's netlist was fed into `run_netrev_import` and the resulting Allegro
> `.brd` independently verified via `report.exe`'s BOM report showing the correct
> `REFDES`. The 12 tools catalogued below still genuinely fail exactly as described
> (their underlying mechanism — Capture.exe's own interactive Tcl session — was not
> fixed, only superseded), so this section remains an accurate technical reference for
> *why that specific path* is blocked, not for what's actually achievable today. See
> `core.tool_status.TOOL_STATUS_NOTES["tclsh"]`/`["pstswp"]`/`["capture"]` for the
> complete current evidence, including why `Capture.Application` COM and `syscap.exe`
> were both investigated and ruled out as alternatives.

**Scope:** the 18 MCP tools in `sigrity_mcp/domains/cad/` that **cannot complete** on this install (status `known_blocked`, plus 1 confirmed product-crash). For every tool: what it does, its exact input arguments, the **exact command / script it generates**, the **failure it faces**, and the root cause. Nothing here is paraphrased from memory — signatures and argv are traced verbatim from source, and each failure is quoted from the live test evidence in `sigrity_mcp/core/tool_status.py`.

**The 4 affected Cadence softwares:**

| # | Software (exe) | Tools | # | Cause class |
|---|---|---|---|---|
| 1 | **OrCAD Capture** (`Capture.exe`) | 11 tools + `generate_schematic_from_spec` | **12** | Machine-level defect in Capture's `Open <project>` path |
| 2 | **SPB Translators** (`con2xml`/`cap2xml`/`dml2con`/`apd2con`) | 4 tools | **4** | Feature pack not installed (empty stubs) |
| 3 | **checkplus** (`checkplus.exe`) | 1 tool | **1** | Wrong product scope (DE-HDL, no `.brd` input) |
| 4 | **designextractor** (`designextractor.exe`) | 1 tool | **1** | Needs an external connectivity server |
| | | | **18** | |

---

## How the commands are actually built (read this first)

Every standalone-CLI tool here calls (in `sigrity_mcp/core/process.py:120-133`):

```python
exe  = executables.resolve(tool)              # e.g. ...SPB_22.1\tools\bin\con2xml.exe
argv = list(build_args or [])
if tcl_script is not None:                    # TRUE only for Capture
    script_path = tcl_script.write(job_dir / script_filename)
    argv += [str(script_path)]                # tcl_arg_flag is None for Capture
argv += list(extra_args or [])
command = [str(exe), *argv]                   # spawned via create_subprocess_exec(*command, cwd=job_dir)
```

`job_dir = runs/<tool>-<uuid10>/`, process spawned with **`cwd = job_dir`**, output → `job_dir/run.log`. So for the four non-Capture tools the final command is **literally just the exe + the args below** — there is no hidden script token.

---

## 1. OrCAD Capture — 12 tools, all `known_blocked`

**Software:** `C:\Cadence\SPB_22.1\tools\bin\Capture.exe`
**Invocation style:** Tcl session (compose-then-run). The tools below only *append lines* to an in-memory macro; the single command that actually launches is built by `capture_run_session`.

### 1.0 The exact command that is launched

`capture_run_session` appends two trailing lines and then runs (verbatim from `capture_tools.py:235-243`):

```python
tcl_sessions.add_line(session_id, 'Menu "File::Close"')
tcl_sessions.add_line(session_id, 'Menu "File::Exit"')
record = await run_session(
    session_id,
    tool="capture",
    tcl_arg_flag=None,                 # <- NO flag: the .tcl path is a bare positional arg
    build_args=[f"-product={product}"],
    script_filename="macro.tcl",
)
```

**Final on-disk command** (after `submit_job` assembles it; cwd = `job_dir`):

```
<SPB_22.1>\tools\bin\Capture.exe -product=OrCAD Capture <jobdir>\macro.tcl
```

i.e. argv tokens: `["…\Capture.exe", "-product=OrCAD Capture", "<jobdir>\macro.tcl"]`
(`-product=OrCAD Capture` is a single token with an internal space.)

**The `macro.tcl` it writes** is the queued lines, in call order, one per line (trailing newline). A full run looks like:

```tcl
Open <project>                    ; start_capture_session  (\ -> / conversion)
SelectPMItem {<design>}           ; capture_select_page
OPage {<schematic_folder>} {<page>} ; capture_select_page
PlacePart <x> <y> {<library_file>} {<part_name>} {<package>} FALSE   ; capture_place_part
PlaceWire <x1> <y1> <x2> <y2>                                ; capture_place_wire
PlacePin <x> <y> {<pin_name>} {<pin_type>} FALSE             ; capture_place_pin
SetProperty {<prop>} {<val>}                                 ; capture_set_property
Menu "Tools::Annotate"                                 ; capture_annotate
Menu "PCB::Design Rules Check"                         ; capture_check_design_rules
Menu "Tools::Create Netlist"                           ; capture_create_netlist
Menu "File::Save"                                      ; capture_save
Menu "File::Close"                                     ; capture_run_session
Menu "File::Exit"                                      ; capture_run_session
```
(`{...}` = `tcl_str` brace-quoting; an empty `package` renders as `{ }`.)

### 1.1 The 12 tools (signatures, args, the Tcl line each emits)

| Tool | Signature | Emits into macro.tcl |
|---|---|---|
| `start_capture_session` | `(project_file: str) -> dict` | `clear_stale_design_lock(project_file)`, then `Open <project>` |
| `capture_select_page` | `(session_id, design, schematic_folder, page) -> dict` | `SelectPMItem {design}` + `OPage {schematic_folder} {page}` |
| `capture_place_part` | `(session_id, x: float, y: float, library_file, part_name, package="") -> dict` | `PlacePart {x} {y} {library_file} {part_name} {package} FALSE` |
| `capture_place_wire` | `(session_id, x1: float, y1: float, x2: float, y2: float) -> dict` | `PlaceWire {x1} {y1} {x2} {y2}` |
| `capture_place_pin` | `(session_id, x: float, y: float, pin_name, pin_type="Passive") -> dict` | `PlacePin {x} {y} {pin_name} {pin_type} FALSE` |
| `capture_set_property` | `(session_id, property_name, value) -> dict` | `SetProperty {property_name} {value}` |
| `capture_annotate` | `(session_id) -> dict` | `Menu "Tools::Annotate"` |
| `capture_check_design_rules` | `(session_id) -> dict` | `Menu "PCB::Design Rules Check"` |
| `capture_create_netlist` | `(session_id) -> dict` | `Menu "Tools::Create Netlist"` |
| `capture_save` | `(session_id) -> dict` | `Menu "File::Save"` |
| `capture_run_session` | `(session_id, product="OrCAD Capture") -> dict` | appends `Menu "File::Close"` + `Menu "File::Exit"`, **then launches** the command in §1.0 |
| `capture_handle_custom_launch_dialog` | `(button="No") -> dict` | *not* a macro line — Win32: finds the "Capture Custom Launch" window and sends `BM_CLICK` (0x00F5) to the button |

`generate_schematic_from_spec` (see §1.3) is the 12th — it just calls all of the above in sequence.

### 1.2 The failure (verbatim root cause from `tool_status.py["capture"]`)

The wrappers are internally correct. The block is in **Capture's own `Open <project>` code path**:

> "the hang reproduces with a *different*, simpler shipped sample project (FullAdder.opj, pure schematic, no PCB data) using ONLY the minimal Open+Close+Exit script (no placement at all) — identical **0-byte log, no `.lck` file ever written** into the project directory (i.e. the `Open <project>` step itself never completes, before any Part/Wire/Pin command has a chance to run), **100% CPU spin, and *zero* windows** for the entire hang (checked live via EnumWindows, so it is not hidden behind a modal dialog of any kind)."

> "Meanwhile `Capture.exe -version` alone returns cleanly in ~0.1s … — so Capture.exe is not fully broken, but its **project-opening code path (the first thing any real automation script does) hangs deterministically, with no CLI flag or documented workaround** found in the local doc tree, and no reproducible fix available to this suite's Python wrapper layer."

**Observed signatures (all three seen on this machine):**
1. **Long hang** — runs the full 90 s/5 min wait, 0-byte log, 100% CPU, must be killed.
2. **"Succeeded" in ~0.1 s** with a completely empty `run.log` — the script is rejected (session not ready / unhandled `Open` error), Capture exits fast having done **nothing**. *Do not read this as success — check for real output, not the state.*
3. **Falls back to the tutorial project** instead of running the given script.

**Why the documented workarounds don't fix it:**
- The stale-`.lck` fix (`clear_stale_design_lock`) is a **no-op here** — the `Open` step never completes, so **no `.lck` is ever written**. (It *did* help Allegro, proven live: a planted stale lock was auto-cleared and the job finished in 5.3 s instead of hanging.)
- `capture_handle_custom_launch_dialog` patches a **separate, narrower** problem — the "Capture Custom Launch" crash-recovery dialog (a prior-session `ACCESS_VIOLATION` in `orPrmWebCompIE64.dll`), **not** the main `Open` hang.

**Bottom line:** Capture's documented CLI (`Capture_Command_Line_Arguments_and_Switches.html`) only supports `-version`/`-viewer`/`-product=<name>`/`-i <ini>` — there is **no headless "run-and-exit" mode**. The bare-arg form `capture <script.tcl>` (*Execute TCL script in Windows*) is real but "after the script executes, it opens as a text file in edit mode in Capture" and replays into a still-initializing GUI. **Fix = a working `syscap.exe` batch mode or a Cadence-level patch — not fixable in this wrapper.**

### 1.3 `generate_schematic_from_spec` — the 12th blocked tool

```python
async def generate_schematic_from_spec(
    project_file: str,
    parts: list[dict],                 # each: {x, y, library_file, part_name, package?}
    wires: Optional[list[dict]] = None,# each: {x1, y1, x2, y2}
    pins: Optional[list[dict]]   = None,# each: {x, y, pin_name, pin_type?}
    design: Optional[str]      = None,
    schematic_folder: Optional[str] = None,
    page: Optional[str]        = None,
    annotate: bool = True,
    create_netlist: bool = True,
) -> dict
```
`parts`, and *all three* of `design`+`schematic_folder`+`page`, must be supplied consistently (partial → early `{"error":…}`). It is a pure composition of the capture primitives above — `schematic_generation_tools.py:132` `start_capture_session`, `:134` `capture_select_page`, `:142` `capture_place_part` (loop), `:152` `capture_place_wire` (loop), `:155` `capture_place_pin` (loop), `:164` `capture_annotate`, `:166` `capture_create_netlist`, `:167` `capture_save`, `:169` `capture_run_session`, `:170` `auto_dismiss_recovery_dialog_if_stuck`. **It inherits the Capture `Open` block verbatim** — one-call sugar over the same broken path. Returns `{**run_result, "parts_placed":N, "wires_placed":N, "pins_placed":N, "page":"…"}`.

---

## 2. SPB Translators — 4 tools, all `known_blocked`

**Software:** `C:\Cadence\SPB_22.1\tools\bin\{con2xml,cap2xml,dml2con,apd2con}.exe`
**Invocation style:** standalone CLI, `submit_job(tool=…, build_args=[input_file, output_file?])`.

All four share the identical argv shape (verbatim, `interchange_tools.py`):

```python
args = [input_file]
if output_file:
    args.append(output_file)
record = await submit_job(tool="<exe>", build_args=args)
```

| Tool | Translation | Final command |
|---|---|---|
| `run_con2xml(input_file, output_file=None)` | Concept-HDL netlist → XML | `con2xml.exe <input_file> [<output_file>]` |
| `run_cap2xml(input_file, output_file=None)` | OrCAD Capture `.opj` → XML | `cap2xml.exe <input_file> [<output_file>]` |
| `run_dml2con(input_file, output_file=None)` | DML (SI model library) → Concept-HDL | `dml2con.exe <input_file> [<output_file>]` |
| `run_apd2con(input_file, output_file=None)` | Allegro Package Designer → Concept-HDL | `apd2con.exe <input_file> [<output_file>]` |

### 2.1 The failure (verbatim root cause — `tool_status.py["con2xml"]`)

> "RE-TESTED 2026-10-11 — confirmed GENUINELY ABSENT on this build (truly blocked, not a mislabel). Hard evidence beyond the earlier 'No Product License selected' message: the four translator exes (`con2xml.exe`/`cap2xml.exe`/`dml2con.exe`/`apd2con.exe`) are **~46KB empty PE *stubs*** — they produce **ZERO output on ANY invocation** including `-help`, `-v`, no-args, `CDS_PRODUCT=SPB`, and a real sample input (e.g. the shipped `top.con`); each process dies before printing anything, and the exit code is lost (reads as null). By contrast `extracta.exe -help` returns 88 lines of real docs. No CDS product is configured (`CDS_LIC_ONLY=1`, `CDS_LIC_FILE=5280@localhost`, `cdsinfo.exe` finds no tag — no product selected that includes Translators). The Translators **DATA** is shipped … but the **tools are not licensed in this build**. **NOT a FlexNet/license issue and NOT a CLI mis-use — the feature pack is simply not in this install; no env/product re-selection unblocks it.**"

Per-exe specifics:
- `cap2xml` — `No Product License selected… Translation cancelled.`, exit 0, against the real `Fault-Detector.opj`.
- `dml2con` — `No Product License selected`, exit 2, against the real `hspice_bbox_template.dml` (DML has no other reader on this machine).
- `apd2con` — `No Product License selected`, exit 2; **doubly blocked** — no `.apd` sample exists anywhere in the install.

**Working alternative for netlist→XML on this build:** `run_allegro_extracta` (`extracta.exe`, confirmed live with its XML export flags).

**Note:** each exe's exact flag convention is a best-effort transcription — the capability gate fires *before* `-help` prints, so flag syntax was never independently confirmed.

---

## 3. checkplus — 1 tool, `known_blocked` (out of scope, not a defect)

**Software:** `C:\Cadence\SPB_22.1\tools\bin\checkplus.exe`
**Invocation style:** standalone CLI.

```python
async def run_allegro_checkplus(
    project_file: str,
    verbose: bool = False,
    max_messages: Optional[int] = None,
    include_path: Optional[str] = None,
    env_file: Optional[str] = None,
    rule_file: Optional[str] = None,
) -> dict
```
argv build (verbatim):
```python
args = ["-proj", project_file]
if verbose:        args.append("-verbose")
if max_messages is not None: args += ["-max_messages", str(max_messages)]
if include_path:   args += ["-I", include_path]
if env_file:       args += ["-r", env_file]
if rule_file:      args += ["-r", rule_file]    # both env & rule map to -r (Cadence overload)
record = await submit_job(tool="allegro_checkplus", build_args=args)
```
**Final command:** `checkplus.exe -proj <project_file> [-verbose] [-max_messages <n>] [-I <path>] [-r <env>] [-r <rule>]`

### 3.1 The failure (verbatim — `tool_status.py["allegro_checkplus"]`)

> "RE-TESTED 2026-10-11 with all four `-proj` forms (the sample dir, the cp.dat file, cwd-inside-the-dir + `-proj .`, cwd + `-proj cp.dat`) — **ALL fail with `[5038] does not exist` / `[3042] Cannot Load Project File`.** Root cause is now unambiguous: `cp.dat` in the shipped sample is a CONCEPT ruleset list … and the doc tree's own title is 'Allegro **Design Entry HDL** Rules Checker' — i.e. **checkplus checks Concept-HDL/DE-HDL design RULES, and there is NO Allegro `.brd` physical-layout input path at all** (zero .brd in the sample dir). So this is correctly 'not applicable to our Allegro .brd flow', NOT a launch/license/argv defect. **Do not use it for PCB sign-off; the DRC path for `.brd` is `batch_drc` / `allegro_run_drc` (both confirmed live).**"

**Status:** "failed" only in the sense of *wrong product for the job* — the tool itself is correctly implemented; it's simply not the DRC path for a `.brd` board.

---

## 4. designextractor — 1 tool, `known_blocked` (missing external dependency)

**Software:** `C:\Cadence\SPB_22.1\tools\bin\designextractor.exe`
**Invocation style:** standalone CLI. **Requires a `.cpm`/`.sdax` project file — not a `.brd`.**

```python
async def run_allegro_design_extractor(
    project_file: str,
    output_file: Optional[str] = None,
    pretty_format: bool = True,
    elastic_url: Optional[str] = None,
    connectivity_server_as_source: bool = False,
) -> dict
```
argv build (verbatim):
```python
args = ["-p", project_file]              # [Mandatory], .cpm/.sdax only
if output_file:  args += ["-o", output_file]
if pretty_format: args.append("-f")      # on by default
if elastic_url:  args += ["-u", elastic_url]   # defaults to http://localhost:9200
if connectivity_server_as_source: args.append("-c")
record = await submit_job(tool="allegro_designextractor", build_args=args)
```
**Final command:** `designextractor.exe -p <project_file> [-o <out>] [-f] [-u http://localhost:9200] [-c]`

### 4.1 The failure (verbatim — `tool_status.py["allegro_designextractor"]`)

> "RE-TESTED 2026-10-11 — confirmed buildable but PRECONDITIONED on a running connectivity server, not on input. `-help` shows `-p` (a .cpm/.sdax) is [Mandatory] and a `-u default http://localhost:9200` Elastic/connectivity URL. 112 .cpm + 12 .sdax files ARE shipped … so the input is obtainable — but running designextractor against any of them **returned rc=0xFFFFFFFF with only the usage banner, because the Elastic/connectivity server it expects to be running at localhost:9200 was not.** So this is NOT a defect and NOT blocked on a missing sample — **it needs the connectivity server (the `-u` target) up** before it will extract a real project. For direct `.brd` extraction without that dependency, use `allegro_extracta` (extracta.exe), which is confirmed live."

**To unblock:** start the Elastic/connectivity server at `localhost:9200` (or pass a reachable one via `elastic_url`), then supply a real `.cpm`/`.sdax`.

---

## Appendix A — the 5th "broken" path worth knowing: `run_specctra_import_session`

Not counted in the 18 (it's a duplicate of a working capability), but **confirmed product-crash**:

| Tool | Exe | Command | Failure |
|---|---|---|---|
| `run_specctra_import_session(board_file, session_file)` | `spif_batch.exe` | `spif_batch.exe -i <board.brd> <session.ses>` | **Deterministic product-level crash `ERROR(SPMHDB-238)`** — dies on every run. **Do not use.** |
| `run_allegro_specctra_import(board_file, session_file, output_file)` *(the fix)* | `allegro.exe` (script replay) | `allegro.exe -s <macro.scr> <board.brd>` where the macro runs the real `specctra_in <session.ses>` (+ closes the `spif_in` form) | **confirmed_live end-to-end** (real routed `.brd` written, 163/163 connections, 451.5 in trace, 0 vias — verified by `report.exe`). |

Use `run_allegro_specctra_import`; avoid `run_specctra_import_session`.

---

## Appendix B — what this does NOT count as "failed" (for honesty)

- **10 `built_untested` tools** (launch fine, just unproven on real data): `allegro_zrouter`, `run_allegro_gerber_plot`, `run_idf_import`, `run_idx_import`, `run_die_abstract_check`, `run_die_abstract_compare`, `run_ibis_check` (versions 3/4/5), `allegro_get_module_instance_location`, `allegro_get_net_length`.
- **`allegro_place_module_instance`** — correctly implemented; blocked on a *board/library-path precondition* (`axlGetParam("library:CAP300")` returns nil on this board), an environmental gap, not a software defect.

**Net:** of the 83 CAD tools, **18 are genuinely failed/known_blocked** (78% work or are merely untested).
