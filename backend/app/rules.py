from typing import Any


ENGINE_VERSION = "rules-engine-local-1.0"


def evaluate_profile(profile: dict[str, Any], evaluation_date: str) -> dict[str, Any]:
    activities = profile.get("activities") or []
    business_type = profile.get("business_type")
    premises = profile.get("premises")
    turnover = profile.get("annual_turnover")
    is_food = (
        "baking" in activities
        or "food" in activities
        or business_type in {"home_bakery", "food_business"}
    )

    results: list[dict[str, Any]] = []
    if is_food:
        results.append({
            "rule_id": "WB-FSSAI-001",
            "rule_version": 1,
            "title": "FSSAI registration assessment",
            "status": "CONDITIONAL" if premises else "UNRESOLVED",
            "authority": "FSSAI",
            "jurisdiction": "IN-WB",
            "source_type": "CANDIDATE",
            "source": "Official source verification pending",
            "matched_conditions": ["food_activity", premises] if premises else ["food_activity"],
            "missing_facts": [] if premises else ["premises"],
            "disclaimer": "Candidate rule. Verify against the current official source before action.",
        })

    if turnover is None:
        results.append({
            "rule_id": "WB-GST-002",
            "rule_version": 1,
            "title": "GST turnover threshold assessment",
            "status": "UNRESOLVED",
            "authority": "GST Department",
            "jurisdiction": "IN-WB",
            "source_type": "CANDIDATE",
            "source": "Official source verification pending",
            "matched_conditions": [],
            "missing_facts": ["annual_turnover"],
            "disclaimer": "Candidate rule. Confirm annual turnover before applicability is evaluated.",
        })
    else:
        results.append({
            "rule_id": "WB-GST-002",
            "rule_version": 1,
            "title": "GST turnover threshold assessment",
            "status": "CONDITIONAL" if turnover < 20_000_00 else "APPLICABLE",
            "authority": "GST Department",
            "jurisdiction": "IN-WB",
            "source_type": "CANDIDATE",
            "source": "Official source verification pending",
            "matched_conditions": ["confirmed_turnover"],
            "missing_facts": [],
            "disclaimer": "Candidate rule. Verify against the current official source before action.",
        })

    results.append({
        "rule_id": "WB-SOE-003",
        "rule_version": 1,
        "title": "Shops and Establishments assessment",
        "status": "APPLICABLE" if business_type else "UNRESOLVED",
        "authority": "West Bengal Labour Department",
        "jurisdiction": "IN-WB",
        "source_type": "CANDIDATE",
        "source": "Official source verification pending",
        "matched_conditions": ["business_activity"] if business_type else [],
        "missing_facts": [] if business_type else ["business_type"],
        "disclaimer": "Candidate rule. Verify against the current official source before action.",
    })

    return {
        "engine_version": ENGINE_VERSION,
        "evaluation_date": evaluation_date,
        "results": results,
    }
