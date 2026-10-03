# stream-out-needs-predefined-films — Workarounds

## What works (confirmed — the precondition pattern)

- **The film-record precondition itself IS solved in-suite**: `allegro_create_film` (SKILL `axlFilmCreate`) + `allegro_save_design` + `allegro_run_session` (all confirmed live, see the `allegro_artwork`/Gerber scenarios) author the film records `stream_out` would need. A board prepared this way satisfies the "pre-defined artwork film records" requirement.
- The related, already-wrapped tools that share this precondition are fully usable: `run_allegro_generate_artwork` (Gerber RS274X) and `run_allegro_gerber_plot` (pen-plotter) both operate on those board films and are the paths to use for film-derived output today.

## What was tried / ruled out

- **There is no in-suite `stream_out` wrapper to call** — it was deliberately left unwrapped this pass. The README is explicit that the only missing piece is the wiring ("just not wired up for this tool yet"), not the precondition itself.
- No confirmed end-to-end GDSII-stream result exists, so GDSII Stream export is not a verified capability.

## How to close the gap (future work)

- Add a `run_stream_out` wrapper (submit_job-style, with the standard absolute-path convention used across this executable family) that takes the film-authoring output as its precondition. The film-creation side is already demonstrated; only the stream_out invocation wrapper is absent.

## Notes

- Status is `built_untested`/unwrapped, not a demonstrated bug — the "needs films" requirement is an inference from its documented relation to the same film-record mechanism `artwork`/`gbplot` use, not from a live `stream_out` run.
