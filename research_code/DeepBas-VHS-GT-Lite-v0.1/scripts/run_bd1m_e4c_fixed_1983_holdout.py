from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bd1m_physics_routing_model import (
    initialize_steady_state,
    route_daily,
)


EXP = ROOT / "outputs/vhs_bd1m/experiments"

FREEZE_JSON = EXP / "e4b3_method_freeze.json"

DATASET = (
    ROOT
    / "outputs/vhs_bd1m"
    / "bd1m_model_dataset_audit.csv"
)

DEV_PRED = (
    EXP
    / "e4b1_incremental_residual_predictions.csv"
)

COEF_FILE = (
    EXP
    / "e4b2b_temperature_seasonality_coefficients.csv"
)

E4B2A_METRICS = (
    EXP
    / "e4b2a_forcing_ablation_metrics.csv"
)

E4B2B_METRICS = (
    EXP
    / "e4b2b_temperature_seasonality_metrics.csv"
)


OUT_METRICS = (
    EXP
    / "e4c_1983_holdout_metrics.csv"
)

OUT_DAILY = (
    EXP
    / "e4c_1983_daily_predictions.csv"
)

OUT_REPORT = (
    EXP
    / "e4c_1983_holdout_report.md"
)


K_HARMONICS = 6

CAUSAL_SUPPORT_FEATURES = [
    "P_inc_3d",
    "P_inc_7d",
    "P_inc_30d",
    "T_inc_7d",
    "T_inc_30d",
]


def nse(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    denominator = np.sum(
        (obs - np.mean(obs)) ** 2
    )

    if denominator == 0:
        return np.nan

    return float(
        1.0
        - np.sum((obs - pred) ** 2)
        / denominator
    )


def kge(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    if len(obs) < 2:
        return np.nan

    obs_std = np.std(obs, ddof=1)
    pred_std = np.std(pred, ddof=1)

    if obs_std == 0 or np.mean(obs) == 0:
        return np.nan

    r = np.corrcoef(obs, pred)[0, 1]

    alpha = pred_std / obs_std
    beta = np.mean(pred) / np.mean(obs)

    return float(
        1.0
        - np.sqrt(
            (r - 1.0) ** 2
            + (alpha - 1.0) ** 2
            + (beta - 1.0) ** 2
        )
    )


def metric_dict(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    mask = (
        np.isfinite(obs)
        & np.isfinite(pred)
    )

    obs = obs[mask]
    pred = pred[mask]

    if len(obs) == 0:
        raise RuntimeError(
            "No valid samples for metric calculation."
        )

    return {
        "n_samples": len(obs),
        "NSE": nse(obs, pred),
        "KGE": kge(obs, pred),
        "RMSE": float(
            np.sqrt(
                np.mean(
                    (obs - pred) ** 2
                )
            )
        ),
        "MAE": float(
            np.mean(
                np.abs(obs - pred)
            )
        ),
        "Bias": float(
            np.mean(pred - obs)
        ),
        "Pearson": float(
            np.corrcoef(obs, pred)[0, 1]
        ),
    }


def add_fourier(df):
    out = df.copy()

    doy = (
        out["date"]
        .dt.dayofyear
        .to_numpy(float)
    )

    year_length = np.where(
        out["date"]
        .dt.is_leap_year
        .to_numpy(),
        366.0,
        365.0,
    )

    phase = (
        2.0
        * np.pi
        * (doy - 1.0)
        / year_length
    )

    columns = []

    for k in range(
        1,
        K_HARMONICS + 1,
    ):

        sin_name = f"season_sin_{k}"
        cos_name = f"season_cos_{k}"

        out[sin_name] = np.sin(
            k * phase
        )

        out[cos_name] = np.cos(
            k * phase
        )

        columns.extend(
            [sin_name, cos_name]
        )

    return out, columns


def frozen_fourier_correction(
    df,
    coef_map,
    features,
):
    correction = np.full(
        len(df),
        float(coef_map["INTERCEPT"]),
        dtype=float,
    )

    for feature in features:

        correction += (
            float(coef_map[feature])
            * df[feature].to_numpy(float)
        )

    return correction


def rmse(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    return float(
        np.sqrt(
            np.mean(
                (obs - pred) ** 2
            )
        )
    )


def main():

    # ==================================================
    # 1. Verify E4B3 freeze
    # ==================================================

    freeze = json.loads(
        FREEZE_JSON.read_text(
            encoding="utf-8"
        )
    )

    if not freeze.get(
        "freeze_status",
        False,
    ):
        raise RuntimeError(
            "E4B3 method is not frozen."
        )

    if (
        freeze[
            "final_correction_model"
        ]["name"]
        != "B2_FOURIER6_SEASONAL"
    ):
        raise RuntimeError(
            "Frozen final model mismatch."
        )

    if (
        freeze[
            "final_correction_model"
        ]["harmonics"]
        != 6
    ):
        raise RuntimeError(
            "Frozen harmonic count mismatch."
        )

    if (
        freeze[
            "final_correction_model"
        ][
            "refit_using_validation_before_test"
        ]
        is not False
    ):
        raise RuntimeError(
            "Validation refit is prohibited."
        )

    tau_global = float(
        freeze[
            "routing_backbone"
        ]["tau_global_days"]
    )

    substeps = int(
        freeze[
            "routing_backbone"
        ][
            "required_substeps_per_day"
        ]
    )

    # ==================================================
    # 2. Load EXACT frozen Fourier coefficients
    # ==================================================

    coef = pd.read_csv(
        COEF_FILE
    )

    coef = coef[
        coef["model"]
        == "B2_fourier6"
    ].copy()

    if len(coef) != 13:
        raise RuntimeError(
            "Expected 13 Fourier6 coefficients "
            "(1 intercept + 12 harmonics). "
            f"Got {len(coef)}."
        )

    coef_map = dict(
        zip(
            coef["feature"],
            coef["coefficient"],
        )
    )

    expected_features = []

    for k in range(1, 7):
        expected_features.extend(
            [
                f"season_sin_{k}",
                f"season_cos_{k}",
            ]
        )

    expected_keys = {
        "INTERCEPT",
        *expected_features,
    }

    if set(coef_map) != expected_keys:
        raise RuntimeError(
            "Frozen Fourier coefficient "
            "schema mismatch."
        )

    # ==================================================
    # 3. BEFORE TEST:
    #    reproduce 1982 development metrics
    # ==================================================

    dev = pd.read_csv(
        DEV_PRED,
        parse_dates=["date"],
    )

    dev, season_features = add_fourier(
        dev
    )

    complete = (
        dev[
            [
                "Q_target_dsk",
                "Q_R1_route",
                "routing_residual",
                *CAUSAL_SUPPORT_FEATURES,
            ]
        ]
        .notna()
        .all(axis=1)
    )

    dev_work = (
        dev.loc[complete]
        .copy()
    )

    train_dev = dev_work[
        dev_work["split_candidate"]
        == "train"
    ].copy()

    val_dev = dev_work[
        dev_work["split_candidate"]
        == "validation"
    ].copy()

    if len(train_dev) != 1431:
        raise RuntimeError(
            f"Development train support "
            f"changed: {len(train_dev)}"
        )

    if len(val_dev) != 365:
        raise RuntimeError(
            f"Validation support changed: "
            f"{len(val_dev)}"
        )

    # ----------------------------------------------
    # Frozen Fourier reproduction
    # ----------------------------------------------

    val_fourier_correction = (
        frozen_fourier_correction(
            val_dev,
            coef_map,
            season_features,
        )
    )

    val_fourier_prediction = np.maximum(
        val_dev[
            "Q_R1_route"
        ].to_numpy(float)
        + val_fourier_correction,
        0.0,
    )

    reproduced_fourier_rmse = rmse(
        val_dev[
            "Q_target_dsk"
        ],
        val_fourier_prediction,
    )

    old_b2b = pd.read_csv(
        E4B2B_METRICS
    )

    old_fourier_row = old_b2b[
        (
            old_b2b["model"]
            == "B2_fourier6"
        )
        & (
            old_b2b["split"]
            == "validation"
        )
    ].iloc[0]

    expected_fourier_rmse = float(
        old_fourier_row["RMSE"]
    )

    if not np.isclose(
        reproduced_fourier_rmse,
        expected_fourier_rmse,
        rtol=0,
        atol=1e-8,
    ):
        raise RuntimeError(
            "Frozen Fourier validation "
            "reproduction failed: "
            f"{reproduced_fourier_rmse} "
            f"vs {expected_fourier_rmse}"
        )

    # ----------------------------------------------
    # Monthly baseline reproduction
    # ----------------------------------------------

    train_month = (
        train_dev[
            [
                "date",
                "routing_residual",
            ]
        ]
        .copy()
    )

    train_month["month"] = (
        train_month["date"].dt.month
    )

    monthly_residual = (
        train_month
        .groupby("month")[
            "routing_residual"
        ]
        .mean()
        .to_dict()
    )

    val_month_correction = (
        val_dev["date"]
        .dt.month
        .map(monthly_residual)
        .to_numpy(float)
    )

    val_month_prediction = np.maximum(
        val_dev[
            "Q_R1_route"
        ].to_numpy(float)
        + val_month_correction,
        0.0,
    )

    reproduced_month_rmse = rmse(
        val_dev[
            "Q_target_dsk"
        ],
        val_month_prediction,
    )

    old_b2a = pd.read_csv(
        E4B2A_METRICS
    )

    old_month_row = old_b2a[
        (
            old_b2a["model"]
            == "A2_monthly_climatology"
        )
        & (
            old_b2a["split"]
            == "validation"
        )
    ].iloc[0]

    expected_month_rmse = float(
        old_month_row["RMSE"]
    )

    if not np.isclose(
        reproduced_month_rmse,
        expected_month_rmse,
        rtol=0,
        atol=1e-8,
    ):
        raise RuntimeError(
            "Monthly validation "
            "reproduction failed: "
            f"{reproduced_month_rmse} "
            f"vs {expected_month_rmse}"
        )

    print(
        "PRE_TEST_REPRODUCTION_GATE=PASS"
    )

    print(
        "reproduced_1982_Fourier6_RMSE="
        f"{reproduced_fourier_rmse:.6f}"
    )

    print(
        "reproduced_1982_monthly_RMSE="
        f"{reproduced_month_rmse:.6f}"
    )

    # ==================================================
    # 4. NOW load complete 1978-1983 routing data
    # ==================================================

    data = pd.read_csv(
        DATASET,
        parse_dates=["date"],
    )

    data = (
        data.sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )

    expected_dates = pd.date_range(
        "1978-01-01",
        "1983-12-31",
        freq="D",
    )

    if not data["date"].equals(
        pd.Series(
            expected_dates,
            name="date",
        )
    ):
        raise RuntimeError(
            "1978-1983 date sequence "
            "is not complete daily."
        )

    if len(data) != 2191:
        raise RuntimeError(
            f"Expected 2191 daily records, "
            f"got {len(data)}"
        )

    if (
        data[
            [
                "Q_input_byblk",
                "Q_target_dsk",
            ]
        ]
        .isna()
        .any()
        .any()
    ):
        raise RuntimeError(
            "Missing Q in full holdout series."
        )

    # ==================================================
    # 5. Continuous R1 route:
    #    initialize ONCE in 1978
    # ==================================================

    inflow = (
        data[
            "Q_input_byblk"
        ]
        .to_numpy(float)
    )

    tau = np.full(
        68,
        tau_global,
        dtype=float,
    )

    initial_storage = (
        initialize_steady_state(
            float(inflow[0]),
            tau,
        )
    )

    q_route, final_storage, mass_error = (
        route_daily(
            inflow,
            tau,
            substeps,
            initial_storage,
        )
    )

    max_mass_error = float(
        np.max(
            np.abs(mass_error)
        )
    )

    if max_mass_error > 1e-7:
        raise RuntimeError(
            "Mass-conservation gate failed: "
            f"{max_mass_error}"
        )

    data["Q_R1_route"] = q_route

    # ==================================================
    # 6. Apply frozen Fourier6
    #    NO fitting here
    # ==================================================

    data, full_season_features = (
        add_fourier(data)
    )

    correction_fourier = (
        frozen_fourier_correction(
            data,
            coef_map,
            full_season_features,
        )
    )

    data["Q_Fourier6_final"] = (
        np.maximum(
            data["Q_R1_route"]
            .to_numpy(float)
            + correction_fourier,
            0.0,
        )
    )

    # ==================================================
    # 7. Fixed monthly sensitivity baseline
    # ==================================================

    month_correction = (
        data["date"]
        .dt.month
        .map(monthly_residual)
        .to_numpy(float)
    )

    data["Q_monthly_sensitivity"] = (
        np.maximum(
            data["Q_R1_route"]
            .to_numpy(float)
            + month_correction,
            0.0,
        )
    )

    # ==================================================
    # 8. 1983 fixed holdout
    # ==================================================

    test = data[
        data["date"].dt.year == 1983
    ].copy()

    if len(test) != 365:
        raise RuntimeError(
            f"Expected 365 test days, "
            f"got {len(test)}"
        )

    obs = (
        test[
            "Q_target_dsk"
        ]
        .to_numpy(float)
    )

    result_rows = []

    model_columns = {
        "R1_ROUTING_ONLY":
            "Q_R1_route",

        "MONTHLY_RESIDUAL_CLIMATOLOGY":
            "Q_monthly_sensitivity",

        "B2_FOURIER6_SEASONAL_FINAL":
            "Q_Fourier6_final",
    }

    for model_name, column in (
        model_columns.items()
    ):

        pred = (
            test[column]
            .to_numpy(float)
        )

        result_rows.append(
            {
                "model": model_name,
                "split": "test_1983",
                **metric_dict(
                    obs,
                    pred,
                ),
            }
        )

    results = pd.DataFrame(
        result_rows
    )

    results.to_csv(
        OUT_METRICS,
        index=False,
    )

    # ==================================================
    # 9. Save 1983 daily predictions for E4D
    # ==================================================

    test[
        [
            "date",
            "Q_input_byblk",
            "Q_target_dsk",
            "Q_R1_route",
            "Q_monthly_sensitivity",
            "Q_Fourier6_final",
        ]
    ].to_csv(
        OUT_DAILY,
        index=False,
    )

    # ==================================================
    # 10. Report
    # ==================================================

    r1 = (
        results[
            results["model"]
            == "R1_ROUTING_ONLY"
        ]
        .iloc[0]
    )

    monthly = (
        results[
            results["model"]
            == "MONTHLY_RESIDUAL_CLIMATOLOGY"
        ]
        .iloc[0]
    )

    final = (
        results[
            results["model"]
            == "B2_FOURIER6_SEASONAL_FINAL"
        ]
        .iloc[0]
    )

    final_rmse_gain_vs_r1 = (
        (
            float(r1.RMSE)
            - float(final.RMSE)
        )
        / float(r1.RMSE)
        * 100.0
    )

    report = f"""# VHS-BD1M E4C Fixed 1983 Holdout

## Freeze compliance

- final model = B2_FOURIER6_SEASONAL
- Fourier harmonics = 6
- Fourier coefficients loaded from E4B2B
- no Fourier refit
- no 1982 refit
- no routing refit
- no model selection using 1983
- routing initialized once at 1978-01-01
- state propagated continuously through 1983

## Pre-test reproduction gate

- 1982 Fourier6 reproduced RMSE =
  {reproduced_fourier_rmse:.6f}

- expected 1982 Fourier6 RMSE =
  {expected_fourier_rmse:.6f}

- 1982 monthly reproduced RMSE =
  {reproduced_month_rmse:.6f}

- expected 1982 monthly RMSE =
  {expected_month_rmse:.6f}

PRE_TEST_REPRODUCTION_GATE=PASS

## Routing audit

- tau_global_days = {tau_global:.10f}
- required substeps/day = {substeps}
- max absolute mass error =
  {max_mass_error:.8g}

## 1983 holdout

### R1 routing only

- NSE = {float(r1.NSE):.6f}
- KGE = {float(r1.KGE):.6f}
- RMSE = {float(r1.RMSE):.6f}
- MAE = {float(r1.MAE):.6f}
- Bias = {float(r1.Bias):.6f}
- Pearson = {float(r1.Pearson):.6f}

### Monthly residual climatology

- NSE = {float(monthly.NSE):.6f}
- KGE = {float(monthly.KGE):.6f}
- RMSE = {float(monthly.RMSE):.6f}
- MAE = {float(monthly.MAE):.6f}
- Bias = {float(monthly.Bias):.6f}
- Pearson = {float(monthly.Pearson):.6f}

### Frozen Fourier6 final model

- NSE = {float(final.NSE):.6f}
- KGE = {float(final.KGE):.6f}
- RMSE = {float(final.RMSE):.6f}
- MAE = {float(final.MAE):.6f}
- Bias = {float(final.Bias):.6f}
- Pearson = {float(final.Pearson):.6f}

## Fixed comparison

- final RMSE improvement vs R1 (%) =
  {final_rmse_gain_vs_r1:.6f}

## Interpretation boundary

1983 is used only as a fixed-method E4 holdout.

No model, harmonic count, routing parameter,
feature set, or correction structure may be
changed based on these results.

## Status

E4C_METHOD_CHANGED_AFTER_FREEZE=false

E4C_1983_TEST_EVALUATED=true

E4C_TEST_USED_FOR_MODEL_SELECTION=false

READY_FOR_E4D_MONTHLY_AGGREGATION=true
"""

    OUT_REPORT.write_text(
        report,
        encoding="utf-8",
    )

    print("E4C complete")

    print(
        "PRE_TEST_REPRODUCTION_GATE=PASS"
    )

    print(
        f"test_R1_NSE={float(r1.NSE):.6f}"
    )

    print(
        f"test_R1_RMSE={float(r1.RMSE):.6f}"
    )

    print(
        "test_monthly_NSE="
        f"{float(monthly.NSE):.6f}"
    )

    print(
        "test_monthly_RMSE="
        f"{float(monthly.RMSE):.6f}"
    )

    print(
        "test_Fourier6_NSE="
        f"{float(final.NSE):.6f}"
    )

    print(
        "test_Fourier6_KGE="
        f"{float(final.KGE):.6f}"
    )

    print(
        "test_Fourier6_RMSE="
        f"{float(final.RMSE):.6f}"
    )

    print(
        "test_Fourier6_MAE="
        f"{float(final.MAE):.6f}"
    )

    print(
        "test_Fourier6_Bias="
        f"{float(final.Bias):.6f}"
    )

    print(
        "final_RMSE_improvement_vs_R1_pct="
        f"{final_rmse_gain_vs_r1:.6f}"
    )

    print(
        "E4C_TEST_USED_FOR_MODEL_SELECTION=false"
    )

    print(
        "READY_FOR_E4D_MONTHLY_AGGREGATION=true"
    )


if __name__ == "__main__":
    main()