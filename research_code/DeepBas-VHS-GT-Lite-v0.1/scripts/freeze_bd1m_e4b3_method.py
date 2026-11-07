from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/vhs_bd1m/experiments"

R1_FILE = EXP / "e4a2_r1_train_fit.csv"
E4B2B_METRICS = EXP / "e4b2b_temperature_seasonality_metrics.csv"
E4B2C_REPORT = EXP / "e4b2c_stability_report.md"
E4B2C_YEARWISE = EXP / "e4b2c_yearwise_stability.csv"
E4B2C_BOOT = EXP / "e4b2c_validation_bootstrap_summary.csv"

FREEZE_JSON = EXP / "e4b3_method_freeze.json"
FREEZE_MD = EXP / "e4b3_method_freeze_report.md"


def main() -> None:

    # --------------------------------------------------
    # 1. Verify prior gate
    # --------------------------------------------------

    report = E4B2C_REPORT.read_text(encoding="utf-8")

    required_status = [
        "E4B2C_TEST_1983_EVALUATED=false",
        "T7_LOYO_STABLE=false",
        "T7_BOOTSTRAP_SUPPORTED=false",
        "T7_SEASONAL_PROXY_STABLE=false",
        "TEMPERATURE_SIGNAL_BEYOND_SEASONALITY=false",
        "NONLINEAR_MODEL_JUSTIFIED=false",
        "RECOMMENDED_FINAL_CORRECTION_MODEL=B2_FOURIER6_SEASONAL",
        "READY_FOR_E4B3_METHOD_FREEZE=true",
    ]

    missing = [
        x for x in required_status
        if x not in report
    ]

    if missing:
        raise RuntimeError(
            f"E4B2C gate mismatch: {missing}"
        )

    # --------------------------------------------------
    # 2. Frozen routing
    # --------------------------------------------------

    r1 = pd.read_csv(R1_FILE)

    if len(r1) != 1:
        raise RuntimeError(
            "Expected exactly one frozen R1 row."
        )

    tau = float(r1.loc[0, "tau_global_days"])
    substeps = int(r1.loc[0, "required_substeps"])

    # --------------------------------------------------
    # 3. Record validation evidence
    # --------------------------------------------------

    metrics = pd.read_csv(E4B2B_METRICS)

    val = (
        metrics[
            metrics["split"] == "validation"
        ]
        .set_index("model")
    )

    fourier = val.loc["B2_fourier6"]
    monthly = val.loc["B1_monthly"]
    t7 = val.loc["B3_T7"]

    yearwise = pd.read_csv(E4B2C_YEARWISE)

    pivot = yearwise.pivot(
        index="holdout_year",
        columns="model",
        values="RMSE",
    )

    boot = pd.read_csv(E4B2C_BOOT).iloc[0]

    # --------------------------------------------------
    # 4. Freeze
    # --------------------------------------------------

    freeze = {
        "protocol":
            "VHS-BD1M-PHASE-E4B3-METHOD-FREEZE",

        "freeze_status": True,

        "routing_backbone": {
            "model": "R1_HOMOGENEOUS_68_REACH",
            "tau_global_days": tau,
            "required_substeps_per_day": substeps,
            "initialization":
                "once at 1978-01-01 steady state",
            "state_reset_at_validation": False,
            "state_reset_at_test": False,
            "routing_refit_after_E4A2": False,
        },

        "final_correction_model": {
            "name": "B2_FOURIER6_SEASONAL",
            "target":
                "Q_DSK_obs - Q_R1_route",
            "harmonics": 6,
            "features": [
                "sin(2*pi*k*DOY/year_length)",
                "cos(2*pi*k*DOY/year_length)",
            ],
            "k": [1, 2, 3, 4, 5, 6],
            "regressor":
                "ordinary_least_squares",
            "fit_period":
                "1978-01-01..1981-12-31",
            "validation_period":
                "1982-01-01..1982-12-31",
            "test_period":
                "1983-01-01..1983-12-31",
            "refit_using_validation_before_test":
                False,
            "prediction_nonnegativity_rule":
                "max(prediction, 0)",
        },

        "rejected_candidates": {
            "T7_temperature_proxy": {
                "reason":
                    "failed LOYO and block-bootstrap stability gates",
                "causal_temperature_claim_allowed":
                    False,
            },
            "temperature_anomaly": {
                "reason":
                    "no gain beyond seasonal Fourier null",
            },
            "nonlinear_model": {
                "reason":
                    "not justified by E4B2B/E4B2C evidence",
            },
            "R2_reach_heterogeneity": {
                "reason":
                    "negligible train gain and poor identifiability",
            },
        },

        "fixed_sensitivity_baselines_for_E4C": [
            "R1_ROUTING_ONLY",
            "MONTHLY_RESIDUAL_CLIMATOLOGY",
        ],

        "validation_evidence": {
            "Fourier6_RMSE":
                float(fourier["RMSE"]),
            "Fourier6_NSE":
                float(fourier["NSE"]),

            "Monthly_RMSE":
                float(monthly["RMSE"]),
            "Monthly_NSE":
                float(monthly["NSE"]),

            "T7_RMSE":
                float(t7["RMSE"]),
            "T7_NSE":
                float(t7["NSE"]),

            "T7_LOYO_wins":
                1,

            "T7_LOYO_median_gain_pct":
                -6.179175,

            "T7_bootstrap_CI":
                [
                    float(boot["ci_2_5"]),
                    float(boot["ci_97_5"]),
                ],
        },

        "interpretation_boundary": {
            "temperature_signal_beyond_seasonality":
                False,

            "temperature_causal_claim_allowed":
                False,

            "interpretation":
                "dominant missing component is treated as "
                "seasonal incremental-catchment contribution; "
                "temperature may act as a seasonal/hydrologic-state "
                "proxy but is not retained as the final correction.",
        },

        "post_freeze_prohibited_changes": [
            "change Fourier harmonic count",
            "select T7 based on 1983",
            "introduce Random Forest based on 1983",
            "retune R1 or R2 using 1983",
            "change feature windows using 1983",
            "select model based on 1983 test performance",
        ],

        "next_phase":
            "E4C_FIXED_METHOD_1983_HOLDOUT",

        "ready_for_E4C": True,
    }

    FREEZE_JSON.write_text(
        json.dumps(
            freeze,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    md = f"""# VHS-BD1M E4B3 Method Freeze

## Final method

Routing backbone:

- R1 homogeneous 68-reach routing
- tau_global_days = {tau:.10f}
- required substeps/day = {substeps}

Final correction:

- B2_FOURIER6_SEASONAL
- six annual Fourier harmonics
- ordinary least squares
- target = observed DSK - R1 routing prediction
- fitted on 1978-1981 only
- validation = 1982
- no validation refit before 1983

## Evidence

1982 validation:

- Fourier6 RMSE = {float(fourier["RMSE"]):.6f}
- Fourier6 NSE = {float(fourier["NSE"]):.6f}
- monthly climatology RMSE = {float(monthly["RMSE"]):.6f}
- T7 RMSE = {float(t7["RMSE"]):.6f}

T7 stability:

- LOYO wins = 1/4
- median LOYO gain = -6.179175%
- bootstrap 95% CI =
  [{float(boot["ci_2_5"]):.6f},
   {float(boot["ci_97_5"]):.6f}]

Therefore T7 is rejected as the final correction.

## Interpretation

The current evidence supports a strong seasonal
incremental-catchment component missing from routing-only
prediction.

No independent causal temperature effect is claimed.

## Freeze

METHOD_FROZEN=true

FINAL_ROUTING_MODEL=R1_HOMOGENEOUS_68_REACH

FINAL_CORRECTION_MODEL=B2_FOURIER6_SEASONAL

FOURIER_HARMONICS=6

FINAL_CORRECTION_TRAIN_PERIOD=1978_1981

VALIDATION_PERIOD=1982

TEST_PERIOD=1983

REFIT_ON_VALIDATION_BEFORE_TEST=false

NONLINEAR_MODEL_ALLOWED_AFTER_FREEZE=false

TEST_BASED_MODEL_SELECTION_ALLOWED=false

READY_FOR_E4C=true
"""

    FREEZE_MD.write_text(
        md,
        encoding="utf-8",
    )

    print("E4B3 method freeze complete")
    print(f"tau_global_days={tau:.10f}")
    print(f"required_substeps={substeps}")
    print(
        "FINAL_CORRECTION_MODEL="
        "B2_FOURIER6_SEASONAL"
    )
    print("FOURIER_HARMONICS=6")
    print(
        "REFIT_ON_VALIDATION_BEFORE_TEST=false"
    )
    print(
        "TEST_BASED_MODEL_SELECTION_ALLOWED=false"
    )
    print("METHOD_FROZEN=true")
    print("READY_FOR_E4C=true")


if __name__ == "__main__":
    main()