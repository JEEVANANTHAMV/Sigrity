"""gen_footprint.py -- generate Allegro headless SKILL scripts to author a package
symbol (footprint) from scratch and/or place it on a board. 100% headless (no GUI).

Proven workflow (SPB 22.1, verified live):
  package .dra (symbol editor)  : axlDBChangeDesignExtents + axlDBCreatePadStack
                                   + body boundary on PACKAGE GEOMETRY/PLACE_BOUND_TOP
                                   + N x axlDBCreatePin + refdes text on REF DES/ASSEMBLY_TOP
                                   -> axlCompileSymbol -> <name>.psm
  board .brd (layout)           : axlSetVariable PSMPATH + axlDBChangeDesignExtents
                                   -> axlDBCreateSymbol (list "<name>" "PACKAGE") -> axlSaveDesign

Input spec (JSON) -- see make_spec() below for the full schema:
  {
    "name":   "ar0830",            # psm name (lowercase, used in PSMPATH + axlDBCreateSymbol)
    "type":   "package",
    "units":  "mil",               # all below are in mils (1 OLB/ball-map unit == 1 mil)
    "body_w": 252.6,               # body outline width  (6.417 mm)
    "body_h": 154.1,               # body outline height (3.914 mm)
    "ball_dia": 8,                 # ball pad diameter in mils (~0.204 mm)
    "refdes_prefix": "U",          # refdes text (U for IC). Use "U*" for a library placeholder.
    "pins": [ {"num":1,"x":-80,"y":50,"signal":"TEST"}, ... ]   # x/y in mils, origin-centered
  }

Outputs (written into --outdir):
  author_<name>.il   -- the symbol-editor SKILL (run against a fresh <name>.dra)
  author_<name>.scr  -- loader: skill (load "...author_<name>.il"); quit
  place_<name>.il    -- the layout (board) SKILL
  place_<name>.scr   -- loader
  run_pack.bat       -- powershell: run the authoring headless, compile .psm
  run_place.bat      -- powershell: run placement on a board, save

Usage:
  python gen_footprint.py spec.json --outdir work/
  python gen_footprint.py --example spec.json   # write an AR0830-style example spec

Then, in a PowerShell prompt, run run_pack.bat then run_place.bat (see SKILL.md).
"""
import argparse, json, os, sys, math

def _mil(v):
    """Round a float to int mils for SKILL point literals."""
    return int(round(float(v)))

def _ball_grid(pitch_mil, cols, rows, first_at):
    """Generate a rectangular ball-grid pin list. first_at=(x0,y0) top-left in mils.
    Row-major numbering: 1..cols across the first row, then next row. Returns pin dicts."""
    pitch = float(pitch_mil)
    x0, y0 = float(first_at[0]), float(first_at[1])
    pins = []
    n = 1
    for r in range(rows):
        for c in range(cols):
            pins.append({"num": n, "x": _mil(x0 + c*pitch), "y": _mil(y0 - r*pitch), "signal": ""})
            n += 1
    return pins

def make_spec_example(path):
    """Write an AR0830-style 59-ball ODCSP example spec (2 rows of balls, 0.204mm pitch)."""
    pitch = 8.03  # 0.204 mm in mils
    # 6 col x 10 row layout (60 cells), pin 60 omitted -> 59 balls
    cols, rows = 6, 10
    # center the grid: place first (top-left) ball so the field is centered on 0:0
    x0 = -((cols - 1) / 2.0) * pitch
    y0 =  ((rows - 1) / 2.0) * pitch
    pins = _ball_grid(pitch, cols, rows, (x0, y0))
    # drop the 60th to model 59-ball (last row last col). (Adjust to your real map.)
    if len(pins) > 59:
        pins = pins[:59]
    spec = {
        "name": "ar0830", "type": "package", "units": "mil",
        "body_w": 252.6, "body_h": 154.1, "ball_dia": 8,
        "refdes_prefix": "U",
        "pins": pins
    }
    json.dump(spec, open(path, "w"), indent=2)
    print("wrote example spec:", path, "pins:", len(pins))

def emit_author_il(spec, outdir):
    name = spec["name"]
    n = len(spec["pins"])
    E = int(math.ceil(max(spec.get("body_w", 300), spec.get("body_h", 300)) / 2.0)) + 200
    E = max(E, 400)  # generous canvas so all pins + boundary are inside extents
    bw, bh = int(round(spec.get("body_w", 300) / 2)), int(round(spec.get("body_h", 200) / 2))
    bd = int(round(spec.get("ball_dia", 8)))
    rf = spec.get("refdes_prefix", "U")
    pin_label_blk = "2"   # text block for pin numbers
    refdes_blk    = "1"   # text block for refdes

    L = ["(progn",
         '(axlMsgPut "PKG AUTHOR %s")' % name.upper(),
         "; (1) establish design extents first",
         "(set 'ER (axlDBChangeDesignExtents (list -%d:-%d %d:%d)))" % (E, E, E, E),
         '(axlMsgPut (list "EXTENTS" (if ER "OK" "FAIL")))',
         "; (2) ball padstack",
         "(set 'PS (axlDBFindByName 'padstack \"%s_ball\"))" % name,
         ("(unless PS (set 'PS (axlDBCreatePadStack \"%s_ball\" nil "
          "(cons (make_axlPadStackPad ?layer \"TOP\" ?type 'REGULAR ?figure 'CIRCLE ?figureSize %d:%d) nil) t)))"
          % (name, bd, bd)),
         '(axlMsgPut (list "PADSTACK" (if PS "OK" "FAIL")))',
         "(set 'PINS 0)",
         "; (3) body boundary on PLACE_BOUND_TOP (solid filled)",
         "(set 'BP (axlPathStart (list -%d:%d %d:%d %d:%d -%d:-%d -%d:%d)))" % (bw,bh,bw,bh,bw,-bh,-bw,-bh,-bw,bh),
         "(set 'OP (axlDBCreateOpenShape BP t \"PACKAGE GEOMETRY/PLACE_BOUND_TOP\"))",
         "(set 'CS (axlDBCreateCloseShape OP t))",
         '(axlMsgPut (list "BODY" (if CS "OK" "FAIL")))',
         "; (4) %d pins" % n]
    for p in spec["pins"]:
        L.append("(if (axlDBCreatePin \"%s_ball\" %d:%d "
                 "(make_axlPinText ?number \"%d\" ?offset 0:12 "
                 "?text (make_axlTextOrientation ?textBlock \"%s\" ?rotation 0.0 ?mirrored nil ?justify \"center\"))) "
                 "(set 'PINS (1+ PINS)))" % (name, _mil(p["x"]), _mil(p["y"]), p["num"], pin_label_blk))
    L += ['; (5) refdes TEXT (REQUIRED for axlCompileSymbol -- otherwise SPMHCS-1)',
          "(set 'RDOR (make_axlTextOrientation ?textBlock \"%s\" ?rotation 0.0 ?mirrored nil ?justify \"center\"))" % refdes_blk,
          "(set 'RD (axlDBCreateText \"%s*\" 0:0 RDOR \"REF DES/ASSEMBLY_TOP\" nil))" % rf,
          '(axlMsgPut (list "REFDES-TEXT" (if RD "OK" "FAIL")))',
          '; (6) compile -> psm',
          "(set 'C (axlCompileSymbol ?symbol \"%s\" ?type \"package\" ?silent t ?silentOnOverwrite t))" % name,
          '(axlMsgPut (list "COMPILE" (if C "OK" "FAIL")))',
          "(axlSaveDesign)",
          '(axlMsgPut (strcat "DONE pins=" PINS " of" %d))' % n,
          ")"]
    il = os.path.join(outdir, "author_%s.il" % name)
    open(il, "w").write("\n".join(L))
    open(os.path.join(outdir, "author_%s.scr" % name), "w").write(
        'skill (load "%s")\nquit\n' % il.replace("\\", "/"))
    return il

def emit_place_il(spec, outdir, psmpath_hint):
    name = spec["name"]
    L = ["(progn",
         '(axlMsgPut "PLACE %s")'.replace(" %s" % name, " %s" % name.upper()),
         "; put the compiled .psm on PSMPATH (keep any existing entries)",
         "(axlSetVariable \"PSMPATH\" \"%s;%%PSMPATH%%\")" % psmpath_hint,
         "; expand the (likely empty/small) board extents so the package fits at origin",
         "(set 'ER (axlDBChangeDesignExtents (list -2000:-2000 2000:2000)))",
         '(axlMsgPut (list "extents" (if ER "OK" "FAIL")))',
         "; place the package (l_symbolData form: (name type)). Refdes is auto-assigned.",
         "(set 'INST (axlDBCreateSymbol (list \"%s\" \"PACKAGE\") 0:0))" % name,
         '(axlMsgPut (list "place" (if INST "OK" "FAIL")))',
         "(axlSaveDesign)",
         '(axlMsgPut "BOARD SAVED")',
         ")"]
    il = os.path.join(outdir, "place_%s.il" % name)
    open(il, "w").write("\n".join(L))
    open(os.path.join(outdir, "place_%s.scr" % name), "w").write(
        'skill (load "%s")\nquit\n' % il.replace("\\", "/"))
    return il

def emit_run_bats(spec, outdir, spb_root):
    name = spec["name"]
    allegro = os.path.join(spb_root, "tools", "bin", "allegro.exe").replace("\\", "/")
    # run_pack: author the .dra (fresh), compile .psm
    pack = [
        "@echo off",
        "setlocal",
        "set CDS_INST_DIR=%s" % spb_root,
        "set ARDIR=%cd%"
        "rem kill stale allegro + locks",
        "taskkill /F /IM allegro.exe >nul 2>&1",
        "timeout /t 2 >nul",
        "del /q %ARDIR%\\*.lck >nul 2>&1",
        "del /q %ARDIR%\\master.tag >nul 2>&1",
        "del /q %ARDIR%\\%name%.dra >nul 2>&1",
        "del /q %ARDIR%\\%name%.psm >nul 2>&1",
        "echo AUTHORING %name%.psm headless..." % name,
        '"%s" -symbol package -nograph -s "%ARDIR%\\author_%s.scr" "%ARDIR%\\%s.dra"' % (allegro, name, name),
        "timeout /t 2 >nul",
        "taskkill /F /IM allegro.exe >nul 2>&1",
        "del /q %ARDIR%\\*.lck >nul 2>&1",
        'if exist "%ARDIR%\\%s.psm" (echo OK: %s.psm created) else (echo WARN: check %s.log)' % (name, name, name),
        "endlocal"
    ]
    # run_place: place into a .brd (board path is $1, default place_%s.brd in same dir)
    place = [
        "@echo off",
        "setlocal",
        "set CDS_INST_DIR=%s" % spb_root,
        "set ARDIR=%cd%"
        "set BRD=%~1",
        'if "%BRD%"=="" set BRD=%ARDIR%\\%s.brd' % name,
        "taskkill /F /IM allegro.exe >nul 2>&1",
        "timeout /t 2 >nul",
        "del /q %ARDIR%\\*.lck >nul 2>&1",
        "echo PLACING %s into %BRD ..." % name,
        '"%s" -nograph -s "%ARDIR%\\place_%s.scr" "%BRD%"' % (allegro, name),
        "timeout /t 2 >nul",
        "taskkill /F /IM allegro.exe >nul 2>&1",
        "del /q %ARDIR%\\*.lck >nul 2>&1",
        'if exist "%BRD%" (echo OK: saved to %BRD%) else (echo WARN: board not saved)',
        "endlocal"
    ]
    open(os.path.join(outdir, "run_pack.bat"), "w").write("\r\n".join(pack))
    open(os.path.join(outdir, "run_place.bat"), "w").write("\r\n".join(place))

def main():
    ap = argparse.ArgumentParser(description="Generate Allegro headless SKILL scripts for package authoring/placement")
    ap.add_argument("spec", help="path to spec JSON (or --example writes an example)")
    ap.add_argument("--outdir", default="work", help="output dir for scripts (default ./work)")
    ap.add_argument("--spb-root", default=r"C:\cadence\SPB_22.1", help="Cadence SPB root")
    ap.add_argument("--psmpath", default=None, help="dir holding the .psm (default = outdir)")
    ap.add_argument("--example", action="store_true", help="write an example spec to SPEC path and stop")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    if a.example:
        make_spec_example(a.spec)
        return
    spec = json.load(open(a.spec))
    psmpath = a.psmpath or a.outdir
    il = emit_author_il(spec, a.outdir)
    pl = emit_place_il(spec, a.outdir, psmpath.replace("\\", "\\"))
    emit_run_bats(spec, a.outdir, a.spb_root)
    print("name   :", spec["name"])
    print("pins   :", len(spec["pins"]))
    print("author :", il)
    print("place  :", pl)
    print("runers :", os.path.join(a.outdir, "run_pack.bat"), "|", os.path.join(a.outdir, "run_place.bat"))
    print("\nSteps:  1) run run_pack.bat  -> builds %s.psm\n         2) run run_place.bat board.brd  -> places + saves" % spec["name"])

if __name__ == "__main__":
    main()
