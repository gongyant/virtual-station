from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/vhs_bd1m/experiments"

INPUT = EXP / "e4b1_incremental_residual_predictions.csv"

YEAR_OUT = EXP / "e4b2c_yearwise_stability.csv"
BOOT_OUT = EXP / "e4b2c_validation_bootstrap_summary.csv"
REPORT_OUT = EXP / "e4b2c_stability_report.md"


ALL_CAUSAL_FEATURES = [
    "P_inc_3d",
    "P_inc_7d",
    "P_inc_30d",
    "T_inc_7d",
    "T_inc_30d",
]

K_HARMONICS = 6
BOOTSTRAPS = 5000
BLOCK_LENGTH = 30
SEED = 42


def nse(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    den = np.sum((obs - np.mean(obs)) ** 2)

    if den == 0:
        return np.nan

    return float(
        1.0
        - np.sum((obs - pred) ** 2) / den
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
    }


def add_fourier(df):
    out = df.copy()

    doy = out["date"].dt.dayofyear.to_numpy(float)

    year_length = np.where(
        out["date"].dt.is_leap_year.to_numpy(),
        366.0,
        365.0,
    )

    phase = (
        2.0 * np.pi * (doy - 1.0) / year_length
    )

    columns = []

    for k in range(1, K_HARMONICS + 1):
        s = f"season_sin_{k}"
        c = f"season_cos_{k}"

        out[s] = np.sin(k * phase)
        out[c] = np.cos(k * phase)

        columns.extend([s, c])

    return out, columns


def fit_predict_residual(
    train,
    test,
    features,
):
    model = LinearRegression()

    model.fit(
        train[features],
        train["routing_residual"],
    )

    correction = model.predict(
        test[features]
    )

    prediction = (
        test["Q_R1_route"].to_numpy(float)
        + correction
    )

    return np.maximum(prediction, 0.0)


def moving_block_bootstrap(
    obs,
    pred_fourier,
    pred_t7,
):
    obs = np.asarray(obs, float)
    pred_fourier = np.asarray(pred_fourier, float)
    pred_t7 = np.asarray(pred_t7, float)

    n = len(obs)

    if n < BLOCK_LENGTH:
        raise ValueError(
            "Validation series shorter than bootstrap block."
        )

    err_fourier = (
        obs - pred_fourier
    ) ** 2

    err_t7 = (
        obs - pred_t7
    ) ** 2

    rng = np.random.default_rng(SEED)

    possible_starts = np.arange(
        0,
        n - BLOCK_LENGTH + 1,
    )

    deltas = np.empty(
        BOOTSTRAPS,
        dtype=float,
    )

    for b in range(BOOTSTRAPS):

        indices = []

        while len(indices) < n:

            start = int(
                rng.choice(possible_starts)
            )

            indices.extend(
                range(
                    start,
                    start + BLOCK_LENGTH,
                )
            )

        idx = np.asarray(
            indices[:n],
            dtype=int,
        )

        rmse_fourier = np.sqrt(
            np.mean(err_fourier[idx])
        )

        rmse_t7 = np.sqrt(
            np.mean(err_t7[idx])
        )

        # Positive delta means T7 is better.
        deltas[b] = (
            rmse_fourier - rmse_t7
        )

    return {
        "bootstrap_replicates": BOOTSTRAPS,
        "block_length_days": BLOCK_LENGTH,
        "mean_delta_rmse": float(
            np.mean(deltas)
        ),
        "median_delta_rmse": float(
            np.median(deltas)
        ),
        "ci_2_5": float(
            np.percentile(deltas, 2.5)
        ),
        "ci_97_5": float(
            np.percentile(deltas, 97.5)
        ),
        "probability_t7_better": float(
            np.mean(deltas > 0)
        ),
    }


def main():

    df = pd.read_csv(
        INPUT,
        parse_dates=["date"],
    )

    # --------------------------------------------------
    # Absolute holdout guard
    # --------------------------------------------------

    if (
        df["date"]
        >= pd.Timestamp("1983-01-01")
    ).any():
        raise RuntimeError(
            "1983 test data detected. "
            "E4B2C must remain train+validation only."
        )

    required = {
        "date",
        "split_candidate",
        "Q_target_dsk",
        "Q_R1_route",
        "routing_residual",
        *ALL_CAUSAL_FEATURES,
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}"
        )

    # Same support as E4B1/E4B2A.
    complete = (
        df[
            [
                "Q_target_dsk",
                "Q_R1_route",
                "routing_residual",
                *ALL_CAUSAL_FEATURES,
            ]
        ]
        .notna()
        .all(axis=1)
    )

    work = df.loc[complete].copy()

    work, season_features = add_fourier(work)

    train_all = work[
        work["split_candidate"] == "train"
    ].copy()

    validation = work[
        work["split_candidate"] == "validation"
    ].copy()

    if len(train_all) != 1431:
        raise RuntimeError(
            f"Expected 1431 train samples, "
            f"got {len(train_all)}"
        )

    if len(validation) != 365:
        raise RuntimeError(
            f"Expected 365 validation samples, "
            f"got {len(validation)}"
        )

    # --------------------------------------------------
    # PART A:
    # Leave-one-year-out within TRAIN ONLY
    # --------------------------------------------------

    fold_rows = []

    train_years = [1978, 1979, 1980, 1981]

    for holdout_year in train_years:

        fold_train = train_all[
            train_all["date"].dt.year
            != holdout_year
        ].copy()

        fold_test = train_all[
            train_all["date"].dt.year
            == holdout_year
        ].copy()

        if fold_train.empty or fold_test.empty:
            raise RuntimeError(
                f"Empty LOYO fold for {holdout_year}"
            )

        # Monthly climatology null.
        month_means = (
            fold_train.assign(
                month=fold_train["date"].dt.month
            )
            .groupby("month")[
                "routing_residual"
            ]
            .mean()
            .to_dict()
        )

        month_correction = (
            fold_test["date"]
            .dt.month
            .map(month_means)
            .to_numpy(float)
        )

        pred_month = np.maximum(
            fold_test[
                "Q_R1_route"
            ].to_numpy(float)
            + month_correction,
            0.0,
        )

        # Fourier6 seasonal correction.
        pred_fourier = fit_predict_residual(
            fold_train,
            fold_test,
            season_features,
        )

        # T7 raw seasonal proxy.
        pred_t7 = fit_predict_residual(
            fold_train,
            fold_test,
            ["T_inc_7d"],
        )

        obs = fold_test[
            "Q_target_dsk"
        ].to_numpy(float)

        for model_name, prediction in [
            (
                "C1_monthly",
                pred_month,
            ),
            (
                "C2_fourier6",
                pred_fourier,
            ),
            (
                "C3_T7_proxy",
                pred_t7,
            ),
        ]:

            fold_rows.append(
                {
                    "holdout_year":
                        holdout_year,
                    "model":
                        model_name,
                    **metric_dict(
                        obs,
                        prediction,
                    ),
                }
            )

    year_metrics = pd.DataFrame(
        fold_rows
    )

    year_metrics.to_csv(
        YEAR_OUT,
        index=False,
    )

    # --------------------------------------------------
    # LOYO T7 vs Fourier summary
    # --------------------------------------------------

    pivot = year_metrics.pivot(
        index="holdout_year",
        columns="model",
        values="RMSE",
    )

    pivot["T7_gain_pct_vs_Fourier"] = (
        (
            pivot["C2_fourier6"]
            - pivot["C3_T7_proxy"]
        )
        / pivot["C2_fourier6"]
        * 100.0
    )

    fold_wins = int(
        (
            pivot["C3_T7_proxy"]
            < pivot["C2_fourier6"]
        ).sum()
    )

    median_gain_pct = float(
        pivot[
            "T7_gain_pct_vs_Fourier"
        ].median()
    )

    # --------------------------------------------------
    # PART B:
    # Full-train fit, 1982 validation
    # --------------------------------------------------

    pred_val_fourier = fit_predict_residual(
        train_all,
        validation,
        season_features,
    )

    pred_val_t7 = fit_predict_residual(
        train_all,
        validation,
        ["T_inc_7d"],
    )

    val_obs = validation[
        "Q_target_dsk"
    ].to_numpy(float)

    val_fourier_metrics = metric_dict(
        val_obs,
        pred_val_fourier,
    )

    val_t7_metrics = metric_dict(
        val_obs,
        pred_val_t7,
    )

    validation_gain_pct = (
        (
            val_fourier_metrics["RMSE"]
            - val_t7_metrics["RMSE"]
        )
        / val_fourier_metrics["RMSE"]
        * 100.0
    )

    # --------------------------------------------------
    # PART C:
    # Paired 30-day moving-block bootstrap
    # --------------------------------------------------

    bootstrap = moving_block_bootstrap(
        val_obs,
        pred_val_fourier,
        pred_val_t7,
    )

    pd.DataFrame(
        [bootstrap]
    ).to_csv(
        BOOT_OUT,
        index=False,
    )

    # --------------------------------------------------
    # Frozen decision gate
    # --------------------------------------------------

    loyo_stable = bool(
        fold_wins >= 3
        and median_gain_pct >= 5.0
    )

    bootstrap_supported = bool(
        bootstrap["ci_2_5"] > 0.0
    )

    proxy_stable = bool(
        loyo_stable
        and bootstrap_supported
    )

    if proxy_stable:
        recommended_model = (
            "B3_T7_SEASONAL_PROXY"
        )
    else:
        recommended_model = (
            "B2_FOURIER6_SEASONAL"
        )

    # --------------------------------------------------
    # Report
    # --------------------------------------------------

    report = [
        "# VHS-BD1M E4B2C Stability Audit",
        "",
        "## Interpretation boundary",
        "",
        "E4B2B established:",
        "",
        "- TEMPERATURE_SIGNAL_BEYOND_SEASONALITY=false",
        "- T7 may only be interpreted as a seasonal / "
        "hydrologic-state proxy",
        "- no causal temperature claim is permitted",
        "",
        "## Protocol",
        "",
        "- 1983 test evaluated = false",
        "- routing backbone remains frozen R1",
        "- no nonlinear model",
        "- no hyperparameter search",
        "- LOYO is restricted to 1978-1981 train years",
        "- paired bootstrap uses 1982 validation only",
        f"- moving-block length = {BLOCK_LENGTH} days",
        f"- bootstrap replicates = {BOOTSTRAPS}",
        "",
        "## Leave-one-year-out",
        "",
    ]

    for year in train_years:

        row = pivot.loc[year]

        report.extend(
            [
                f"### Holdout {year}",
                "",
                f"- Fourier6 RMSE = "
                f"{float(row['C2_fourier6']):.6f}",
                f"- T7 proxy RMSE = "
                f"{float(row['C3_T7_proxy']):.6f}",
                f"- T7 gain (%) = "
                f"{float(row['T7_gain_pct_vs_Fourier']):.6f}",
                "",
            ]
        )

    report.extend(
        [
            "## LOYO summary",
            "",
            f"- T7 wins = {fold_wins}/4",
            f"- median T7 gain vs Fourier (%) = "
            f"{median_gain_pct:.6f}",
            "",
            "## 1982 validation",
            "",
            f"- Fourier6 RMSE = "
            f"{val_fourier_metrics['RMSE']:.6f}",
            f"- Fourier6 NSE = "
            f"{val_fourier_metrics['NSE']:.6f}",
            f"- T7 RMSE = "
            f"{val_t7_metrics['RMSE']:.6f}",
            f"- T7 NSE = "
            f"{val_t7_metrics['NSE']:.6f}",
            f"- T7 RMSE gain (%) = "
            f"{validation_gain_pct:.6f}",
            "",
            "## 30-day block bootstrap",
            "",
            f"- mean ΔRMSE(Fourier-T7) = "
            f"{bootstrap['mean_delta_rmse']:.6f}",
            f"- median ΔRMSE = "
            f"{bootstrap['median_delta_rmse']:.6f}",
            f"- 95% CI = "
            f"[{bootstrap['ci_2_5']:.6f}, "
            f"{bootstrap['ci_97_5']:.6f}]",
            f"- P(T7 better) = "
            f"{bootstrap['probability_t7_better']:.6f}",
            "",
            "## Predeclared gate",
            "",
            "- LOYO: T7 must beat Fourier in >= 3/4 years",
            "- LOYO median RMSE gain must be >= 5%",
            "- bootstrap 95% CI lower bound must be > 0",
            "",
            "## Status",
            "",
            "E4B2C_TEST_1983_EVALUATED=false",
            f"T7_LOYO_STABLE="
            f"{str(loyo_stable).lower()}",
            f"T7_BOOTSTRAP_SUPPORTED="
            f"{str(bootstrap_supported).lower()}",
            f"T7_SEASONAL_PROXY_STABLE="
            f"{str(proxy_stable).lower()}",
            "TEMPERATURE_SIGNAL_BEYOND_SEASONALITY=false",
            "NONLINEAR_MODEL_JUSTIFIED=false",
            f"RECOMMENDED_FINAL_CORRECTION_MODEL="
            f"{recommended_model}",
            "READY_FOR_E4B3_METHOD_FREEZE=true",
        ]
    )

    REPORT_OUT.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    print("E4B2C complete")

    for year in train_years:
        row = pivot.loc[year]

        print(
            f"LOYO_{year}_T7_gain_pct="
            f"{float(row['T7_gain_pct_vs_Fourier']):.6f}"
        )

    print(
        f"T7_LOYO_wins={fold_wins}/4"
    )

    print(
        "T7_LOYO_median_gain_pct="
        f"{median_gain_pct:.6f}"
    )

    print(
        "validation_T7_gain_pct="
        f"{validation_gain_pct:.6f}"
    )

    print(
        "bootstrap_delta_RMSE_CI="
        f"[{bootstrap['ci_2_5']:.6f},"
        f"{bootstrap['ci_97_5']:.6f}]"
    )

    print(
        "bootstrap_P_T7_better="
        f"{bootstrap['probability_t7_better']:.6f}"
    )

    print(
        "T7_SEASONAL_PROXY_STABLE="
        f"{str(proxy_stable).lower()}"
    )

    print(
        "RECOMMENDED_FINAL_CORRECTION_MODEL="
        f"{recommended_model}"
    )

    print(
        "E4B2C_TEST_1983_EVALUATED=false"
    )


if __name__ == "__main__":
    main()