import insurance_mcp


def _assert_topic(module_title: str, expected_topic: str):
    qs = insurance_mcp.generate_topic_aligned_questions(
        module_order=1,
        module_title=module_title,
        module_description=f"A comprehensive overview of {module_title.lower()}.",
        count=10,
        seed="test-seed",
    )
    assert qs, "Expected non-empty question bank"
    topics = {q.get("topic") for q in qs}
    assert topics == {expected_topic}


def test_topic_alignment_basics():
    _assert_topic("What Is Car Insurance?", "car_insurance_basics")
    _assert_topic("Understanding Deductibles", "deductibles_full")
    _assert_topic("What Is a Premium?", "premium_basics")


def test_topic_alignment_safe_driving_and_accidents():
    _assert_topic("Steps to Take During a Car Accident", "accident_steps")
    _assert_topic("Do’s and Don’ts of Safe Driving", "safe_driving")
    _assert_topic("Filing a Claim After an Accident", "claim_after_accident")


def test_topic_alignment_coverages():
    _assert_topic("Types of Car Insurance Coverage", "coverage_types")
    _assert_topic("Liability Insurance", "liability")
    _assert_topic("Collision Coverage", "collision")
    _assert_topic("Comprehensive Coverage", "comprehensive")
    _assert_topic("Medical Payments / PIP", "medical_payments")
    _assert_topic("Uninsured / Underinsured Motorist Coverage", "uninsured_underinsured")
    _assert_topic("Gap Insurance", "gap_insurance")
    _assert_topic("Rental Car Coverage", "rental_car")


def test_topic_alignment_premiums_deductibles_and_claims():
    _assert_topic("Deductibles", "deductibles_short")
    _assert_topic("Premiums", "premiums_short")
    _assert_topic("Insurance Claims", "claims_short")
    _assert_topic("Insurance Adjusters", "adjusters")


def test_topic_alignment_policy_and_limits():
    _assert_topic("Insurance Policy", "policy")
    _assert_topic("Coverage Limits", "coverage_limits")
    _assert_topic("Policy Renewal and Cancellation", "policy_renewal")
    _assert_topic("State Insurance Requirements", "state_requirements")


def test_topic_alignment_rates_and_behavior():
    _assert_topic("Factors Affecting Insurance Rates", "rate_factors_short")
    _assert_topic("Driving Record Impact", "driving_record_impact")
    _assert_topic("Discounts", "discounts_short")
    _assert_topic("Avoiding Insurance Fraud", "fraud")
    _assert_topic("Responsible Driving and Insurance", "responsible_driving")
