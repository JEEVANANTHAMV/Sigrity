import json
import os
import pytest

from sigrity_mcp.domains.cad.audit_approval_tools import (
    generate_design_change_report,
    record_engineering_approval,
    tag_ai_design_revision,
)


@pytest.mark.asyncio
async def test_audit_approval_lifecycle(tmp_path):
    proj_path = str(tmp_path / "FRDM_IMX91.brd")
    meta_path = str(tmp_path / "AI_REVISION_META.json")
    report_path = str(tmp_path / "Change_Report.md")

    # 1. Tag revision
    tag_res = await tag_ai_design_revision(
        project_path=proj_path,
        revision_id="REV_AI_001",
        change_summary="Optimized DDR4 routing and added bypass caps",
        output_meta_path=meta_path,
    )
    assert tag_res["status"] == "success"
    assert tag_res["approval_status"] == "PENDING_ENGINEERING_REVIEW"

    # 2. Record engineering approval
    app_res = await record_engineering_approval(
        metadata_file_path=meta_path,
        reviewer_name="Gokulan Udayakumar",
        reviewer_email="gokulan.udayakumar@ltsct.com",
        reviewer_role="Hardware Lead",
        decision="APPROVED",
        review_comments="DDR4 timing and impedance verified.",
    )
    assert app_res["status"] == "success"
    assert app_res["approval_status"] == "APPROVED"

    # 3. Generate change report
    rep_res = await generate_design_change_report(
        baseline_design_name="FRDM_IMX91_v1.0",
        ai_modified_design_name="FRDM_IMX91_v1.1_AI",
        added_components=["C101", "C102"],
        removed_components=[],
        modified_nets=["DDR_CLK_P", "DDR_CLK_N"],
        constraint_changes=["Enforced 80Ω diff impedance on DDR bus"],
        change_rationale="Minimize jitter and reflection on high-speed memory bus.",
        output_report_path=report_path,
    )
    assert rep_res["status"] == "success"
    assert os.path.exists(report_path)
