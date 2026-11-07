import math

from vhs.router import SafetyEvidence, route_virtual_station_output


def test_missing_natural_supervision_withholds_discharge():
    output = route_virtual_station_output(
        None,
        None,
        SafetyEvidence(False, False, False, False, "geometry_only"),
        "rating_baseline",
        "natural_head",
    )
    assert math.isnan(output.point_q_m3s)
    assert output.output_status == "withheld_insufficient_evidence"


def test_validated_historical_reservoir_head_is_routed():
    output = route_virtual_station_output(
        10.0,
        14.0,
        SafetyEvidence(True, True, True, True, "historically_gauged_gap"),
        "physical_reference",
        "bounded_reservoir_head",
    )
    assert output.point_q_m3s == 14.0
    assert output.correction_applied


def test_rejected_agriculture_head_falls_back_to_endpoint_baseline():
    output = route_virtual_station_output(
        8.0,
        20.0,
        SafetyEvidence(True, True, False, False, "ungauged_middle_station"),
        "geometric_endpoints",
        "agriculture_memory_head",
    )
    assert output.point_q_m3s == 8.0
    assert output.output_status == "physical_baseline_fallback"
    assert not output.correction_applied


def test_authorized_negative_specialist_is_clipped_to_zero():
    output = route_virtual_station_output(
        3.0,
        -5.0,
        SafetyEvidence(True, True, True, True, "test"),
        "baseline",
        "specialist",
    )
    assert output.point_q_m3s == 0.0
