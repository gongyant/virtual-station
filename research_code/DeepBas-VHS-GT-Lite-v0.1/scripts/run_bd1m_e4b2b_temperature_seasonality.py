from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/vhs_bd1m/experiments"

INPUT = EXP / "e4b1_incremental_residual_predictions.csv"

METRICS_OUT = EXP / "e4b2b_temperature_seasonality_metrics.csv"
COEF_OUT = EXP / "e4b2b_temperature_seasonality_coefficients.csv"
PRED_OUT = EXP / "e4b2b_temperature_seasonality_predictions.csv"
REPORT_OUT = EXP / "e4b2b_temperature_seasonality_report.md"


T_FEATURES = [
    "T_inc_7d",
    "T_inc_30d",
]

K_HARMONICS = 6


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


def metrics(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    mask = np.isfinite(obs) & np.isfinite(pred)
    obs = obs[mask]
    pred = pred[mask]

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
        "Pearson": float(
            np.corrcoef(obs, pred)[0, 1]
        ),
    }


def add_fourier_features(df):
    df = df.copy()

    doy = df["date"].dt.dayofyear.to_numpy(float)

    year_length = np.where(
        df["date"].dt.is_leap_year.to_numpy(),
        366.0,
        365.0,
    )

    phase = (
        2.0
        * np.pi
        * (doy - 1.0)
        / year_length
    )

    cols = []

    for k in range(1, K_HARMONICS + 1):
        sin_name = f"season_sin_{k}"
        cos_name = f"season_cos_{k}"

        df[sin_name] = np.sin(k * phase)
        df[cos_name] = np.cos(k * phase)

        cols.extend(
            [sin_name, cos_name]
        )

    return df, cols


def fit_residual_model(
    work,
    train_mask,
    features,
    model_name,
    coef_rows,
):
    model = LinearRegression()

    model.fit(
        work.loc[train_mask, features],
        work.loc[
            train_mask,
            "routing_residual",
        ],
    )

    correction = model.predict(
        work[features]
    )

    coef_rows.append(
        {
            "model": model_name,
            "feature": "INTERCEPT",
            "coefficient": float(
                model.intercept_
            ),
        }
    )

    for feature, coefficient in zip(
        features,
        model.coef_,
    ):
        coef_rows.append(
            {
                "model": model_name,
                "feature": feature,
                "coefficient": float(
                    coefficient
                ),
            }
        )

    return correction


def main():

    df = pd.read_csv(
        INPUT,
        parse_dates=["date"],
    )

    # --------------------------------------------------
    # Absolute test-data guard
    # --------------------------------------------------

    if (
        df["date"]
        >= pd.Timestamp("1983-01-01")
    ).any():
        raise RuntimeError(
            "1983 test data detected. "
            "E4B2B must remain train+validation only."
        )

    required = {
        "date",
        "split_candidate",
        "Q_target_dsk",
        "Q_R1_route",
        "routing_residual",
        "T_inc_7d",
        "T_inc_30d",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}"
        )

    complete = (
        df[
            [
                "Q_target_dsk",
                "Q_R1_route",
                "routing_residual",
                *T_FEATURES,
            ]
        ]
        .notna()
        .all(axis=1)
    )

    work = df.loc[complete].copy()

    if len(
        work[
            work["split_candidate"] == "train"
        ]
    ) != 1431:
        raise RuntimeError(
            "Unexpected train support."
        )

    if len(
        work[
            work["split_candidate"]
            == "validation"
        ]
    ) != 365:
        raise RuntimeError(
            "Unexpected validation support."
        )

    train_mask = (
        work["split_candidate"] == "train"
    )

    validation_mask = (
        work["split_candidate"]
        == "validation"
    )

    # --------------------------------------------------
    # Seasonal Fourier design
    # --------------------------------------------------

    work, season_features = (
        add_fourier_features(work)
    )

    # --------------------------------------------------
    # Temperature seasonal decomposition
    #
    # Fit seasonal expectation using TRAIN ONLY.
    # --------------------------------------------------

    temp_season_coefficients = []

    for temperature_feature in T_FEATURES:

        seasonal_model = LinearRegression()

        seasonal_model.fit(
            work.loc[
                train_mask,
                season_features,
            ],
            work.loc[
                train_mask,
                temperature_feature,
            ],
        )

        expected_temperature = (
            seasonal_model.predict(
                work[season_features]
            )
        )

        anomaly_name = (
            f"{temperature_feature}_anom"
        )

        work[anomaly_name] = (
            work[temperature_feature]
            - expected_temperature
        )

        temp_season_coefficients.append(
            {
                "model":
                    f"{temperature_feature}_season",
                "feature": "INTERCEPT",
                "coefficient":
                    float(
                        seasonal_model.intercept_
                    ),
            }
        )

        for feature, coefficient in zip(
            season_features,
            seasonal_model.coef_,
        ):
            temp_season_coefficients.append(
                {
                    "model":
                        f"{temperature_feature}_season",
                    "feature": feature,
                    "coefficient":
                        float(coefficient),
                }
            )

    # --------------------------------------------------
    # Models
    # --------------------------------------------------

    coef_rows = []

    # B0 routing only
    work["B0_R1"] = work["Q_R1_route"]

    # B1 monthly residual climatology
    train_month = (
        work.loc[
            train_mask,
            ["date", "routing_residual"]
        ]
        .copy()
    )

    train_month["month"] = (
        train_month["date"].dt.month
    )

    monthly_mean = (
        train_month
        .groupby("month")[
            "routing_residual"
        ]
        .mean()
        .to_dict()
    )

    work["month"] = work["date"].dt.month

    work["B1_monthly"] = (
        work["Q_R1_route"]
        + work["month"].map(monthly_mean)
    )

    # B2 strong smooth seasonal null
    season_correction = fit_residual_model(
        work,
        train_mask,
        season_features,
        "B2_fourier6",
        coef_rows,
    )

    work["B2_fourier6"] = (
        work["Q_R1_route"]
        + season_correction
    )

    # B3 T7 only
    correction = fit_residual_model(
        work,
        train_mask,
        ["T_inc_7d"],
        "B3_T7",
        coef_rows,
    )

    work["B3_T7"] = (
        work["Q_R1_route"] + correction
    )

    # B4 T30 only
    correction = fit_residual_model(
        work,
        train_mask,
        ["T_inc_30d"],
        "B4_T30",
        coef_rows,
    )

    work["B4_T30"] = (
        work["Q_R1_route"] + correction
    )

    # B5 T7 + T30 raw
    correction = fit_residual_model(
        work,
        train_mask,
        [
            "T_inc_7d",
            "T_inc_30d",
        ],
        "B5_T7_T30",
        coef_rows,
    )

    work["B5_T7_T30"] = (
        work["Q_R1_route"] + correction
    )

    # B6 season + T7 anomaly
    features = (
        season_features
        + ["T_inc_7d_anom"]
    )

    correction = fit_residual_model(
        work,
        train_mask,
        features,
        "B6_season_T7anom",
        coef_rows,
    )

    work["B6_season_T7anom"] = (
        work["Q_R1_route"] + correction
    )

    # B7 season + T30 anomaly
    features = (
        season_features
        + ["T_inc_30d_anom"]
    )

    correction = fit_residual_model(
        work,
        train_mask,
        features,
        "B7_season_T30anom",
        coef_rows,
    )

    work["B7_season_T30anom"] = (
        work["Q_R1_route"] + correction
    )

    # B8 season + both anomalies
    features = (
        season_features
        + [
            "T_inc_7d_anom",
            "T_inc_30d_anom",
        ]
    )

    correction = fit_residual_model(
        work,
        train_mask,
        features,
        "B8_season_Tboth_anom",
        coef_rows,
    )

    work["B8_season_Tboth_anom"] = (
        work["Q_R1_route"] + correction
    )

    model_columns = [
        "B0_R1",
        "B1_monthly",
        "B2_fourier6",
        "B3_T7",
        "B4_T30",
        "B5_T7_T30",
        "B6_season_T7anom",
        "B7_season_T30anom",
        "B8_season_Tboth_anom",
    ]

    # --------------------------------------------------
    # Physical non-negativity + audit
    # --------------------------------------------------

    negative_counts = {}

    for col in model_columns:

        negative_counts[col] = int(
            (work[col] < 0).sum()
        )

        work[col] = np.maximum(
            work[col],
            0.0,
        )

    # --------------------------------------------------
    # Metrics
    # --------------------------------------------------

    rows = []

    for split_name, mask in [
        ("train", train_mask),
        ("validation", validation_mask),
    ]:

        subset = work.loc[mask]

        obs = subset[
            "Q_target_dsk"
        ].to_numpy(float)

        for model_name in model_columns:

            pred = subset[
                model_name
            ].to_numpy(float)

            rows.append(
                {
                    "model": model_name,
                    "split": split_name,
                    **metrics(obs, pred),
                }
            )

    metrics_df = pd.DataFrame(rows)

    metrics_df.to_csv(
        METRICS_OUT,
        index=False,
    )

    pd.DataFrame(
        coef_rows
        + temp_season_coefficients
    ).to_csv(
        COEF_OUT,
        index=False,
    )

    # --------------------------------------------------
    # Temperature correlation audit
    # --------------------------------------------------

    train_t_corr = float(
        work.loc[
            train_mask,
            [
                "T_inc_7d",
                "T_inc_30d",
            ],
        ]
        .corr()
        .iloc[0, 1]
    )

    val_t_corr = float(
        work.loc[
            validation_mask,
            [
                "T_inc_7d",
                "T_inc_30d",
            ],
        ]
        .corr()
        .iloc[0, 1]
    )

    # --------------------------------------------------
    # Decision
    # --------------------------------------------------

    validation_metrics = (
        metrics_df[
            metrics_df["split"]
            == "validation"
        ]
        .set_index("model")
    )

    null_candidates = [
        "B1_monthly",
        "B2_fourier6",
    ]

    anomaly_candidates = [
        "B6_season_T7anom",
        "B7_season_T30anom",
        "B8_season_Tboth_anom",
    ]

    best_null = min(
        null_candidates,
        key=lambda x:
            float(
                validation_metrics.loc[
                    x,
                    "RMSE",
                ]
            ),
    )

    best_anomaly = min(
        anomaly_candidates,
        key=lambda x:
            float(
                validation_metrics.loc[
                    x,
                    "RMSE",
                ]
            ),
    )

    null_rmse = float(
        validation_metrics.loc[
            best_null,
            "RMSE",
        ]
    )

    anomaly_rmse = float(
        validation_metrics.loc[
            best_anomaly,
            "RMSE",
        ]
    )

    null_nse = float(
        validation_metrics.loc[
            best_null,
            "NSE",
        ]
    )

    anomaly_nse = float(
        validation_metrics.loc[
            best_anomaly,
            "NSE",
        ]
    )

    rmse_gain_pct = (
        (null_rmse - anomaly_rmse)
        / null_rmse
        * 100.0
    )

    nse_gain = (
        anomaly_nse - null_nse
    )

    # Predeclared practical diagnostic gate.
    beyond_seasonality = bool(
        rmse_gain_pct >= 5.0
        and nse_gain >= 0.05
    )

    # --------------------------------------------------
    # Save predictions
    # --------------------------------------------------

    work[
        [
            "date",
            "split_candidate",
            "Q_target_dsk",
            "Q_R1_route",
            "routing_residual",
            "T_inc_7d",
            "T_inc_30d",
            "T_inc_7d_anom",
            "T_inc_30d_anom",
            *model_columns,
        ]
    ].to_csv(
        PRED_OUT,
        index=False,
    )

    # --------------------------------------------------
    # Report
    # --------------------------------------------------

    report = [
        "# VHS-BD1M E4B2B Temperature vs Seasonality",
        "",
        "## Protocol",
        "",
        "- train = 1978-1981",
        "- validation = 1982",
        "- test 1983 evaluated = false",
        "- frozen R1 routing backbone",
        "- no routing refit",
        "- no nonlinear model",
        "- temperature seasonal decomposition fitted on train only",
        f"- Fourier harmonics = {K_HARMONICS}",
        "",
        "## Temperature collinearity",
        "",
        f"- train corr(T7,T30) = {train_t_corr:.6f}",
        f"- validation corr(T7,T30) = {val_t_corr:.6f}",
        "",
        "## Validation",
        "",
    ]

    for model_name in model_columns:

        row = validation_metrics.loc[
            model_name
        ]

        report.extend(
            [
                f"### {model_name}",
                "",
                f"- NSE = {float(row.NSE):.6f}",
                f"- KGE = {float(row.KGE):.6f}",
                f"- RMSE = {float(row.RMSE):.6f}",
                f"- MAE = {float(row.MAE):.6f}",
                f"- Bias = {float(row.Bias):.6f}",
                "",
            ]
        )

    report.extend(
        [
            "## Key diagnostic",
            "",
            f"- strongest seasonal null = {best_null}",
            f"- strongest seasonal null RMSE = {null_rmse:.6f}",
            f"- best temperature-anomaly model = {best_anomaly}",
            f"- anomaly RMSE = {anomaly_rmse:.6f}",
            f"- RMSE gain vs seasonal null (%) = {rmse_gain_pct:.6f}",
            f"- NSE gain vs seasonal null = {nse_gain:.6f}",
            "",
            "Practical gate fixed before this experiment:",
            "",
            "- RMSE improvement >= 5%",
            "- NSE improvement >= 0.05",
            "",
            "## Status",
            "",
            "E4B2B_TEST_1983_EVALUATED=false",
            f"TEMPERATURE_SIGNAL_BEYOND_SEASONALITY="
            f"{str(beyond_seasonality).lower()}",
            "READY_FOR_E4B2C_STABILITY=true",
        ]
    )

    REPORT_OUT.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    print("E4B2B complete")

    for name in model_columns:

        rmse = float(
            validation_metrics.loc[
                name,
                "RMSE",
            ]
        )

        print(
            f"validation_{name}_RMSE="
            f"{rmse:.6f}"
        )

    print(
        f"train_T7_T30_corr={train_t_corr:.6f}"
    )

    print(
        f"validation_T7_T30_corr={val_t_corr:.6f}"
    )

    print(
        f"strongest_seasonal_null={best_null}"
    )

    print(
        f"best_temperature_anomaly_model="
        f"{best_anomaly}"
    )

    print(
        "temperature_anomaly_RMSE_gain_pct="
        f"{rmse_gain_pct:.6f}"
    )

    print(
        "temperature_anomaly_NSE_gain="
        f"{nse_gain:.6f}"
    )

    print(
        "TEMPERATURE_SIGNAL_BEYOND_SEASONALITY="
        f"{str(beyond_seasonality).lower()}"
    )

    print(
        "E4B2B_TEST_1983_EVALUATED=false"
    )


if __name__ == "__main__":
    main()