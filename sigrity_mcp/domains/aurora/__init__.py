"""Domain 4 — In-Design Analysis (Sigrity Aurora), honestly scoped.

Research finding (confirmed via this machine's own install manifest, which lists
"Allegro Sigrity SI and PI Products\\Sigrity Aurora" as a *licensed product bundle name*
with zero corresponding files anywhere under C:\\Cadence\\Sigrity2024.0, plus Cadence's
own installation-guide text: "You can run the Sigrity Aurora ... flows from the Cadence
OrCAD and Allegro 22.10 base or later release"): Aurora is not a standalone Sigrity
Suite tool. It is a real-time, in-layout SI/PI/power-aware checking flow that runs
*inside* Allegro/OrCAD X PCB Editor, using Sigrity's simulation engines as a linked
library — it has no independent executable, and no Allegro/OrCAD install exists on
this machine. No publicly documented SKILL or Tcl automation surface for Aurora itself
was found either (Cadence may document one behind an authenticated support portal, but
that couldn't be confirmed here).

Building tools that claim to launch, configure, or query live Aurora sessions would
therefore be fabricating a capability this environment cannot provide. Instead, this
domain provides one honest scope-notice tool and one practical bridge: a mapping from
the checks Aurora performs in-design to the closest equivalent standalone tool already
implemented elsewhere in this suite (Domain 1/2/3), so a caller who reaches for
"Aurora" still finds the right pre/post-layout tool instead of a dead end.
"""

from sigrity_mcp.domains.aurora import scope_tools  # noqa: F401
