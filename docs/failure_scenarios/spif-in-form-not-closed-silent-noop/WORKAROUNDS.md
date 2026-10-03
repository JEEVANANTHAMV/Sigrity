# Workarounds: `spif_in` Dialog Left Open Causes Silent No-Op

## Verified Workaround

Immediately after the `specctra_in "<path>"` line and **before any other top-level command** (save, another command, or `quit`), issue:

```
setwindow form.spif_in
FORM spif_in CLOSE
setwindow pcb
```

This switches the command window to the form, closes it, and switches back to the PCB window, unblocking the dispatcher. This is already wired into `run_allegro_specctra_import` (spif_specctra_tools.py:105-107) — callers of that tool do not need to do anything. The workaround only matters if you are hand-authoring a `.scr`/Tcl script that runs `specctra_in` yourself.

Evidence: `sigrity_mcp/core/tool_status.py:235-236` — "Fixed by inserting `setwindow form.spif_in` / `FORM spif_in CLOSE` / `setwindow pcb` between the `specctra_in` line and whatever runs next"; live-verified end-to-end in the same function (import + save + `report.exe` read-back all matching, per `sigrity_mcp/core/tool_status.py:244-256`).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Insert the 3-line form-close sequence after `specctra_in` | worked — save and every following command execute correctly; live-verified end-to-end | `sigrity_mcp/core/tool_status.py:228-256`; spif_specctra_tools.py:105-107 |
| 2 | Rely on `specctra_in` to close its own form | didnt_work — confirmed live, the form stays open (modeless) afterward | `sigrity_mcp/core/tool_status.py:231-234`; spif_specctra_tools.py:99-104 comment |
| 3 | Omit the save entirely and treat the in-memory post-import state as the deliverable | not_applicable for this suite — the whole point of `run_allegro_specctra_import` producing an `output_file` is that the board must be saved to disk for `report.exe`/downstream tools to read; unsaved in-memory state is lost when the session quits | spif_specctra_tools.py:108-113 |

## Prevention

1. If you hand-write any Allegro script that calls `specctra_in`, always follow it immediately with the 3-line close sequence above — do not assume the form is self-closing, even though the docs describe the same-line-argument form as "auto-running."
2. If an Allegro session reports `succeeded`/rc 0 but downstream read-back (`report.exe`) shows no change on disk, grep the design's **own** `allegro.jrl` journal (not `run.log`) for the exact string `Finish current command first` — that is the specific tell for this failure, and it will be the **only** trace of the problem anywhere.
3. Never treat `state:"succeeded"` from an `allegro_run_session` as proof that a queued save actually executed — independently check the output file's size/sha1, as every live verification of this tool's fix was done.

## Remaining Gaps

- This suite has no tool that reads Allegro's own `.jrl` journal and surfaces its contents into a job's normal output surface (`run.log`, job dir, `get_job_status`) — so this specific silent-failure signature (`Finish current command first` in `.jrl` only) is only diagnosable by a human or agent who knows to look there. No in-suite automated detection exists for it, though this specific code path is now fixed so the bug itself should not recur in `run_allegro_specctra_import`.
