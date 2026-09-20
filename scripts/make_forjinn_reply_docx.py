"""Generate the FORJINN x LTSCT POC response as a .docx (InnoSynth voice)."""

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ACCENT = RGBColor(0x1F, 0x45, 0x7D)
HEX_ACCENT = "1F457D"
HEX_SOFT = "D9E2F3"

doc = Document()

# Base style
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(10.5)
style.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

for s in doc.sections:
    s.top_margin = Cm(1.8)
    s.bottom_margin = Cm(1.8)
    s.left_margin = Cm(2.0)
    s.right_margin = Cm(2.0)


def set_cell_bg(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def h1(text):
    p = doc.add_heading(level=1)
    r = p.add_run(text)
    r.font.color.rgb = ACCENT
    r.font.size = Pt(15)
    return p


def h2(text):
    p = doc.add_heading(level=2)
    r = p.add_run(text)
    r.font.color.rgb = ACCENT
    r.font.size = Pt(12.5)
    return p


def para(text, bold=False, size=10.5, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(size)
    return p


def bullets(items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, htext in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        r = p.add_run(htext)
        r.bold = True
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_bg(hdr[i], HEX_ACCENT)
    for ri, row in enumerate(rows):
        cells = t.rows[ri + 1].cells
        for ci, val in enumerate(row):
            cells[ci].text = ""
            p = cells[ci].paragraphs[0]
            r = p.add_run(str(val))
            r.font.size = Pt(10)
            if ri % 2 == 1:
                set_cell_bg(cells[ci], "F2F6FC")
    if widths:
        for ci, w in enumerate(widths):
            for row in t.rows:
                row.cells[ci].width = Cm(w)
    doc.add_paragraph()
    return t


# ---------------------------------------------------------------- Title
p = doc.add_paragraph()
r = p.add_run("InnoSynth  x  L&T Semiconductor Technologies (LTSCT)")
r.bold = True
r.font.size = Pt(18)
r.font.color.rgb = ACCENT

p = doc.add_paragraph()
r = p.add_run("FORJINN — PCB CAD / Schematic AI Agent")
r.bold = True
r.font.size = Pt(14)

para("POC Capability Statement & Work Plan (Response to the POC Technical Discovery Form, v1.0)",
     italic=True, size=11)

table(
    ["Document title", "FORJINN PCB CAD / Schematic AI Agent — POC Capability Statement & Work Plan"],
    [],
)
table(
    ["Field", "Value"],
    [
        ["Prepared by", "InnoSynth"],
        ["Prepared for", "L&T Semiconductor Technologies (LTSCT)"],
        ["Version", "1.1"],
        ["Date", "2026-09-20"],
        ["Responds to", "FORJINN POC Technical Discovery Form v1.0 (signed by LTSCT HW Design Lead, 12-09-2026)"],
    ],
    widths=[4.5, 12.0],
)

# ---------------------------------------------------------------- 1. Position
h1("1.  Our Position — the Study Platform is Already Built and Validated")

para(
    "Before this POC, InnoSynth built and validated a complete automation study platform "
    "against the exact same tool chain LTSCT listed in the discovery form — Cadence "
    "Allegro PCB Editor / OrCAD Capture (SPB 22.1) and Cadence Sigrity (2024.0, "
    "Aurora-class SI/PI). The platform exposes 188+ automation tools across 8 domains, "
    "driven entirely through the vendors' own automation surfaces (SKILL, Tcl, headless "
    "batch CLI). We did not prototype this during this response: the platform already "
    "exists, and our own end-to-end evaluation of it passed 12/12 representative "
    "engineering tasks on self-hosted AI inference — full-board DRC + auto-placement, "
    "schematic design database-to-power-integrity signoff, Gerber / IPC-2581 / STEP "
    "manufacturing export, and a multi-physics thermal stress signoff."
)

para(
    "What this means for the POC: LTSCT does not wait for us to learn the tools. Once "
    "the POC workstations and AI nodes are available (Section 4), we install the "
    "platform, validate it against LTSCT's own two benchmark boards, and begin "
    "engineer-facing delivery immediately. Everything below is split into what we have "
    "already done, and what we will implement on LTSCT infrastructure once the machines "
    "are provisioned."
)

# ---------------------------------------------------------------- 2. Already completed
h1("2.  What We Have Already Done (Study Phase — Complete)")

h2("2.1  Automation platform — 188+ tools, 8 domains, one deployment")

table(
    ["Domain", "What we built and validated"],
    [
        ["Power Integrity (PI)",
         "PowerDC (IR-drop), XcitePI, OptimizePI — headless batch runs with real results; board-aware extraction paths."
         ],
        ["Signal Integrity (SI)",
         "PowerSI (drives directly from a real .brd file — auto-extraction to simulation confirmed), SPDSIM, BroadbandSPICE."
         ],
        ["Extraction & Modeling",
         "Layout translators including Altium .PcbDoc and DXF ingestion (real conversions produced), Clarity 3D EM extraction, XtractIM, Touchstone de-embedding, rigid-flex 2D cross-hatch field solver."
         ],
        ["In-Design Analysis (Aurora)",
         "Aurora Workflow Manager automation for all six checks (impedance, coupling, crosstalk, return path, reflection, IR drop) via Allegro batch form replay — plus mapping of each check to the standalone high-throughput solver."
         ],
        ["CAD Creation (Allegro / OrCAD)",
         "Batch DRC and design reports; database mutation (net creation/assignment verified persisted on disk); SKILL-scripted trace / via / padstack / placement authoring; Constraint Manager scripting (~60 rule functions — spacing, physical, electrical constraint sets); full-board headless SPECCTRA autorouting (100% connected, 0 conflicts on study boards); via / pin-escape fanout routing (Z-Router) with connections control file; auto-placement engine; from-scratch board creation (DXF / IPC-2581 import / blank template); 18-layer rigid-flex stackup definitions; high-speed constraint presets (DDR4/5, PCIe Gen4/5, USB4, MIPI, 1000BASE-T); IPC-2581 / IPC-356 / ODB++-class / STEP / RS274X Gerber / drill / netlist / BOM manufacturing exports; PSpice batch simulation; schematic checklist rule engine (decoupling, pull-up/down, floating clocks, reset, test points); requirement-to-schematic authoring chain; manufacturing-package structural validation."
         ],
        ["Thermal (Celsius)",
         "Celsius3D electrothermal / stress, CelsiusCFD, Celsius2D — real displacement / strain / stress results produced."
         ],
        ["Component Sourcing & Policy",
         "Single tool querying DigiKey, Mouser, Farnell/element14, Arrow and Avnet concurrently for stock, lead time, price, lifecycle and alternates — matching the supplier list in the LTSCT form — plus a configurable vendor-preference / AVL policy engine with BOM compliance scoring."
         ],
        ["Platform / Enterprise",
         "FlexNet license diagnostics (per-feature, live), install introspection, model-library tools, SharePoint and network-drive sync for designs and component libraries, declarative multi-step pipeline orchestrator, job monitoring (status / logs / cancel), stale-lock and session health handling, AI revision watermarking, change-comparison impact reports, and engineering sign-off (approval) gates."
         ],
    ],
    widths=[4.2, 12.3],
)

h2("2.2  FORJINN-form capabilities — built ahead of the POC")

table(
    ["LTSCT capability (form priority #)", "Status in our study platform"],
    [
        ["1. Requirement-to-schematic creation",
         "Schematic authoring chain (part/wire/pin placement, annotate, netlist, save) + project creation from template + PSpice batch simulation — built; runs against LTSCT boards once machines are available."
         ],
        ["2. Schematic review & validation",
         "Design-rule / ERC checks driven from Capture's own rule matrix; design reports and BOM parsing — built."
         ],
        ["3. Schematic checklist verification (user-defined rules)",
         "Rule engine over real net/BOM data (decoupling, pull-up/down, clocks, reset, test points) — built, unit-tested against real report output."
         ],
        ["4. Component / BOM recommendation",
         "5-distributor live lookup (stock/lead time/price/lifecycle/alternates) — built; needs LTSCT API credentials to activate on their network."
         ],
        ["5. BOM checklist verification (user-defined rules)",
         "Vendor-preference / AVL policy engine with BOM compliance scoring — built."
         ],
        ["6. Documentation intelligence (read & correlate docs)",
         "Self-hosted retrieval over PDF / DOCX / XLSX / PPTX / CSV / HTML / images; SharePoint & network-drive sync — built."
         ],
        ["7. Design document generation (HDD, reports, etc.)",
         "Hardware Design Document, architecture / interface descriptions, BOM summaries, design review reports, requirement-to-design traceability matrix — auto-generated — built."
         ],
        ["8. Test plan creation",
         "Validation & bring-up test plan generation from requirements / schematics / interfaces / power architecture — built."
         ],
        ["9. User guide creation",
         "Board user guide generation (setup, connectors, interfaces, power, jumpers, test points, troubleshooting) — built."
         ],
        ["10. DRC/ERC & constraint checking",
         "Batch DRC, constraint validation, checklist compliance — confirmed live on real boards."
         ],
        ["11. Placement & routing assistance",
         "Auto-placement + full-board autorouting + Z-Router fanout + constraint-driven rules — confirmed (100% connected on study boards)."
         ],
        ["12. Gerber / manufacturing package analysis",
         "Gerber / IPC-2581 / IPC-356 / STEP / drill generation + structural validation of every artifact — confirmed live."
         ],
    ],
    widths=[6.2, 10.3],
)

h2("2.3  Evaluation evidence — 12/12 end-to-end tasks passed")

para(
    "We evaluated the platform by running realistic engineering tasks driven by "
    "self-hosted AI models (two separate inference nodes on an internal LAN, no "
    "external internet) against the full tool suite. All twelve task-and-endpoint runs "
    "reached a verified final answer:"
)

table(
    ["Task (as executed by the AI agent)", "Result"],
    [
        ["Schematic DB / .brd → PowerSI power-integrity signoff (end to end)", "OK, 92–227 s, 0 errors"],
        ["Allegro design report + design-integrity check on a real board", "OK, 26–89 s, 0 errors"],
        ["In-design analysis scope + solver recommendations", "OK, 25–81 s, 0 errors"],
        ["Batch DRC + auto-placement on a real board (incl. honest reporting of a genuine board issue)", "OK, 21–82 s, 0 errors"],
        ["Manufacturing export (IPC-2581 + STEP) + IBIS model check", "OK, 63–117 s, 0 errors"],
        ["Full Celsius3D electrothermal / stress signoff", "OK, 662–784 s, 0 errors"],
    ],
    widths=[10.5, 6.0],
)

para(
    "The same evaluation demonstrated the operating behaviour LTSCT requires in "
    "Section 5.2 of the form: the agent runs only on customer-controlled "
    "infrastructure, reports honest tool outcomes rather than fabricating success, and "
    "leaves a full audit trail of every run (prompt, tool calls, results, time)."
)

# ---------------------------------------------------------------- 3. What we will implement
h1("3.  What We Will Implement on LTSCT Infrastructure")

para(
    "These are the remaining implementation steps. They require no new development — "
    "they are deployment, configuration, and the first runs on LTSCT's own boards and "
    "documents. We will execute them as soon as the machines in Section 4 are available:"
)

table(
    ["#", "Implementation item", "Blocked on"],
    [
        ["W1", "Install & validate the tool platform on LTSCT Windows 10 workstations against LTSCT's installed Allegro 22.1 / Sigrity 24.1; run the 12-task evaluation suite on LTSCT infrastructure as the green baseline", "Workstations + license reachability (form 2.2)"],
        ["W2", "Wire the self-hosted AI model nodes (per the deployment option confirmed in Section 5) to the agent service", "AI node provisioning (Section 5)"],
        ["W3", "Ingest LTSCT's two benchmark boards (.dsn / .brd) + reference documents into the design index, component knowledge base, and retrieval index; wire SharePoint / network-drive sync", "LTSCT data drop (Section 4)"],
        ["W4", "Measure LTSCT's current baseline: manual schematic creation / review timing per engineer, on the benchmark module — the number the POC success criteria are measured against", "2 POC users"],
        ["W5", "Configure LTSCT's design-rule values (trace / clearance, via / annular ring, differential-pair impedance, copper weight) and internal standards into the constraint + checklist rule engines (Section 4.2 of the form, currently blank)", "LTSCT rule documentation"],
        ["W6", "Activate supplier-portal credentials (DigiKey / Mouser / Farnell / Arrow / Avnet) and load the project's preferred-vendor / AVL policy", "LTSCT API keys + InfoSec egress sign-off"],
        ["W7", "Stand up the approval gateway (human sign-off roles, AI-revision tags, audit logging, retention values per LTSCT IT policy)", "LTSCT IT sign-off (Section 5, items 3–5)"],
        ["W8", "End-to-end POC delivery on both benchmark boards, per the timeline in Section 6", "All of the above"],
    ],
    widths=[1.2, 11.0, 4.3],
)

# ---------------------------------------------------------------- 4. POC inputs
h1("4.  POC Inputs We Need from LTSCT (Week-1 checklist)")

bullets([
    "Workstation pool — see Section 4.1 minimum specification.",
    "Native .dsn / .brd of the two benchmark boards (FRDM-IMX91 class) plus 3–5 reference designs if available (simple to complex).",
    "Reference documents: datasheets, reference manuals, errata, application notes, HRS / PRD, board & SI/PI design guidelines, DFM/DFA checklists, AVL.",
    "Design-rule values from Section 4.2 of the form (currently blank) — or the internal PCB layout guideline document containing them.",
    "Supplier API credentials (DigiKey / Mouser / Farnell / Arrow / Avnet) and the InfoSec-approved egress allow-list.",
    "SSO / identity details (protocol and service account) for the two POC users.",
    "Log-retention values per LTSCT IT / security policy.",
])

h2("4.1  Workstation & compute specification (minimum)")

table(
    ["Resource", "Minimum for 2-user POC", "Purpose"],
    [
        ["Windows 10 workstations", "1–2",
         "Run the Cadence study / test environment (Allegro PCB Editor + Sigrity 24.1, enterprise FlexNet licenses — named or floating as LTSCT holds; reachability to the license server is already confirmed in form 2.2). The FORJINN platform runs as a local service on these same hosts and checks out floating seats the same way the engineers' interactive tools do — no additional EDA seats required."
         ],
        ["AI inference node", "1 GPU server (≈80 GB-class VRAM, e.g. one 100+ GB GPU or two 48–80 GB GPUs; 32-GB-class minimum acceptable with a smaller model)",
         "Self-hosted LLM serving the agent core. Our own 12/12 evaluation ran at comparable scale (OpenAI-compatible service, e.g. a ~30–40B-class model); if LTSCT compute is more limited, we adapt the model size down — the evaluation proves the pipeline at that class."
         ],
        ["Storage", "≈1–2 TB shared storage", "Designs, libraries, reference documents, agent run outputs, audit logs."],
        ["Network", "Internal LAN (workstations ↔ license server ↔ storage ↔ AI node); egress only to the approved supplier / technical-document allow-list", "Per Section 6 of the form."],
        ["Microsoft Excel", "On the tool workstation", "Required by one library-generation path (confirmed in the study)."],
    ],
    widths=[3.2, 4.0, 9.3],
)

# ---------------------------------------------------------------- 5. AI model deployment
h1("5.  AI Model Deployment — Option for Joint Decision")

para(
    "All design data must remain in the LTSCT-controlled environment (form 6.1–6.2), "
    "so FORJINN is architected with no external AI dependency. The study evaluation "
    "itself already ran on self-hosted inference nodes on an internal LAN — the "
    "self-hosted path is a configuration we operate, not a proposal. Three options for "
    "LTSCT to choose from:"
)

table(
    ["Option", "Description", "Trade-off"],
    [
        ["A — Fully on-prem (preferred)",
         "GPU server(s) in the LTSCT data center serving an OpenAI-compatible inference service (vLLM-class) with open-weight models (70B-class for reasoning + a smaller fast model); agent core, retrieval index and tool platform on LTSCT servers / workstations alongside.",
         "Zero data leaves premises end-to-end. Lead time depends only on GPU availability within the 8–16 week window."
         ],
        ["B — LTSCT private cloud",
         "Identical architecture hosted in LTSCT's own private-cloud tenancy rather than bare metal.",
         "Fastest ramp if private-cloud GPU capacity already exists; fully LTSCT-controlled."
         ],
        ["C — Hybrid: on-prem agents, managed models",
         "Agent core, tools and all design data on-prem; LLM inference on LTSCT-approved managed infrastructure that never sees design databases (prompts limited to redacted, non-proprietary content only).",
         "Falls back only if GPU procurement exceeds the POC window; requires InfoSec approval and a data-classification review of prompt traffic."
         ],
    ],
    widths=[3.4, 8.1, 5.0],
)

para("Open items for LTSCT IT / InfoSec at POC kickoff:", bold=True)
bullets([
    "Option choice (A / B / C) and GPU availability status; if procurement is needed, confirm it fits the 8–16 week window.",
    "Model selection sign-off: we nominate candidate weights/versions with measured quality data from the 12/12 evaluation as evidence; LTSCT approves.",
    "No-training commitment: foundation models will not be trained on LTSCT design data (written into the deployment config; verification available to LTSCT).",
    "Log / audit retention period and role-based log access — configurable in the platform; LTSCT sets the values.",
    "SSO protocol for the two POC users + service account (Entra ID / SAML / LDAP) — the form carried this as an open question; fallback is local domain accounts.",
    "Egress allow-list: the five supplier domains + public datasheet/errata domains for InfoSec approval. Outbound traffic is limited to part-number lookups — design data never transits.",
])

# ---------------------------------------------------------------- 6. Timeline
h1("6.  Proposed POC Timeline — 6.5 Weeks (fits the 8–16 week window)")

para(
    "We propose a 6.5-week plan, deliberately sequenced so the first engineer-facing "
    "value (baseline + first agent review report) lands in Week 2, leaving more than "
    "three weeks of buffer inside LTSCT's stated 8–16 week window for board-specific "
    "hardening and a second design pass. Phase entry starts on Day 1 of machine "
    "availability — the clock below begins when Section 4 inputs arrive."
)

table(
    ["Week", "Phase", "What we do (InnoSynth)", "LTSCT involvement", "Gate / exit criteria"],
    [
        ["1", "Deployment & enablement",
         "Platform install on LTSCT workstations; validate against LTSCT's Allegro / Sigrity; AI node wiring; run the 12-task evaluation suite on LTSCT infrastructure; stand up approval gateway & audit logging.",
         "IT: machines, licenses, network, credentials per Sections 4–5. InfoSec: egress allow-list, retention values.",
         "12/12 evaluation green on LTSCT infra; 2 users signed in via SSO."
         ],
        ["2", "Baseline, data ingestion & first review",
         "Ingest the two benchmark boards + reference documents; index component libraries / knowledge base; measure the manual baseline cycle (schematic creation + review time, per engineer); agent dry-run: requirement extraction + full DRC/ERC + first design review report.",
         "HW Design Lead: confirm boards, rule values, baseline timing method. 2 users: provide baseline timing.",
         "Baseline timing captured; first agent review report signed off by the Lead as 'valid format'."
         ],
        ["3", "Requirement-to-schematic (board 1 module)",
         "Agent generates architecture proposal, power tree, preliminary BOM and a draft schematic for the benchmark module of board 1; requirement-to-schematic traceability matrix.",
         "HW Architect + Design Engineer: review architecture, power strategy, component selection (per the form's review cycle).",
         "Draft schematic + traceability matrix accepted for engineering refinement."
         ],
        ["4", "Schematic validation & checklist (board 1)",
         "Full schematic review pass: ERC / design rules (LTSCT baseline), checklist verification, BOM validation with live sourcing data + vendor policy; findings report with recommendations.",
         "Design Engineers: engineering corrections in Capture; approval gateway records each approved AI change (AI revision tag).",
         "100% of seeded known issues flagged; zero unflagged critical errors (LTSCT's critical-error list enforced as a release gate)."
         ],
        ["5", "Board implementation & SI/PI/thermal signoff",
         "Placement + Z-Router fanout + full-board autorouting on the benchmark board; constraint application (high-speed presets + LTSCT internal rules); Aurora in-design checks + PowerDC / PowerSI / Celsius signoff runs on the routed board; what-if variants (trace width / dielectric) for SI tuning.",
         "Validation / System team: interface coverage and testability review.",
         "DRC-clean routed board; PI/SI/thermal reports complete."
         ],
        ["6", "Manufacturing package, documentation & revision comparison",
         "Full manufacturing package generation + structural validation (Gerber / IPC-2581 / ODB++-class / drill / BOM / pick-and-place); HDD, test plan, user guide, design review report; revision comparison study design vs. AI-assisted design.",
         "HW Design Lead: final review; both POC users sign off on the artifact set.",
         "Complete artifact set delivered for both boards (or both modules, per the plan agreed in Week 2)."
         ],
        ["7 (buffer 0.5)", "Readout & rollout plan",
         "Success-criteria readout vs. Section 7 targets; operations runbook (job monitoring, log tailing, retry/cancel, license diagnostics); second-team rollout plan (board family, users, success bar).",
         "LTSCT stakeholders: POC review and rollout decision.",
         "Signed POC outcome report; rollout decision."
         ],
    ],
    widths=[1.6, 2.6, 5.6, 3.6, 3.4],
)

para(
    "Contingency: if the LTSCT board set is more complex than FRDM-IMX91-class, the "
    "buffer absorbs it; if machines arrive late, Weeks 1–2 compress in parallel — the "
    "platform install and data ingestion run concurrently once the machines exist. The "
    "plan holds inside 8 weeks even if onboarding starts Week 3 of the POC window."
)

# ---------------------------------------------------------------- 7. Success
h1("7.  Success Criteria & Rollout Readiness (for joint signature)")

h2("7.1  Proposed success bar — jointly measured at the Week-7 readout")

table(
    ["Measure", "Target"],
    [
        ["Requirement-to-schematic (board 1 module)",
         "≥ 90% connectivity accuracy vs. the engineered reference; all checklist items pass; traceability matrix complete."
         ],
        ["Schematic review",
         "100% of seeded known defects found by the agent (LTSCT to seed 10–15 defects across the two boards); ≤ 5 false positives per full review."
         ],
        ["DRC / ERC & rules",
         "100% of LTSCT-rule violations flagged; zero items from LTSCT's critical-error list pass the release gate unflagged (verified in a seeded test)."
         ],
        ["Placement / routing",
         "Agent-assisted board reaches the engineering baseline's connectivity outcome with a DRC-clean final package."
         ],
        ["Manufacturing package",
         "Complete and structurally validated (Gerber / IPC-2581 / drill / BOM / pick-and-place), generated end-to-end by the agent flow."
         ],
        ["Time improvement",
         "Schematic creation / review cycle time reduced ≥ 30% vs. the Week-2 measured baseline; HDD / test plan / user guide delivered as drafts."
         ],
        ["Operations & audit",
         "100% of agent runs complete with full audit trail (revisions, approvals, rationale); 100% of gated actions show approval records; zero design-data egress events observed by InfoSec."
         ],
    ],
    widths=[4.6, 11.9],
)

para(
    "Clear failure: a seeded critical error reaches the release gate unflagged; an "
    "AI-modified design is applied without an approval record; design data observed "
    "leaving LTSCT premises; or requirement-to-schematic connectivity below 70%.",
    italic=True,
)

h2("7.2  What must be true for LTSCT to roll FORJINN out to other teams")

table(
    ["Dimension", "Condition"],
    [
        ["Technical",
         "All 7.1 metrics met on the benchmark boards; ≥ 2 users x 4+ weeks of operational history with zero unflagged-critical failures; documented operations runbook (job monitoring, log inspection, retry/cancel, license diagnostics, session-health handling — all features of the platform, proven in the study evaluation); a full audit/recovery exercise demonstrated live."
         ],
        ["Organizational",
         "Named agent owner inside HW Design; approval-gate roles (Lead / Engineer / Validation, per the form's review cycle) chartered; IT sign-offs closed (SSO model, egress allow-list, retention values, model deployment option — Section 5 items); vendor-policy / AVL rules loaded from LTSCT project data; a second-team pilot plan scoped (board family, users, success bar)."
         ],
    ],
    widths=[3.2, 13.3],
)

para(
    "Because the platform is config-driven (per-project rules, per-project vendor "
    "policy, per-team approval roles), extension to a second team is configuration, not "
    "re-architecture."
)

# ---------------------------------------------------------------- 8. Signoff
h1("8.  Sign-off")

para(
    "This document is a POC scoping input, not a contractual commitment. Items "
    "requiring LTSCT confirmation are explicitly marked in Sections 4, 5 and 7: "
    "workstation/GPU provisioning, the AI deployment option, SSO and egress details, "
    "benchmark board selection, the design-rule values, and the seeded-defect set."
)

table(
    ["LTSCT", "Role", "Signature", "Date"],
    [
        ["", "Technical Owner — HW Design Lead", "", ""],
        ["", "IT / Infrastructure Owner", "", ""],
        ["", "InfoSec / Cybersecurity Contact", "", ""],
    ],
    widths=[3.0, 6.5, 3.5, 3.5],
)
table(
    ["InnoSynth", "Role", "Signature", "Date"],
    [["", "Project Owner", "", ""]],
    widths=[3.0, 6.5, 3.5, 3.5],
)

out = "/root/Sigrity/FORJINN_LTSCT_POC_Response.docx"
doc.save(out)
print("saved:", out)
