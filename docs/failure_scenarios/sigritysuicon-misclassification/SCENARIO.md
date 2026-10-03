# `SigritySuiteCon.exe` Misclassified as a GUI Shell — It Is a Google Test (gtest) Binary

**Slug**: `sigritysuicon-misclassification`
**Tool(s) affected**: none wrapped — this is a **documentation/classification correction** for the suite's own research note about `SigritySuiteCon.exe`. No in-suite tool depends on or wraps it.
**Status category**: `tool_bug_fixed` (per manifest row 109) — a wrong conclusion in this suite's docs, now corrected; `verified_workaround: N/A (doc correction only)`
**Pipeline stage**: platform (research/documentation accuracy — no live pipeline impact)

## Symptom

An **earlier research pass** in this project **guessed/misclassified** `SigritySuiteCon.exe` as a **Chromium-embedded GUI shell** (a "suite console" / browser-based management UI). That conclusion was carried in the platform domain's scope notes. A **later re-probe** (running `SigritySuiteCon.exe -h` live) corrected it: the binary is actually an **internal Google Test (`gtest`) binary** — its `-h` output is *literally `gtest`'s own flag reference* (`--gtest_list_tests`, `--gtest_filter`, ...), not a Chromium GUI and not a scripting console.

The "failure" here is a **research-classification error** (a wrong capability assumption), not a runtime defect. The corrected consequence is the same as before — **the binary remains correctly unwrapped** — but for a different, now-confirmed reason.

## Root Cause

The original misclassification came from **guessing from the name** ("SuiteCon" → "suite console" → assumed a GUI/console shell) without a live `-h` probe, which the project's own discipline warns against (README:715-723 lists *three* "no automation surface" conclusions that turned out wrong after a differently-worded search — "a 'not found' conclusion is only as strong as the search that produced it"). The re-probe ran the binary's real `-help`/`-h` and read the *actual* flag surface, which is `gtest`'s, revealing the true nature: it is a compiled test executable, not an automation surface at all.

## Evidence

- `sigrity_mcp/domains/platform/__init__.py:7-14` (module docstring, verbatim): "We deliberately do NOT wrap `SigritySuite.exe` / `SigritySuiteManager.exe` / `SigSuiteReg.exe`: their command-line contracts are undocumented and untested. **CORRECTED FINDING: `SigritySuiteCon.exe -h` was re-probed live and is confirmed to be an internal Google Test (gtest) binary** — its `-h` output is literally `gtest`'s own flag reference (`--gtest_list_tests`, `--gtest_filter`, ...), **not a Chromium-embedded GUI shell as an earlier pass of this research guessed**, and not a scripting console either way — so it remains correctly unwrapped, just for a different, now-confirmed reason."
- `README.md:712-714` (live-validation finding #8, verbatim): "**`SigritySuiteCon.exe` is a Google Test (`gtest`) binary**, not a Chromium-embedded GUI shell as an earlier pass of this research speculated — **corrected in `platform/__init__.py`**. Still correctly unwrapped either way."
- `README.md:715-723` (finding #9) — the broader discipline this correction exemplifies: "Three 'no automation surface' conclusions from earlier in this same research were wrong... this is the clearest evidence in this whole project that a **'not found' conclusion is only as strong as the search that produced it**."
- `sigrity_mcp/core/tool_status.py` — `SigritySuiteCon` is **not** in `TOOL_STATUS` (it is unwrapped, as the corrected note states); the absence is consistent with "correctly unwrapped, just for a different reason."

## Pipeline Impact

**None, directly.** `SigritySuiteCon.exe` is not wrapped and no pipeline step references it. The impact is purely on the *accuracy of the suite's documented scope and research conclusions*: leaving it misclassified as a "GUI shell" would (a) mislead a future integrator into probing for a GUI automation surface that does not exist, and (b) understate the project's own research-discipline point that name-guessing must be replaced by a live `-h` re-probe. The correction is a doc fix with no code or runtime change.