from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SafetyEvidence:
    required_inputs_available: bool
    physical_reference_available: bool
    specialist_validated: bool
    specialist_authorized: bool
    scope: str


@dataclass(frozen=True)
class RoutedOutput:
    point_q_m3s: float
    output_status: str
    method: str
    correction_applied: bool
    claim_scope: str


def route_virtual_station_output(
    baseline_q_m3s: float | None,
    specialist_q_m3s: float | None,
    evidence: SafetyEvidence,
    baseline_method: str,
    specialist_method: str,
) -> RoutedOutput:
    baseline_finite = baseline_q_m3s is not None and np.isfinite(baseline_q_m3s)
    specialist_finite = specialist_q_m3s is not None and np.isfinite(specialist_q_m3s)
    if not evidence.required_inputs_available or not evidence.physical_reference_available:
        return RoutedOutput(
            point_q_m3s=float("nan"),
            output_status="withheld_insufficient_evidence",
            method="no_discharge_output",
            correction_applied=False,
            claim_scope=evidence.scope,
        )
    if not baseline_finite:
        return RoutedOutput(
            point_q_m3s=float("nan"),
            output_status="withheld_missing_baseline",
            method="no_discharge_output",
            correction_applied=False,
            claim_scope=evidence.scope,
        )
    if (
        evidence.specialist_validated
        and evidence.specialist_authorized
        and specialist_finite
    ):
        return RoutedOutput(
            point_q_m3s=float(max(float(specialist_q_m3s), 0.0)),
            output_status="specialist_output_authorized",
            method=specialist_method,
            correction_applied=True,
            claim_scope=evidence.scope,
        )
    return RoutedOutput(
        point_q_m3s=float(max(float(baseline_q_m3s), 0.0)),
        output_status="physical_baseline_fallback",
        method=baseline_method,
        correction_applied=False,
        claim_scope=evidence.scope,
    )
