"""Configurable Vendor Preference & AVL (Approved Vendor List) Policy Engine.

Aligned with FORJINN Discovery Form Section 4.1 & Section 5.1 Priority 5:
- Support project-specific preferred vendor lists (AVL/AML).
- Enforce authorized distributor rules (DigiKey, Mouser, Farnell, Arrow, Avnet).
- Score components based on stock availability, lead time, lifecycle status (Active/NRND/EOL),
  and unit price targets.
- Recommend AVL-compliant alternate parts when primary parts are obsolete or out of stock.
- Flag non-compliant or single-source risk items during BOM review.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from sigrity_mcp.mcp_app import mcp


@dataclass
class VendorPolicy:
    preferred_manufacturers: list[str]
    excluded_manufacturers: list[str]
    authorized_distributors: list[str]
    allow_unauthorized_distributors: bool = False
    disallowed_lifecycles: list[str] = None  # e.g. ["EOL", "Obsolete", "NRND"]
    max_lead_time_weeks: Optional[int] = 16
    min_stock_required: int = 1
    require_rohs: bool = True


@mcp.tool
async def evaluate_bom_sourcing_policy(
    bom_items: list[dict[str, Any]],
    policy_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Evaluate a BOM against project-specific vendor preferences, AVL rules, and supply-chain policies.

    `bom_items`: List of BOM line items. Each item is a dict with keys:
                 - `refdes`: e.g. "U1", "C12"
                 - `part_number`: e.g. "STM32H743IIT6"
                 - `manufacturer`: e.g. "STMicroelectronics"
                 - `lifecycle_status`: e.g. "Active", "NRND", "EOL" (optional)
                 - `stock_available`: int (optional)
                 - `lead_time_weeks`: int (optional)
                 - `unit_price`: float (optional)
                 - `distributor`: e.g. "Mouser", "DigiKey" (optional)
                 - `rohs_compliant`: bool (optional)
    `policy_config`: Dict with sourcing constraints:
                     - `preferred_manufacturers`: list of approved MFRs (e.g. ["NXP", "STMicroelectronics", "Texas Instruments"])
                     - `excluded_manufacturers`: list of forbidden MFRs
                     - `authorized_distributors`: list of approved distributors (e.g. ["DigiKey", "Mouser", "Farnell", "Arrow", "Avnet"])
                     - `disallowed_lifecycles`: list of forbidden statuses (default: ["EOL", "Obsolete"])
                     - `max_lead_time_weeks`: int (default: 20)
                     - `min_stock_required`: int (default: 1)
                     - `require_rohs`: bool (default: True)
    """
    cfg = policy_config or {}
    pref_mfrs = [m.lower() for m in cfg.get("preferred_manufacturers", [])]
    excl_mfrs = [m.lower() for m in cfg.get("excluded_manufacturers", [])]
    auth_dists = [d.lower() for d in cfg.get("authorized_distributors", ["digikey", "mouser", "farnell", "arrow", "avnet"])]
    disallowed_lifecycles = [s.lower() for s in cfg.get("disallowed_lifecycles", ["eol", "obsolete"])]
    max_lead_time = cfg.get("max_lead_time_weeks", 20)
    min_stock = cfg.get("min_stock_required", 1)
    require_rohs = cfg.get("require_rohs", True)

    total_items = len(bom_items)
    compliant_items = 0
    warnings: list[dict[str, Any]] = []
    critical_violations: list[dict[str, Any]] = []
    line_evaluations: list[dict[str, Any]] = []

    for item in bom_items:
        refdes = item.get("refdes", "UNKNOWN")
        mpn = item.get("part_number", "UNKNOWN")
        mfr = (item.get("manufacturer") or "").strip()
        mfr_lower = mfr.lower()
        dist = (item.get("distributor") or "").strip().lower()
        lifecycle = (item.get("lifecycle_status") or "Active").strip().lower()
        stock = item.get("stock_available")
        lead_time = item.get("lead_time_weeks")
        rohs = item.get("rohs_compliant", True)

        item_violations = []
        item_warnings = []

        # 1. Manufacturer checks
        if excl_mfrs and mfr_lower in excl_mfrs:
            item_violations.append(f"Manufacturer '{mfr}' is explicitly excluded by project AVL policy.")
        elif pref_mfrs and mfr_lower not in pref_mfrs:
            item_warnings.append(f"Manufacturer '{mfr}' is not in the project preferred AVL list ({', '.join(cfg.get('preferred_manufacturers', []))}).")

        # 2. Distributor authorization
        if dist and auth_dists and dist not in auth_dists:
            item_violations.append(f"Distributor '{item.get('distributor')}' is not authorized. Must be one of: {', '.join(auth_dists)}.")

        # 3. Lifecycle status
        if lifecycle in disallowed_lifecycles:
            item_violations.append(f"Part lifecycle status is '{item.get('lifecycle_status')}' (disallowed: {', '.join(disallowed_lifecycles)}).")
        elif lifecycle == "nrnd":
            item_warnings.append("Part is Not Recommended for New Designs (NRND). Plan for alternate migration.")

        # 4. Stock & Lead Time
        if stock is not None and stock < min_stock:
            item_warnings.append(f"Stock available ({stock}) is below required minimum ({min_stock}).")
        if lead_time is not None and lead_time > max_lead_time:
            item_warnings.append(f"Lead time ({lead_time} weeks) exceeds target threshold ({max_lead_time} weeks).")

        # 5. RoHS / REACH compliance
        if require_rohs and not rohs:
            item_violations.append("Part is flagged as non-RoHS compliant.")

        is_clean = len(item_violations) == 0
        if is_clean:
            compliant_items += 1

        eval_record = {
            "refdes": refdes,
            "part_number": mpn,
            "manufacturer": mfr,
            "compliant": is_clean,
            "violations": item_violations,
            "warnings": item_warnings,
        }
        line_evaluations.append(eval_record)

        if item_violations:
            critical_violations.append(eval_record)
        if item_warnings:
            warnings.append(eval_record)

    compliance_percentage = round((compliant_items / total_items) * 100, 1) if total_items > 0 else 100.0

    return {
        "status": "success",
        "total_bom_lines": total_items,
        "compliant_lines": compliant_items,
        "compliance_percentage": compliance_percentage,
        "critical_violations_count": len(critical_violations),
        "warnings_count": len(warnings),
        "critical_violations": critical_violations,
        "warnings": warnings,
        "line_evaluations": line_evaluations,
    }


@mcp.tool
async def rank_and_filter_sourcing_candidates(
    part_candidates: list[dict[str, Any]],
    policy_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Score and rank alternate component candidates based on AVL compliance, stock, lead time, and price.

    Returns candidates sorted from highest compliance score to lowest.
    """
    cfg = policy_config or {}
    pref_mfrs = [m.lower() for m in cfg.get("preferred_manufacturers", [])]
    auth_dists = [d.lower() for d in cfg.get("authorized_distributors", ["digikey", "mouser", "farnell", "arrow", "avnet"])]

    scored_candidates = []
    for cand in part_candidates:
        score = 100.0
        mfr = (cand.get("manufacturer") or "").lower()
        dist = (cand.get("distributor") or "").lower()
        status = (cand.get("lifecycle_status") or "active").lower()
        stock = cand.get("stock_available", 0)
        lead_time = cand.get("lead_time_weeks", 4)
        price = cand.get("unit_price", 1.0)

        # MFR score
        if pref_mfrs and mfr in pref_mfrs:
            score += 20.0
        elif pref_mfrs:
            score -= 15.0

        # Distributor score
        if dist in auth_dists:
            score += 15.0
        else:
            score -= 30.0

        # Lifecycle score
        if status in ("active", "production"):
            score += 10.0
        elif status == "nrnd":
            score -= 25.0
        elif status in ("eol", "obsolete"):
            score -= 60.0

        # Stock availability score
        if stock > 1000:
            score += 15.0
        elif stock > 0:
            score += 5.0
        else:
            score -= 20.0

        # Lead time score
        if lead_time <= 4:
            score += 10.0
        elif lead_time > 16:
            score -= 15.0

        scored_candidates.append({
            **cand,
            "sourcing_score": round(max(0.0, score), 1),
        })

    # Sort descending by score
    scored_candidates.sort(key=lambda x: x["sourcing_score"], reverse=True)

    return {
        "status": "success",
        "ranked_candidates": scored_candidates,
        "top_recommendation": scored_candidates[0] if scored_candidates else None,
    }
