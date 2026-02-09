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


def test_topic_alignment_accident_steps():
    _assert_topic("Steps to Take During a car accident", "accident_steps")


def test_topic_alignment_safe_driving():
    _assert_topic("Do's and Don'ts of Safe Driving", "safe_driving")


def test_topic_alignment_rates_and_discounts():
    _assert_topic("Factors affecting insurance rates", "rate_factors")
    _assert_topic("How to get discounts on auto insurance", "discounts")


def test_topic_alignment_special_coverages():
    _assert_topic("How to handle uninsured motorist situations", "uninsured_motorist")
    _assert_topic("Understanding rental car coverage", "rental_car")
    _assert_topic("Understanding roadside assistance coverage", "roadside")


def test_topic_alignment_total_loss_and_gap_and_fraud():
    _assert_topic("What to do in case of a total loss", "total_loss")
    _assert_topic("Understanding gap insurance", "gap")
    _assert_topic("How to avoid insurance fraud", "fraud")
