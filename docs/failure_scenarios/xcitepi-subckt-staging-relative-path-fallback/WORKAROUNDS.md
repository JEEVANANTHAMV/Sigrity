# Workarounds — xcitepi-subckt-staging-relative-path-fallback

## verified_workaround (from SCENARIOS.md index): "co-locate all inputs"

Stage the subckt file into the **same directory** as the tech file, all four inputs, before launching:

```
copy_file(source_file="...\xcitepi\demo_decap.gds",            ".../xcitepi_smoke/demo_decap.gds",            overwrite=true)
copy_file(source_file="...\xcitepi\demo1.map",                 ".../xcitepi_smoke/demo1.map",                 overwrite=true)
copy_file(source_file="...\xcitepi\demo1_pme_ckt.tech",        ".../xcitepi_smoke/demo1_pme_ckt.tech",        overwrite=true)
copy_file(source_file="...\xcitepi\demo1_pme_circuit_def.txt", ".../xcitepi_smoke/demo1_pme_circuit_def.txt", overwrite=true)
```

Then launch `start_xcitepi_session(tech_file=".../xcitepi_smoke/demo1_pme_ckt.tech")` and `xcitepi_open_layout(...)` from that same directory — so the tech file's CWD-relative `.include` resolves its sibling subckt without an absolute path.

### Key points
- Co-locate EVERY input the tech file references (`.include` subckt, circuit-def, etc.), not just the main four. Any file a tech line resolves CWD-relative must be a sibling.
- This is a staging fix, not a code fix — the wrapper (`xcitepi_tools.py`) only transports the tech file path; it does not rewrite `.include` targets in the tech file. You cannot "fix" it in the wrapper without editing Cadence's tech file, which the project scope forbids.

## Do NOT

- Do not pass only the tech file's original path and expect its `.include`s to resolve against the tech file's own directory — they resolve against the job CWD.
- Do not read a clean `state:"succeeded"` + rc 0 and stop: with this failure the engine can exit 0 while having placed **zero circuit** — verify by reading the produced netlist / placement counts, not the exit code.
