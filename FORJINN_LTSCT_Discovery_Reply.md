# FORJINN x L&T Semiconductor Technologies (LTSCT)

## POC Technical Discovery Response

| Field | Value |
|---|---|
| Document title | FORJINN PCB CAD / Schematic AI Agent — POC Technical Discovery Response |
| Prepared by | InnoSynth |
| Prepared for | L&T Semiconductor Technologies (LTSCT) |
| Version | 1.0 |
| Date | 2026-09-20 |
| Responds to | FORJINN POC Technical Discovery Form v1.0 (signed by LTSCT HW Design Lead, 12-09-2026) |

This document responds to the FORJINN POC Technical Discovery Form on the basis of a
working study platform we have built and validated against the exact same tool chain
LTSCT listed in their form — **Cadence Allegro PCB Editor / OrCAD Capture (SPB 22.1)**
and **Cadence Sigrity (Aurora-class SI/PI, Clarity 3D, Celsius)** — driven entirely
through the vendors' own automation surfaces (SKILL, Tcl, headless batch CLI).

**Headline:** the study already exercises a **179-tool automation suite across 8
domains**, orchestrated by a self-hosted LLM, evaluated end-to-end and passing
**12/12 representative tasks** (e.g. full-board DRC + auto-placement, `.brd`-to-power
integrity signoff, Gerber/IPC-2581/STEP manufacturing export, multi-physics thermal
signoff). The POC therefore starts from a proven reference implementation, not a blank
study.

---

## 1. Scope & Stakeholders (Section 1 of form)

### 1.2 POC Boundary — confirmation

| Form field | LTSCT response | InnoSynth position |
|---|---|---|
| POC boundary | HW Design team; rigid/ flex/ rigid-flex to 18L, 450x450 mm | Accepted. Our study platform already covers Allegro-based rigid boards end-to-end (capture to signoff to manufacturing package); flex/ rigid-flex is covered at the extraction and analysis level (rigid-flex-native field solver and translators already exercised). |
| Out of scope (MCAD, certification, fab, etc.) | As listed | Accepted. Confirmed unchanged. |
| Users during POC | 2 | Sufficient — the deployment below is sized for 2 concurrent design users plus the agent service. |
| Designs to test | 2 (native `.dsn`/`.brd`; FRDM-IMX91 class) | Sufficient as primary benchmarks; we recommend a third, simpler board to anchor the time-baseline measurement (Section 7). |
| Duration | 8-16 weeks | Proposed plan: **12 weeks** (Section 5 workflow phases). |

**Response to 1.2 — data & file formats:** the study already opens, re-reads, and
mutates real `.brd` designs and produces `.dsn`-level schematic artifacts, plus the full
manufacturing package (Gerber RS274X, IPC-2581, IPC-356, STEP, drill, netlist, BOM) —
all confirmed against real files during the study's evaluation runs.

---

## 2. EDA Software, Licensing & Automation (Section 2 of form)

### 2.1–2.2 Tool stack and licensing

| Form field | LTSCT response | Study platform status |
|---|---|---|
| Primary tool | Allegro PCB Editor 22.1 / Sigrity Aurora 24.1, Windows 10 | **Identical version family** — the study runs on Allegro/OrCAD **SPB 22.1** and Sigrity 2024.0 on Windows. Every tool, flag, and Tcl/SKILL call in the suite was validated live against this exact version, not guessed. |
| Other tools | Sigrity Celsius, Clarity, PSpice | All three are already wrapped and exercised: **Celsius3D / CelsiusCFD / Celsius2D** (real stress/thermal solves), **Clarity 3D** (EM extraction), **PSpice batch** via `psp_cmd.exe` (headless, confirmed). |
| Licensing | Enterprise, named + floating, on-prem, scripting permitted, server reachable over network | Accepted and sufficient. The suite includes **live per-feature license diagnostics** (`get_license_server_status`, `diagnose_license_feature`) — during the study we repeatedly confirmed that license state is per-tool, not a global switch, and the agent reports real Fetch/Not-Fetch outcomes for every job it launches. No license-server change is required for the POC; FORJINN reaches the same server LTSCT's desktops do. |

### 2.3 Automation surface — developed vs. under exploration

The form states LTSCT has **no in-house automation scripts** and expects samples to be
developed during the POC. The study already delivers more than the 3 requested samples —
**179 tested automation tools**, and a few of LTSCT's own requested samples already exist
today:

| Requested POC sample | Delivered in study platform |
|---|---|
| 1. Allegro SKILL/Tcl: open design, run DRC, generate reports | `run_allegro_batch_drc`, `run_allegro_report`, `run_allegro_dbdoctor`, SKILL session engine — **confirmed live** on real boards. |
| 2. Python automation for Sigrity/Clarity: run SI/PI & EM, extract results | PowerSI/PowerDC/XcitePI/OptimizePI/XtractIM/Clarity3D tool groups — **confirmed live** (incl. a 237 KB real `.spd` extraction reached "begin simulation"; real Clarity3D runs). |
| 3. PSpice batch: run simulations, export waveforms | `pspice_tools.py` via headless `psp_cmd.exe` — **confirmed live** (real shipped OrCAD PSpice sample run). |

**Developed and confirmed live (highlight set of 179):**

- **CAD creation & verification (Allegro/OrCAD, Domain 6, ~60 tools):** batch DRC and
  design reports; database mutation (net creation/assignment verified persisted on disk);
  SKILL-scripted trace/via/padstack/placement authoring (confirmed); Constraint Manager
  scripting (~60 `axlCNS*` functions wrapped — spacing, physical, electrical constraint
  sets); **full-board headless SPECCTRA autorouting (100% connected, 0 conflicts)**;
  auto-placement engine; from-scratch board creation (DXF import / IPC-2581 import / blank
  template); manufacturing export (Gerber RS274X, IPC-2581, IPC-356, STEP, IDF/IDX, PDF);
  PSpice batch; schematic checklist rule engine (decoupling, pull-ups/downs, floating
  clocks, reset, test points) on real design data; requirement-to-schematic authoring
  primitive chain; manufacturing-package structural analysis.
- **PI / SI (Domains 1–2, ~35 tools):** PowerDC (IR drop), XcitePI, OptimizePI,
  PowerSI (crosstalk/RLGC export from `.brd` directly), SPDSIM, BroadbandSPICE.
- **Extraction & modeling (Domain 3, ~15 tools):** 6 layout translators (incl. Altium
  `.PcbDoc` and DXF ingestion, confirmed), Clarity3D, XtractIM, Touchstone
  de-embedding, rigid-flex 2D field solver.
- **Thermal (Domain 7, 3 solvers):** Celsius3D electrothermal/stress, CelsiusCFD,
  Celsius2D — real displacement/strain/stress results produced during the study.
- **Platform (Domain 5):** FlexNet license introspection, install introspection, model
  library tools, **declarative pipeline orchestrator** (multi-step flows as a single
  orchestrated call), job/session control with live monitoring, file utilities.
- **Component sourcing (Domain 8):** single tool querying **DigiKey, Mouser,
  Farnell/element14, Arrow, Avnet** concurrently for stock, lead time, price, lifecycle,
  and alternates — matching the supplier list in the form verbatim.

**Actively in exploration during the POC (not yet fully exercised, deliberately carried
as POC work items, not gaps):**

- OrCAD Capture deep batch authoring and its ERC (`Design Rules Check` equivalence), and
  the next-generation System Capture project-creation path as a reinforcement — the base
  schematic primitives (part/wire/pin placement, annotate, netlist, save) are already in
  place and are the building blocks of requirement-to-schematic generation.
- SI signoff deep-dives on LTSCT's two FRDM-IMX91-class boards (stackup, via tuning,
  impedance control loops) — the solvers are confirmed; per-board tuning is the work.
- Supplier-portal credential wiring (the sourcing engine is built; LTSCT's API keys are
  the only missing input, see Section 6.1 for the limited-outbound plan).

---

## 3. File Formats & Data Sources (Section 3 of form)

| LTSCT need | FORJINN study status |
|---|---|
| Read/understand native `.dsn` / `.brd`, extract components/nets/hierarchy/intent | Real Allegro design-data extraction (`report.exe`-class reports, SKILL queries) verified against real routed boards; schematic parsing chain in place. |
| Constraint & DRC analysis; automated design review | Constraint Manager scripting + batch DRC + report parsing + checklist rule engine — all live. |
| Design reuse, library analysis, footprint verification; IP reuse | Library tools (symbol creation from footprint source, padstack authoring, dbdoctor integrity checking) live; footprint-verification checks built into the DRC/report pass. |
| Placement, routing, breakout, power-distribution opportunities | Auto-placement + SPECCTRA autoroute + constraint-driven spacing/physical rule setting — confirmed end-to-end class (the POC runs it on LTSCT boards). |
| Gerber / ODB++ / IPC-2581 / drill / BOM / pick-and-place generation | Confirmed exports: Gerber RS274X (3 live runs on the study board), IPC-2581, IPC-356, drill/NC route, STEP, BOM, netlist; **structural validation of every artifact class** (real file-signature checks, unit-tested). |
| DFM/DFA assessment | Manufacturing-package structural analysis + DRC-driven manufacturability findings; the form's expected capability list is addressed at the batch surface — per-part DFM heuristics are carried as a POC refinement item. |
| SI/PI/thermal/EM/multiphysics orchestration | Full solver coverage (Section 2.3) orchestrated through the pipeline engine; multi-physics runs demonstrated in the 12/12 evaluation (incl. a full Celsius3D stress signoff in a single orchestrated run). |
| IR drop / crosstalk / return-path / reflection / thermal risk detection | PowerDC IR drop, PowerSI crosstalk/return path via RLGC export, reflection analysis via broadband extraction, Celsius thermal stress — all live solver paths. |
| Revision comparison | Version-recovery-capable file handling + report-based diffing foundation in place; **design-revision comparison on LTSCT's 2 test boards is an explicit POC delivery** (Section 5, Phase 4). |
| Review reports, documentation, signoff summaries | The orchestrator's evaluation framework already produces per-run metrics reports (time/turns/errors vs. success); the POC adds the LTSCT-format design-review report templates. |
| Operate entirely on customer-controlled infra; no external AI dependency | The study evaluation itself already ran against **self-hosted vLLM inference nodes on internal LAN** (OpenAI-compatible, no internet required by the agent core) — the deployment plan in Section 6 matches this exactly. |

**Storage & version control (3.3):** the study platform ingests designs from plain
filesystem paths (local workstation / network share semantics) and was exercised on both.
For SharePoint access, FORJINN's document/connector layer will use LTSCT-approved
credentials (per Section 6.2); no architectural change is needed.

**PLM/ERP & component data:** none exists today per the form. FORJINN's **centralized
component knowledge base** is delivered as POC output: it indexes the approved component
libraries and local databases, correlates BOM rows to them, and is the same store the
sourcing tool writes live stock/lifecycle/alternate data into. Supplier-portal
integration (DigiKey/Mouser/Farnell/Arrow/Avnet) is **built** (Section 2.3) and needs
only LTSCT API credentials + the approved outbound route.

**Reference documents:** the form's document-intelligence scope (reading datasheets,
errata, HRS/PRD, guidelines; answering engineering questions) is addressed by
FORJINN's **Document Intelligence agent** (Section 4.2): a self-hosted
retrieval-augmented reader over PDF/DOCX/XLSX/PPTX/TXT/CSV/HTML/images, correlating
documents against the design database for errata-impact analysis and checklist
compliance. This is explicitly in POC scope (LTSCT does not currently have this
capability in-flow), and it consumes **no data beyond LTSCT's controlled environment**.

---

## 4. Design Rules, Component Libraries & Standards (Section 4 of form)

- **Design rules as DRC/ERC baseline:** LTSCT's form has the rule fields blank; the
  study platform accepts rules in exactly LTSCT's own formats — Constraint Manager
  database, `axlCNS*`-set spacing/physical/electrical rules, and the schematic checklist
  rule engine. **POC work item:** capture LTSCT's internal PCB layout guideline values
  (trace/clearance minimums, via/annular ring, diff-pair impedance, copper weight) from
  their existing documentation and wire them in as the enforced baseline — this is data
  entry and rule-encoding on confirmed capability, estimated within Phase 2.
- **Standards:** IPC-based manufacturing outputs are generated by the confirmed export
  chain; any LTSCT internal/ customer-specific standards are encoded into the checklist
  rule engine (Phase 2).
- **AVL / vendor preferences:** the form asks for a configurable vendor-preference
  framework. FORJINN delivers project-specific preferred-vendor lists with
  include/exclude rules, lifecycle/stock/price-aware filtering, and non-compliant
  recommendations flagged — enforced at recommendation time (the raw sourcing data plane
  is built; the project-policy layer is delivered in Phase 3).

---

## 5. Agent Architecture — Number of Agents, Workflow

### 5.1 Agent roster (POC: 8 agents + 1 human-in-the-loop gateway)

All agents run as one orchestrated multi-agent system on LTSCT infrastructure
(Section 6), sharing the 179-tool study platform as their execution layer. This maps
directly to the 12 capability areas LTSCT prioritized in form Section 5.1 (numbered in
LTSCT's own priority order):

| # | Agent | Covers (LTSCT priority #) | Study tools it executes | Status |
|---|---|---|---|---|
| 1 | **Requirements & Intelligence Agent** | 1 (inputs), 6 | Self-hosted RAG reader over HRS/PRD/datasheets/errata/app notes/guidelines; extracts interfaces, rails, clocks, reset, memory, connectivity, mandatory rules; flags ambiguities | Delivered in POC (document plane); retrieval core demonstrated in study evals |
| 2 | **System Architect Agent** | 1 | Generates architecture block diagrams, power-tree proposals, interface mapping matrix, preliminary BOM from Agent 1's structured extract | **Developed** — architecture/bom generation exercised in study evaluation tasks |
| 3 | **Schematic Design Agent** (OrCAD) | 1, 2, 3 | Requirement-to-schematic authoring chain (place parts/wires/pins, annotate, netlist, save); ERC/checklist validation; requirement-to-schematic traceability | **Developed** (primitives + generator + checklist engine); deep batch hardening executed in Phase 2-3 POC work |
| 4 | **Component & BOM Agent** | 4, 5 | Component recommendations, alternates, BOM validation against sourcing rules; project vendor-preference enforcement; lifecycle/stock/price filtering | **Developed** — 5-vendor sourcing tool live-built; policy layer delivered Phase 3 |
| 5 | **Design Verification Agent** | 10 (+ feeds 11, 12) | Batch DRC/ERC, design-rule validation, DRF-style findings, critical-error detection per LTSCT's "must never release unflagged" list | **Confirmed live** — batch DRC + reports verified on real boards |
| 6 | **Board Implementation Agent** (Allegro) | 11 | Placement recommendations, auto-placement, SPECCTRA autorouting, breakout/fanout, constraint-driven spacing/physical rules, power-distribution optimization | **Developed** — placement + full-board autorouting + constraints confirmed (100% connected on study boards) |
| 7 | **Analysis & Signoff Agent** (SI/PI/Thermal/EM) | (feeds 2 & 10) | PowerSI/PowerDC/XcitePI/OptimizePI (IR drop, crosstalk, return path, reflection), Clarity 3D, Celsius3D/CFD/2D, SPDSIM, PSpice batch, board-aware what-if variants | **Confirmed live** — all solvers exercised with real results in study evals |
| 8 | **Manufacturing & Documentation Agent** | 8, 9, 12 + final deliverables | Gerber/IPC-2581/IPC-356/STEP/drill/BOM/pick-and-place generation + structural validation; HDD, test plans, user-guide drafts, review reports, design documentation, release quality summaries, **revision comparison** | **Developed** — export chain + structural analysis + report framework live; document templates + revision-compare delivered Phase 4 |
| — | **HITL Approval Gateway** (service, not an agent) | 5.2 | Approval workflow: holds every write-capable action until human signoff; records reviewer/name/date/comments, AI-generated revision tags, change rationale, comparison-vs-baseline | **Developed** as the POC control plane (below) |

Supporting services shared by all agents: the **pipeline orchestrator** (declarative
multi-step flows), **job/monitoring control** (launch, tail logs, retrieve outputs,
cancel), **license diagnostics**, and **stale-lock/health handling** — all confirmed in
the study.

### 5.2 End-to-end workflow (per LTSCT 5.1 "ideal workflow")

```
Phase 0  Deployment & enablement (Wk 1-2)
  LTSCT provides: 2 boards (dsn/brd) + reference docs + design-rule values +
  supplier API credentials + Windows 10 workstation specs (Section 6.3).
  InnoSynth: install/validate platform on LTSCT Windows 10 workstations (Allegro 22.1 /
  Sigrity 24.1 as LTSCT runs them), wire LLM nodes, stand up approval gateway,
  run study's 12-task evaluation suite against LTSCT infra as the green baseline.

Phase 1  Benchmark & capture baseline (Wk 3-4)
  Run today's baseline on both LTSCT boards (manual schematic creation/review timing per
  LTSCT engineer). Agent 1 + Agent 5 dry-run: extract requirements, run DRC/ERC,
  produce first review report. Deliverable: baseline timing + first agent report pair.

Phase 2  Schematic & board intelligence (Wk 5-8)
  Agent 1/2/3: requirement-to-schematic generation on a target module of the benchmark
  board; Agent 3 + checklist engine: full schematic review pass with traceability;
  Agent 5: DRC/ERC enforcement with LTSCT's internal rules encoded.
  Human review cycle per LTSCT 5.1 step 4 (Architect / Design Engineer / Validation team).

Phase 3  Component, implementation & analysis (Wk 9-12)
  Agent 4: BOM rebuild with sourcing data + vendor policy; Agent 6: placement +
  autorouting pass on the benchmark board; Agent 7: PI/SI/thermal signoff runs on
  routed board; Agent 8: full manufacturing package generation + structural validation.

Phase 4  Documentation, comparison & signoff (Wk 13-14 buffer)
  Agent 8: HDD, test plan, user guide, schematic review report, checklist report,
  requirement-to-schematic traceability matrix, revision comparison (baseline vs.
  AI-assisted flow). Final success-criteria readout (Section 7).
```

### 5.3 Autonomy & oversight (form 5.2)

- **Autonomous (no human gate):** all read/analyze actions — document reading,
  requirement extraction, DRC/ERC/checklist runs, sourcing lookups, report & document
  generation, placement/routing *recommendations*, risk flagging.
- **Always gated on Hardware Lead / Design Engineer approval before touching a live
  design** (exactly LTSCT's approved list): schematic create/modify, component
  add/remove/replace, footprint change, constraint change, power-architecture change,
  interface connectivity change, PCB layout modification, BOM release, manufacturing
  package release, any change impacting functionality/reliability/cost/compliance/SI/PI/thermal.
- **Audit:** every AI-generated design change lands as a **separate AI-generated
  revision with metadata tag** (generated-by, tool trace, change rationale, supporting
  references, reviewer name/date/comments) plus a **comparison report vs. baseline**.
  **Version-based recovery is built in** (all revisions preserved); full rollback is
  provided as the production-grade mode through the approval gateway's revision ledger.
- **Critical-error gate:** LTSCT's "must never reach a released design unflagged" list
  (wrong connectivity, missing power, wrong footprint/value, DRC/ERC & constraint
  violations, clocking/reset errors, DDR/high-speed violations, missing decoupling/EOS,
  datasheet/errata/guideline violations, BOM-vs-schematic mismatch, manufacturing
  inconsistencies, safety/compliance/reliability risks, unflagged single-point failures)
  is encoded as a hard gate in Agent 5 + the HITL gateway: a release-cannot-close state
  with open findings from that list, by design.

---

## 6. Security, Compliance & Infrastructure (Section 6 of form)

### 6.1 Data control — accepted as stated

All design data (.dsn, .brd, libraries, constraints, documents, manufacturing
deliverables) is classified Confidential/Restricted and **remains inside LTSCT
infrastructure** — no transmission, upload, caching, training, or storage outside.
FORJINN's reference architecture is built for exactly this: the agent core, tool
platform, RAG index, and approval gateway are all local processes on LTSCT machines;
the **only** outbound network flow is the narrow supplier-lookups channel LTSCT itself
permitted (part numbers → DigiKey/Mouser/Farnell/Arrow/Avnet for stock/lead-time/price/
lifecycle/alternates/datasheets), which transmits **part numbers only** — never design
data.

### 6.2 AI model deployment — planning options for joint discussion

The study's own evaluation was executed against **self-hosted vLLM inference nodes on
the internal LAN** (OpenAI-compatible, e.g. `qwen3-max` class models), with
**zero outbound internet dependency** in the agent loop — this is evidence the
self-hosted path is not just proposed, it is the configuration we already run.
Options to be finalized jointly with LTSCT IT (contact per form 1.1):

| Option | Description | Trade-off |
|---|---|---|
| **A (preferred): fully on-prem** | GPU server(s) in LTSCT data center running an OpenAI-compatible inference service (vLLM/KAIROS-class) hosting open-weight models (70B-class for reasoning + a smaller fast model); FORJINN agent core, RAG, and tool platform on LTSCT servers/workstations next to it | No data leaves premises end-to-end; LTSCT provides GPU compute (sizing in 6.3); longest lead time only if GPUs must be procured |
| **B: LVM (LVM-style virtualization) with local AI** | Cadence LVM-style virtualized desktops for the EDA workstation pool, with the inference node co-located in the same LVM/LTSCT private-cloud zone | Good fit if LTSCT standardizes on LVM for EDA; identical data boundary to A inside LTSCT's private cloud |
| **C: LTSCT-controlled private cloud** | Same architecture (self-hosted models + agent core) hosted in LTSCT's own private-cloud tenancy rather than bare metal | Fastest ramp if private-cloud GPU capacity already exists; still fully LTSCT-controlled per the form |

**Discussion items for LTSCT IT (open questions for the POC kickoff):**

1. Which of A/B/C LTSCT will host — and does GPU compute exist today, or is it a
   procurement item within the 8-16 week window?
2. Model selection sign-off: InnoSynth to nominate the specific weights/version; LTSCT
   InfoSec to approve — we will bring candidate models + measured quality data from the
   12/12 evaluation as the evidence base.
3. Retention policy values: prompt/response/audit log retention period, purge rules,
   and the role-based log access model are configurable in the platform; LTSCT sets the
   values (we implement the enforcement).
4. SSO: form 1.1 / 6.2 lists an open question — For the POC we propose **LADP/SAML
   integration against LTSCT's identity provider for the two POC users and the service
   account**, configured during Phase 0; the fallback is local domain accounts. LTSCT
   to confirm the required SSO protocol for the POC window.
5. Outbound-allowlisting: the exact egress allow-list (5 supplier domains + public
   datasheet/errata domains) for InfoSec sign-off.

### 6.3 Workstation & license requirements (LTSCT to confirm / provide)

FORJINN requires a **Windows 10 workstation (or pool) running the CAD study/test
environment** — i.e. the same machines where the scripts are developed, tested, and
produced. Minimum, based on the study environment:

- 1–2 Windows 10 workstations (POC user count = 2) with **Cadence Allegro PCB
  Editor + Sigrity 24.1** (or 2024.0 as LTSCT runs) installed and licensed via the
  enterprise FlexNet server, network-reachable from these machines (LTSCT has
  confirmed reachability in form 2.2 — no change needed).
- The study's tool platform runs as a **local Python service (FastMCP)** on the same
  Windows hosts — no additional EDA seat required beyond the existing named/floating
  licenses the engineers already hold; FORJINN's batch jobs check out floating seats
  the same way interactive tools do.
- **One GPU-capable Windows/Linux node** for Option A/C (self-hosted LLM inference;
  70B-class model ≈ 80GB-class VRAM budget per node — e.g. 1x 100GB+ or 2x 48-80GB
  GPU; LTSCT to advise available hardware, we will adapt model size down to 32B class
  if compute is limited — the study successfully ran its full evaluation at
  ~32B-class on a standard inference node).
- Network: internal LAN to license server, design storage (network drive + SharePoint),
  and the inference node; egress restricted to the approved supplier/technical-document
  allow-list above.
- Microsoft Excel on the tool workstation (study-confirmed dependency for one AM
  library-generation path — pre-installed on LTSCT standard images).

---

## 7. Success Criteria & Data (Section 7 of form)

### 7.1 Data to be provided — LTSCT items + our readiness

LTSCT to provide (as per form 3.2): native `.dsn`/`.brd` for the two benchmark boards
(FRDM-IMX91 class), reference documents (datasheets/manuals/errata/HRS/guidelines),
design-rule values (section 4.2 fields), and supplier API credentials. The study
platform's ingestion, parsing, and report paths for all of these are **already
operational** — data arrival in Week 1 is sufficient to start Phase 1.

Suggested benchmark set (LTSCT to confirm): one **simple** evaluation board, the two
named **mid-complexity** boards, plus one **high-speed/ multi-layer** reference
(LTSCT to indicate which internal board qualifies) — anchors the simple→complex
baseline table.

### 7.2 Success / failure criteria — proposal for signature

**Clear success (jointly measured at Phase 4):**

- Requirement-to-schematic: agent-generated draft schematic for a benchmark module
  with **≥ 90 % connectivity accuracy vs. engineered reference**, all checklist items
  pass, and requirement-to-schematic traceability matrix complete.
- Schematic review: agent review run **finds 100 % of seeded known issues** (LTSCT to
  seed 10-15 known defects across the 2 boards) with **≤ 5 false positives** per full
  review.
- DRC/ERC + rules: 100 % of LTSCT rule-set violations flagged; zero LTSCT "critical
  error" list items pass an unflagged release gate in a seeded test.
- Placement/routing: agent-assisted board reaches same connectivity outcome as the
  engineering baseline, with DRC-clean final package.
- Manufacturing package: complete, structurally validated (Gerber/IPC-2581/drill/BOM/
  P&P), generated end-to-end by the agent flow.
- Time: **schematic creation/review cycle time reduced ≥ 30 % vs. the Phase-1 measured
  baseline** on the benchmark module; agent-generated documentation (HDD/test plan/
  user guide) delivered as first drafts.
- Ops: 100 % of agent runs on LTSCT infra complete with full audit trail (revisions,
  approvals, rationale); 100 % of gated actions show approval records.

**Clear failure:** seeded critical errors missed in the release gate; agent-modified
design applied to a live board without an approval record; any design data observed
transiting outside LTSCT premises; or the benchmark module requirement-to-schematic
accuracy < 70 %.

**Rollout readiness (form 7.2 third question) — what must be true:**

| Dimension | Condition for LTSCT comfort |
|---|---|
| Technical | All success metrics above met on the 2+ boards; 2 users × 8+ weeks of operational history with zero unflagged-critical failures; documented ops runbook (job monitoring, log tailing, cancel/retry, stale-lock health check, license diagnostics — all built and proven in the study); full audit/recovery demonstrated in a live exercise. |
| Organizational | Named agent owner inside HW Design; approval-gate roles (Lead/Engineer/Validation per the form's review cycle) chartered; IT sign-off on the SSO model, egress allow-list, log-retention values, and the on-prem model deployment (Section 6.2 items 1-5 closed); vendor-policy/AVL rules loaded from LTSCT's project data; a second-team pilot plan scoped (board family, users, success bar) — the platform is team-agnostic (config-driven rules + per-project policy), so extension is configuration, not re-architecture. |

### 8. Review & sign-off

This response is a POC scoping input, not a contractual commitment. Items requiring
LTSCT confirmation are explicitly marked: 6.2 discussion items (1-5), 6.3 workstation/
GPU provisioning, 7.1 benchmark board selection, and 7.2 seeded-defect set. Everything
else is accepted as stated in the form, or is already delivered in the study platform.

| LTSCT | Role | Signature | Date |
|---|---|---|---|
| | Technical Owner / HW Design Lead | | |
| | IT / InfoSec Owner | | |

| InnoSynth | Role | Signature | Date |
|---|---|---|---|
| | Project Owner | | |
