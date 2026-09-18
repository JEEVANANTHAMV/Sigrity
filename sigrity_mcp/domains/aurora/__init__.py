"""Domain 4 — In-Design Analysis (Sigrity Aurora), honestly scoped.

UPDATED FINDING: Allegro/OrCAD (SPB 22.1) *is* installed on this machine after all, at
C:\\Cadence\\SPB_22.1 — a separate, sibling Cadence product line from the Sigrity Suite
that an earlier pass of this research missed. This does NOT change the conclusion below,
but it does replace the evidence for it. Direct research against the real Allegro/OrCAD
doc set (`doc/sigrity_aurora`, `doc/algroroute/chap13.html`) confirmed Aurora is a real,
license-gated MODE inside `allegro.exe` itself (selected at its GUI product-chooser
dialog, then driven entirely through `Analyze -> Workflow Manager`), performing six
checks — impedance, coupling, crosstalk, return path, reflection, IR drop — each writing
its own proprietary result-file extension (`.impida`, `.cplida`, `.xtalkida`, `.rpida`,
`.rfltida`, `.irida`). Critically: **zero CLI or SKILL automation surface exists for any
of these six checks** — every workflow is menu/dialog-driven only (net-selection dialogs,
per-workflow Analysis Options dialogs, a "Start Analysis" button), confirmed by grepping
the entire SKILL function/narrative reference on disk for "aurora"/"workflow manager"
and finding nothing. A prior "constraint-driven, uses scenario files" characterization
was also checked directly against the docs and found to be unsupported — there is no
scenario file format or SKILL API for defining Aurora setups; drop that claim.

One dead end worth recording so it isn't rediscovered: `C:\\Cadence\\SPB_22.1\\tools\\bin\\
aurora.exe` looks promising by name but is a same-name-different-product false lead — a
596 KB launcher for Allegro Design Workbench (a PDM/design-collaboration tool, config
folder `tools/pcbdw/configs/aurora/`), not the SI/PI analysis feature at all.
`allegrosigritypi.exe`/`allegrosigritysi.exe` are also confirmed to be plain GUI
product-launchers into Allegro (pre-selecting a Sigrity PI/SI license tier before the
editor opens), not independently batch-scriptable — no `-b`/`-tcl`-style flags exist for
either anywhere in the docs.

Bottom line unchanged: building tools that claim to launch, configure, or query live
Aurora sessions would be fabricating a capability this environment cannot provide, now
confirmed by direct evidence rather than absence-of-files inference. This domain
provides one honest scope-notice tool and one practical bridge: a mapping from the
checks Aurora performs in-design to the closest equivalent standalone tool already
implemented elsewhere in this suite (Domain 1/2/3), so a caller who reaches for "Aurora"
still finds the right pre/post-layout tool instead of a dead end.
"""

from sigrity_mcp.domains.aurora import scope_tools  # noqa: F401
