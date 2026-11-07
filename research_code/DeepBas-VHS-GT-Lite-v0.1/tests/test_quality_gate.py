from vhs.quality import evaluate_physical_reference, evaluate_specialist_output


def test_physical_reference_above_envelope_is_rejected():
    result = evaluate_physical_reference(101.0, upper_envelope_m3s=100.0)
    assert result.rejected
    assert result.reason == "physical_reference_above_frozen_envelope"


def test_specialist_ratio_outside_bounds_is_rejected():
    result = evaluate_specialist_output(
        50.0,
        10.0,
        specialist_upper_envelope_m3s=100.0,
        ratio_lower=0.4,
        ratio_upper=4.0,
    )
    assert result.rejected
    assert result.reason == "specialist_to_reference_ratio_outside_frozen_bounds"


def test_valid_pair_is_accepted():
    physical = evaluate_physical_reference(10.0, upper_envelope_m3s=100.0)
    specialist = evaluate_specialist_output(
        15.0,
        10.0,
        specialist_upper_envelope_m3s=100.0,
        ratio_lower=0.4,
        ratio_upper=4.0,
    )
    assert physical.accepted
    assert specialist.accepted
