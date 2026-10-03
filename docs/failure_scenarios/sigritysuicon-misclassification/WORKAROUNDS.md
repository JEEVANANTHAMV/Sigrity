# Workarounds: `SigritySuiteCon.exe` Misclassification

## Resolution (doc correction only — `verified_workaround: N/A`)

There is **no in-suite workaround or code change** because there is **no behavioral defect to work around**: `SigritySuiteCon.exe` was never wrapped, and the corrected nature (gtest binary, not a GUI shell) does not unblock any automation. The "fix" is the **documentation correction** itself, already landed:

- `sigrity_mcp/domains/platform/__init__.py:9-14` — the "CORRECTED FINDING" note now states the binary is a confirmed `gtest` executable and remains correctly unwrapped, for a now-confirmed reason.
- `README.md:712-714` — live-validation finding #8 records the same correction.

Manifest row 109 marks this `verified_workaround: N/A (doc correction only)`, and `tool_bug_fixed` reflects that the *error* (misclassification) is corrected in the docs.

## The "workaround" that matters: the method, not a code fix

The real, transferable mitigation is a **research-discipline rule**, documented in the project's own findings:

1. **Do not classify a binary from its name.** "SuiteCon" → "console/GUI shell" was the wrong guess. Run the binary's real `-h`/`--help`/`-help` and read the *actual* flag surface first. (For `SigritySuiteCon.exe`, `-h` yielded `--gtest_list_tests`, `--gtest_filter` — the tell-tale sign of `gtest`.)
2. **Treat every "no automation surface" / "GUI-only" / "unavailable" conclusion as only as strong as the search that produced it** (README:715-723). A re-probe with a differently-worded search or a live `-h` can overturn it — this is exactly what happened to `SigritySuiteCon.exe` and to three other "no surface" conclusions in the same pass (`auto_route`/SPECCTRA, `axlCNS*` scripting, `psp_cmd.exe`).
3. **Keep the corrected note where the old wrong note was** so the correction is discoverable in place (the "CORRECTED FINDING" prefix in `platform/__init__.py`).

## Workarounds / mitigations (with outcomes)

| # | Item | Outcome | Evidence |
|---|------|---------|----------|
| 1 | (original) classify `SigritySuiteCon.exe` as a Chromium GUI shell | **wrong** — name-guess with no live probe | platform/__init__.py:12-13 ("an earlier pass ... guessed") |
| 2 | **Re-probe `SigritySuiteCon.exe -h` live** | **corrected** — confirms it is a `gtest` binary (`--gtest_*` flags) | platform/__init__.py:9-11; README:712-714 |
| 3 | Wrap it as a GUI/console tool | **still correct NOT to wrap** — it is a test binary, not an automation surface | platform/__init__.py:13-14 ("remains correctly unwrapped") |
| 4 | Apply the "live `-h` re-probe / re-search" discipline to future "no surface" calls | **prevents recurrence** of this class of misclassification | README:715-723 |

## Prevention

1. Before asserting a binary is "GUI-only," "unavailable," or "no automation surface," **capture its real `-h`/`--help` output** in the research note (not just a guess from the name).
2. When a later probe contradicts an earlier note, **mark it "CORRECTED FINDING"** in the same file/location so the old wrong claim doesn't linger (as done in `platform/__init__.py` and README finding #8).
3. Periodically **re-search for automation surfaces with differently-worded queries** — the project found multiple overturned "no surface" conclusions this exact way (README:715-723).

## Remaining Gaps

A doc-only gap with no runtime consequence. The binary remains correctly unwrapped; the only residual risk is a *future* reader overlooking the correction and re-adopting the old "GUI shell" guess — which is why the "CORRECTED FINDING" prefix and the README cross-reference exist. No in-suite code, no flag, and no tool depend on `SigritySuiteCon.exe`, so there is nothing further to fix.