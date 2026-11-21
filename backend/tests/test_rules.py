from app.rules import evaluate_profile


def test_non_food_business_does_not_receive_fssai_rule():
    profile = {
        "business_name": "North Kolkata Hardware",
        "business_type": "small_business",
        "activities": ["retail"],
        "premises": "commercial_premises",
        "annual_turnover": 500000,
    }
    evaluation = evaluate_profile(profile, "2026-11-21")
    rule_ids = {result["rule_id"] for result in evaluation["results"]}
    assert "WB-FSSAI-001" not in rule_ids


def test_food_business_receives_fssai_candidate_rule():
    profile = {
        "business_name": "Home Bakery",
        "business_type": "home_bakery",
        "activities": ["baking", "online_sales"],
        "premises": "residential_kitchen",
        "annual_turnover": None,
    }
    evaluation = evaluate_profile(profile, "2026-11-21")
    results = {result["rule_id"]: result for result in evaluation["results"]}
    assert results["WB-FSSAI-001"]["status"] == "CONDITIONAL"
    assert results["WB-GST-002"]["status"] == "UNRESOLVED"
    assert "annual_turnover" in results["WB-GST-002"]["missing_facts"]


def test_missing_employee_count_is_preserved_as_missing_not_zero():
    profile = {
        "business_name": "New Service",
        "business_type": "small_business",
        "activities": ["consulting"],
        "premises": "commercial_premises",
        "annual_turnover": 100000,
        "employee_count": None,
    }
    evaluation = evaluate_profile(profile, "2026-11-21")
    assert evaluation["engine_version"] == "rules-engine-local-1.0"
