from __future__ import annotations

from dataclasses import dataclass

import numpy as np


QUALITY_POLICY_VERSION = "vhs_quality_gate_v2_2026-07-27"


@dataclass(frozen=True)
class QualityDecision:
    accepted: bool
    rejected: bool
    reason: str


def evaluate_physical_reference(
    value: float | None,
    *,
    upper_envelope_m3s: float,
) -> QualityDecision:
    if value is None or not np.isfinite(value):
        return QualityDecision(False, True, "missing_or_nonfinite_physical_reference")
    if float(value) < 0.0:
        return QualityDecision(False, True, "negative_physical_reference")
    if float(value) > float(upper_envelope_m3s):
        return QualityDecision(False, True, "physical_reference_above_frozen_envelope")
    return QualityDecision(True, False, "accepted_physical_reference")


def evaluate_specialist_output(
    specialist_value: float | None,
    physical_reference: float | None,
    *,
    specialist_upper_envelope_m3s: float,
    ratio_lower: float,
    ratio_upper: float,
) -> QualityDecision:
    if specialist_value is None or not np.isfinite(specialist_value):
        return QualityDecision(False, True, "missing_or_nonfinite_specialist_output")
    if float(specialist_value) < 0.0:
        return QualityDecision(False, True, "negative_specialist_output")
    if float(specialist_value) > float(specialist_upper_envelope_m3s):
        return QualityDecision(False, True, "specialist_output_above_frozen_envelope")
    if physical_reference is None or not np.isfinite(physical_reference):
        return QualityDecision(False, True, "specialist_without_physical_reference")
    if float(physical_reference) <= 0.0:
        return QualityDecision(False, True, "specialist_ratio_undefined")
    ratio = float(specialist_value) / float(physical_reference)
    if ratio < float(ratio_lower) or ratio > float(ratio_upper):
        return QualityDecision(False, True, "specialist_to_reference_ratio_outside_frozen_bounds")
    return QualityDecision(True, False, "accepted_specialist_output")
