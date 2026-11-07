from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/vhs_bd1m/experiments"

INPUT = EXP / "e4b1_incremental_residual_predictions.csv"

METRICS_OUT = EXP / "e4b2a_forcing_ablation_metrics.csv"
COEF_OUT = EXP / "e4b2a_forcing_ablation_coefficients.csv"
PRED_OUT = EXP / "e4b2a_forcing_ablation_predictions.csv"
REPORT_OUT = EXP / "e4b2a_forcing_ablation_report.md"


P_FEATURES = [
    "P_inc_3d",
    "P_inc_7d",
    "P_inc_30d",
]

T_FEATURES = [
    "T_inc_7d",
    "T_inc_30d",
]

PT_FEATURES = P_FEATURES + T_FEATURES


def nse(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    den = np.sum((obs - np.mean(obs)) ** 2)

    if den == 0:
        return np.nan

    return float(
        1.0 - np.sum((obs - pred) ** 2) / den
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
        1.0 - np.sqrt(
            (r - 1.0) ** 2
            + (alpha - 1.0) ** 2
            + (beta - 1.0) ** 2
        )
    )


def metric_dict(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    mask = np.isfinite(obs) & np.isfinite(pred)

    obs = obs[mask]
    pred = pred[mask]

    if len(obs) == 0:
        return {
            "n_samples": 0,
            "NSE": np.nan,
            "KGE": np.nan,
            "RMSE": np.nan,
            "MAE": np.nan,
            "Bias": np.nan,
            "Pearson": np.nan,
        }

    pearson = (
        float(np.corrcoef(obs, pred)[0, 1])
        if len(obs) >= 2
        else np.nan
    )

    return {
        "n_samples": len(obs),
        "NSE": nse(obs, pred),
        "KGE": kge(obs, pred),
        "RMSE": float(
            np.sqrt(np.mean((obs - pred) ** 2))
        ),
        "MAE": float(
            np.mean(np.abs(obs - pred))
        ),
        "Bias": float(
            np.mean(pred - obs)
        ),
        "Pearson": pearson,
    }


def fit_ols(
    train,
    df,
    features,
    name,
    coef_rows,
):
    model = LinearRegression()

    model.fit(
        train[features],
        train["routing_residual"],
    )

    correction = model.predict(
        df[features]
    )

    coef_rows.append(
        {
            "model": name,
            "feature": "INTERCEPT",
            "coefficient": float(model.intercept_),
        }
    )

    for feature, coefficient in zip(
        features,
        model.coef_,
    ):
        coef_rows.append(
            {
                "model": name,
                "feature": feature,
                "coefficient": float(coefficient),
            }
        )

    return correction


def main():

    df = pd.read_csv(
        INPUT,
        parse_dates=["date"],
    )

    # E4B2A must contain only train + validation.
    if (df["date"] >= "1983-01-01").any():
        raise RuntimeError(
            "1983 test data detected. "
            "E4B2A must not evaluate test."
        )

    required = {
        "date",
        "split_candidate",
        "Q_target_dsk",
        "Q_R1_route",
        "routing_residual",
        *PT_FEATURES,
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}"
        )

    # ------------------------------------------------------
    # Use EXACTLY the same support for every ablation.
    # ------------------------------------------------------

    complete = (
        df[
            [
                "Q_target_dsk",
                "Q_R1_route",
                "routing_residual",
                *PT_FEATURES,
            ]
        ]
        .notna()
        .all(axis=1)
    )

    work = df.loc[complete].copy()

    train = work[
        work["split_candidate"] == "train"
    ].copy()

    validation = work[
        work["split_candidate"] == "validation"
    ].copy()

    if len(train) != 1431:
        raise RuntimeError(
            f"Expected 1431 train samples, got {len(train)}"
        )

    if len(validation) != 365:
        raise RuntimeError(
            f"Expected 365 validation samples, "
            f"got {len(validation)}"
        )

    # ------------------------------------------------------
    # A0: routing only
    # ------------------------------------------------------

    work["A0_R1"] = work["Q_R1_route"]

    # ------------------------------------------------------
    # A1: constant mean residual
    # ------------------------------------------------------

    mean_residual = float(
        train["routing_residual"].mean()
    )

    work["A1_mean_residual"] = (
        work["Q_R1_route"]
        + mean_residual
    )

    # ------------------------------------------------------
    # A2: monthly residual climatology
    # ------------------------------------------------------

    train = train.copy()
    train["month"] = train["date"].dt.month
    work["month"] = work["date"].dt.month

    monthly_residual = (
        train.groupby("month")["routing_residual"]
        .mean()
        .to_dict()
    )

    if set(monthly_residual.keys()) != set(range(1, 13)):
        raise RuntimeError(
            "Train monthly residual climatology "
            "does not contain all 12 months."
        )

    work["A2_monthly_climatology"] = (
        work["Q_R1_route"]
        + work["month"].map(monthly_residual)
    )

    # ------------------------------------------------------
    # A3-A5: meteorological residual models
    # ------------------------------------------------------

    coef_rows = []

    correction_p = fit_ols(
        train,
        work,
        P_FEATURES,
        "A3_P_OLS",
        coef_rows,
    )

    correction_t = fit_ols(
        train,
        work,
        T_FEATURES,
        "A4_T_OLS",
        coef_rows,
    )

    correction_pt = fit_ols(
        train,
        work,
        PT_FEATURES,
        "A5_PT_OLS",
        coef_rows,
    )

    work["A3_P_OLS"] = (
        work["Q_R1_route"] + correction_p
    )

    work["A4_T_OLS"] = (
        work["Q_R1_route"] + correction_t
    )

    work["A5_PT_OLS"] = (
        work["Q_R1_route"] + correction_pt
    )

    # Same physical non-negativity rule.
    prediction_columns = [
        "A0_R1",
        "A1_mean_residual",
        "A2_monthly_climatology",
        "A3_P_OLS",
        "A4_T_OLS",
        "A5_PT_OLS",
    ]

    negative_counts = {}

    for column in prediction_columns:

        negative_counts[column] = int(
            (work[column] < 0).sum()
        )

        work[column] = np.maximum(
            work[column],
            0.0,
        )

    # ------------------------------------------------------
    # Metrics
    # ------------------------------------------------------

    rows = []

    for split in ["train", "validation"]:

        subset = work[
            work["split_candidate"] == split
        ]

        obs = subset[
            "Q_target_dsk"
        ].to_numpy(float)

        for model_name in prediction_columns:

            pred = subset[
                model_name
            ].to_numpy(float)

            rows.append(
                {
                    "model": model_name,
                    "split": split,
                    **metric_dict(obs, pred),
                }
            )

    metrics = pd.DataFrame(rows)

    metrics.to_csv(
        METRICS_OUT,
        index=False,
    )

    pd.DataFrame(
        coef_rows
    ).to_csv(
        COEF_OUT,
        index=False,
    )

    work[
        [
            "date",
            "split_candidate",
            "Q_target_dsk",
            "Q_R1_route",
            "routing_residual",
            *PT_FEATURES,
            *prediction_columns,
        ]
    ].to_csv(
        PRED_OUT,
        index=False,
    )

    # ------------------------------------------------------
    # Validation diagnostic
    # ------------------------------------------------------

    val = (
        metrics[
            metrics["split"] == "validation"
        ]
        .set_index("model")
    )

    r1_rmse = float(
        val.loc["A0_R1", "RMSE"]
    )

    mean_rmse = float(
        val.loc["A1_mean_residual", "RMSE"]
    )

    seasonal_rmse = float(
        val.loc["A2_monthly_climatology", "RMSE"]
    )

    p_rmse = float(
        val.loc["A3_P_OLS", "RMSE"]
    )

    t_rmse = float(
        val.loc["A4_T_OLS", "RMSE"]
    )

    pt_rmse = float(
        val.loc["A5_PT_OLS", "RMSE"]
    )

    strongest_null_rmse = min(
        mean_rmse,
        seasonal_rmse,
    )

    pt_gain_vs_null_pct = (
        (
            strongest_null_rmse
            - pt_rmse
        )
        / strongest_null_rmse
        * 100.0
    )

    pt_beats_mean = bool(
        pt_rmse < mean_rmse
    )

    pt_beats_seasonal = bool(
        pt_rmse < seasonal_rmse
    )

    ready_nonlinear = (
        pt_beats_mean
        and pt_beats_seasonal
    )

    # ------------------------------------------------------
    # Report
    # ------------------------------------------------------

    report_lines = [
        "# VHS-BD1M Phase E4B2A Forcing Ablation",
        "",
        "## Protocol",
        "",
        "- train: 1978-1981",
        "- validation: 1982",
        "- 1983 test evaluated: false",
        "- same 1431/365 support used for every model",
        "- routing backbone: frozen R1",
        "- no routing refit",
        "- no hyperparameter tuning",
        "",
        "## Models",
        "",
        "- A0: routing only",
        "- A1: routing + train mean residual",
        "- A2: routing + train monthly residual climatology",
        "- A3: routing + incremental precipitation OLS",
        "- A4: routing + incremental temperature OLS",
        "- A5: routing + incremental precipitation + temperature OLS",
        "",
        "## Validation RMSE",
        "",
        f"- A0 R1 = {r1_rmse:.6f}",
        f"- A1 mean residual = {mean_rmse:.6f}",
        f"- A2 monthly climatology = {seasonal_rmse:.6f}",
        f"- A3 P-only = {p_rmse:.6f}",
        f"- A4 T-only = {t_rmse:.6f}",
        f"- A5 P+T = {pt_rmse:.6f}",
        "",
        "## Key diagnostic",
        "",
        f"- strongest null RMSE = {strongest_null_rmse:.6f}",
        f"- P+T gain vs strongest null (%) = "
        f"{pt_gain_vs_null_pct:.6f}",
        f"- P+T beats mean-residual null = "
        f"{str(pt_beats_mean).lower()}",
        f"- P+T beats monthly-climatology null = "
        f"{str(pt_beats_seasonal).lower()}",
        "",
        "## Negative-prediction audit",
        "",
    ]

    for name, count in negative_counts.items():
        report_lines.append(
            f"- {name}: {count}"
        )

    report_lines.extend(
        [
            "",
            "## Status",
            "",
            "E4B2A_TEST_1983_EVALUATED=false",
            f"INCREMENTAL_FORCING_BEATS_CONSTANT_NULL="
            f"{str(pt_beats_mean).lower()}",
            f"INCREMENTAL_FORCING_BEATS_SEASONAL_NULL="
            f"{str(pt_beats_seasonal).lower()}",
            f"READY_FOR_E4B2B_NONLINEAR="
            f"{str(ready_nonlinear).lower()}",
        ]
    )

    REPORT_OUT.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("E4B2A complete")

    print(
        f"validation_A0_R1_RMSE={r1_rmse:.6f}"
    )

    print(
        "validation_A1_mean_RMSE="
        f"{mean_rmse:.6f}"
    )

    print(
        "validation_A2_monthly_RMSE="
        f"{seasonal_rmse:.6f}"
    )

    print(
        f"validation_A3_P_RMSE={p_rmse:.6f}"
    )

    print(
        f"validation_A4_T_RMSE={t_rmse:.6f}"
    )

    print(
        f"validation_A5_PT_RMSE={pt_rmse:.6f}"
    )

    print(
        "PT_gain_vs_strongest_null_pct="
        f"{pt_gain_vs_null_pct:.6f}"
    )

    print(
        "READY_FOR_E4B2B_NONLINEAR="
        f"{str(ready_nonlinear).lower()}"
    )

    print(
        "E4B2A_TEST_1983_EVALUATED=false"
    )


if __name__ == "__main__":
    main()