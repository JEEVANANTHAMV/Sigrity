# Workarounds: Argument-Name Traps → Silent ~20-Min Hang

## Verified Workaround (in-suite)

**Source the exact argument names from the SKILL.md / tool docstrings, never guess.** Manifest row 99 marks this `verified_workaround: YES (source names from SKILL.md)`. The specific verified-correct names (from the live-tested record in SKILL.md:97-104 and `file_tools.py`):

| Trap (wrong name) | Correct name | Tool(s) |
|---|---|---|
| `source` / `destination` | `source_file` / `destination_file` | `copy_file`, `move_file` |
| `source` / `destination` | `file_path` | `delete_file` |
| `positive_net` | `positive_node` / `negative_node` | PowerSI edge-port setters |
| `"1MHz"` (unit-suffixed) | `"1e6"` (plain Hz string) | PowerSI `start`/`end` frequency sweep |
| project/design path passed *once* | must be passed again as a **second** arg on `*_run_session` | Celsius2D/3D/CFD, Clarity3D |

Source: `sigrity_mcp/domains/platform/file_tools.py:22,37,54`; `.forjinn/skills/sigrity/SKILL.md:97-104`.

## Why it is still "known_blocked"

There is **no in-suite auto-correction** for plausible-but-wrong arg names. The tools are strict in both directions: a *required* arg missing → `missing_argument` (fast), but a *wrong-named optional* arg is silently ignored and the resulting underspecified/invalid command can push the batch process into a **silent interactive-prompt hang** that only the long stall/watchdog timeout finally kills. Correcting the typo *before* the call is the only reliable avoidance, and doing that requires the caller to know the exact names in advance — which is a **documentation/learning** fix, not a runtime guard. (An "did you mean X?" fuzzy-match or an explicit "unknown arg rejected" guard would require source changes to every tool's arg handling; none is implemented.)

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Copy arg names verbatim from SKILL.md / tool docstring | **works** — avoids both the `missing_argument` and the silent-hang paths | SKILL.md:97-104; file_tools.py:22-60 |
| 2 | Guess a plausible name | **fails** — either `missing_argument` (fast, visible) or ~20-min silent hang (invisible until timeout) | SKILL.md:99 ("either raises `missing_argument` or, worse, hangs ~20 min") |
| 3 | On a hang, recover via `get_job_status` / `list_all_jobs(state="running")` + `cancel_job` | **works to bound the damage** (stops the silent stall), but does not fix the arg — you must re-issue with the correct name | SKILL.md:36-40 (rule 1 recovery); job tools table SKILL.md:57-63 |
| 4 | Rely on the pipeline's `error`-only raised-step record to catch it | **only catches the fast path** (`missing_argument`); the silent-hang path produces no step-level `error` at all | pipeline_tools.py:66-75 |

## Prevention

1. **Before writing any `run_tool_pipeline` step, look up the tool's exact argument names** in its SKILL.md section / `@mcp.tool` docstring. Do not infer names by convention (`source`, `net`, `1MHz` are all traps).
2. **For the verified traps, use the corrected forms as a checklist**: file tools → `source_file`/`destination_file`/`file_path`; PowerSI ports → `positive_node`/`negative_node`; frequencies → plain Hz (`"1e6"`); Celsius/Clarity3D `*_run_session` → pass the project/design path **again** as the second arg.
3. **Bound any run that looks like it is hanging** with `get_job_status`/`list_all_jobs(state="running")` + `cancel_job`, then re-issue with corrected args rather than letting the ~20-min stall or the MCP client round-trip cap consume the whole call.
4. Keep `stop_on_error=True` so the *fast* failure path (`missing_argument`) halts the pipeline early instead of running the remaining steps against a broken earlier step.

## Remaining Gaps

No fuzzy/`did-you-mean` arg validation, no "unexpected argument rejected" guard, and no fast-fail for the silent interactive-prompt hang — so the trap only closes if the caller *already knows* the right names. The ~20-minute silent window is bounded only externally by the MCP client's flat 30 s round-trip cap (observed) and the job stall/watchdog timeout, neither of which tells the caller *which arg was wrong*.