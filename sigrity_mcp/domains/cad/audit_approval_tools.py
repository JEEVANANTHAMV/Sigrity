"""Audit Trail, AI Revision Tagging, and Engineering Approval Sign-off Workflow.

Aligned with FORJINN Discovery Form Section 5.2 & Section 6.2:
- Tag designs with AI metadata (Agent Version, Trace ID, Timestamp, Rationale).
- Record engineering approval workflows (Reviewer Name, Role, Date, Approval Status, Comments).
- Generate design change comparison reports (AI modifications vs baseline).
- Maintain complete traceability and audit logs for hardware sign-off before release.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Literal, Optional

from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def tag_ai_design_revision(
    project_path: str,
    revision_id: str,
    agent_name: str = "FORJINN PCB AI Agent",
    agent_version: str = "1.0",
    change_summary: str = "Automated schematic/layout updates",
    source_requirements: Optional[list[str]] = None,
    output_meta_path: Optional[str] = None,
) -> dict[str, Any]:
    """Tag a PCB/schematic project with AI metadata for full auditability and revision tracking."""
    now_iso = datetime.utcnow().isoformat() + "Z"
    meta_path = output_meta_path or os.path.join(os.path.dirname(project_path) or ".", "AI_REVISION_META.json")

    meta_record = {
        "project_path": os.path.abspath(project_path),
        "ai_revision": revision_id,
        "agent_name": agent_name,
        "agent_version": agent_version,
        "timestamp_utc": now_iso,
        "change_summary": change_summary,
        "source_requirements": source_requirements or [],
        "approval_status": "PENDING_ENGINEERING_REVIEW",
        "human_reviewer": None,
        "approval_date": None,
    }

    os.makedirs(os.path.dirname(meta_path) or ".", exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_record, f, indent=2)

    return {
        "status": "success",
        "metadata_file": os.path.abspath(meta_path),
        "ai_revision": revision_id,
        "approval_status": "PENDING_ENGINEERING_REVIEW",
    }


@mcp.tool
async def record_engineering_approval(
    metadata_file_path: str,
    reviewer_name: str,
    reviewer_email: str,
    reviewer_role: Literal["Hardware Lead", "Design Engineer", "Validation Lead", "InfoSec / IT Owner"],
    decision: Literal["APPROVED", "REJECTED", "CHANGES_REQUESTED"],
    review_comments: str,
    risk_assessment: Optional[str] = None,
) -> dict[str, Any]:
    """Record a formal human engineering review decision before AI changes are released to live designs."""
    if not os.path.exists(metadata_file_path):
        raise FileNotFoundError(f"Metadata file '{metadata_file_path}' not found.")

    with open(metadata_file_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    approval_entry = {
        "reviewer_name": reviewer_name,
        "reviewer_email": reviewer_email,
        "reviewer_role": reviewer_role,
        "decision": decision,
        "review_comments": review_comments,
        "risk_assessment": risk_assessment or "Low",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    meta["approval_status"] = decision
    meta["human_reviewer"] = reviewer_name
    meta["approval_date"] = approval_entry["timestamp"]
    if "approval_history" not in meta:
        meta["approval_history"] = []
    meta["approval_history"].append(approval_entry)

    with open(metadata_file_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return {
        "status": "success",
        "approval_status": decision,
        "metadata_file": os.path.abspath(metadata_file_path),
        "latest_approval": approval_entry,
    }


@mcp.tool
async def generate_design_change_report(
    baseline_design_name: str,
    ai_modified_design_name: str,
    added_components: list[str],
    removed_components: list[str],
    modified_nets: list[str],
    constraint_changes: list[str],
    change_rationale: str,
    output_report_path: Optional[str] = None,
) -> dict[str, Any]:
    """Generate a formal markdown design change comparison report comparing AI modifications against baseline."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = output_report_path or "AI_Design_Change_Report.md"

    lines = [
        f"# AI Design Change & Impact Report",
        f"**Date:** {date_str}  ",
        f"**Baseline Design:** {baseline_design_name}  ",
        f"**AI-Modified Design:** {ai_modified_design_name}  ",
        f"**Classification:** LTSCT Confidential  ",
        "\n---\n",
        "## 1. Rationale for AI Modifications",
        f"{change_rationale.strip()}",
        "\n---\n",
        "## 2. Component Delta Summary",
        f"- **Added Components ({len(added_components)}):** {', '.join(added_components) if added_components else 'None'}",
        f"- **Removed Components ({len(removed_components)}):** {', '.join(removed_components) if removed_components else 'None'}",
        "\n---\n",
        "## 3. Net & Connectivity Changes",
        f"- **Modified / Re-assigned Nets ({len(modified_nets)}):** {', '.join(modified_nets) if modified_nets else 'None'}",
        "\n---\n",
        "## 4. Constraint & Design Rule Changes",
    ]

    if constraint_changes:
        for c in constraint_changes:
            lines.append(f"- {c}")
    else:
        lines.append("- No constraint changes.")

    lines.append("\n---\n## 5. Engineering Sign-Off Gate")
    lines.append("| Reviewer Name | Role | Decision | Signature / Date |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append("| _________________ | Hardware Lead | [ ] APPROVED / [ ] REJECTED | _________________ |")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "report_path": os.path.abspath(out_path),
        "total_added_components": len(added_components),
        "total_removed_components": len(removed_components),
        "total_modified_nets": len(modified_nets),
    }
