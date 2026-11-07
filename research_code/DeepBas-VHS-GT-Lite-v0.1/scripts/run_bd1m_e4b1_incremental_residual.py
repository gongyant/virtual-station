from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bd1m_physics_routing_model import (
    initialize_steady_state,
    numba_available,
    route_daily,
    route_daily_fast,
    substep_count,
    verify_fast_parity,
)


EXP = ROOT / "outputs/vhs_bd1m/experiments"

DATASET = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
FEATURES_FILE = EXP / "e4b0_incremental_forcing_features.csv"
R1_FIT = EXP / "e4a2_r1_train_fit.csv"

PREDICTIONS = EXP / "e4b1_incremental_residual_predictions.csv"
METRICS = EXP / "e4b1_incremental_residual_metrics.csv"
COEFFICIENTS = EXP / "e4b1_incremental_residual_coefficients.csv"
REPORT = EXP / "e4b1_incremental_residual_report.md"


FEATURES = [
    "P_inc_3d",
    "P_inc_7d",
    "P_inc_30d",
    "T_inc_7d",
    "T_inc_30d",
]


def nse(obs: np.ndarray, pred: np.ndarray) -> float:
    denominator = np.sum((obs - np.mean(obs)) ** 2)
    if denominator == 0:
        return np.nan
    return float(
        1.0 - np.sum((obs - pred) ** 2) / denominator
    )


def kge(obs: np.ndarray, pred: np.ndarray) -> float:
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


def metric_dict(
    obs: np.ndarray,
    pred: np.ndarray,
) -> dict[str, float | int]:
    obs = np.asarray(obs, dtype=float)
    pred = np.asarray(pred, dtype=float)

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
        }

    return {
        "n_samples": len(obs),
        "NSE": nse(obs, pred),
        "KGE": kge(obs, pred),
        "RMSE": float(np.sqrt(np.mean((obs - pred) ** 2))),
        "MAE": float(np.mean(np.abs(obs - pred))),
        "Bias": float(np.mean(pred - obs)),
    }


def main() -> None:
    # ----------------------------------------------------------
    # 1. Read frozen R1 parameter
    # ----------------------------------------------------------

    r1 = pd.read_csv(R1_FIT)

    if len(r1) != 1:
        raise ValueError(
            f"Expected one frozen R1 row, got {len(r1)}"
        )

    tau_global = float(r1.loc[0, "tau_global_days"])

    if not np.isfinite(tau_global) or tau_global <= 0:
        raise ValueError("Invalid frozen R1 tau.")

    tau = np.full(68, tau_global, dtype=float)
    substeps = substep_count(tau)

    if substeps > 576:
        raise ValueError(
            f"R1 requires {substeps} substeps > frozen cap 576."
        )

    # ----------------------------------------------------------
    # 2. Load hydro data
    # ----------------------------------------------------------

    data = pd.read_csv(
        DATASET,
        parse_dates=["date"],
    )

    data = (
        data.sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )

    required = {
        "date",
        "Q_input_byblk",
        "Q_target_dsk",
        "split_candidate",
    }

    if not required.issubset(data.columns):
        raise ValueError(
            f"Dataset missing {required - set(data.columns)}"
        )

    # E4B1 development deliberately stops at validation end.
    # 1983 test is not evaluated in this phase.
    development = data[
        data["date"] <= pd.Timestamp("1982-12-31")
    ].copy()

    expected_dates = pd.date_range(
        "1978-01-01",
        "1982-12-31",
        freq="D",
    )

    if not development["date"].reset_index(drop=True).equals(
        pd.Series(expected_dates, name="date")
    ):
        raise ValueError(
            "1978-1982 development dates are not continuous daily."
        )

    if development["Q_input_byblk"].isna().any():
        raise ValueError(
            "Missing Q_input_byblk in development period."
        )

    # ----------------------------------------------------------
    # 3. Continuous R1 routing: initialize ONCE in 1978
    # ----------------------------------------------------------

    inflow = development["Q_input_byblk"].to_numpy(float)

    initial_storage = initialize_steady_state(
        float(inflow[0]),
        tau,
    )

    if numba_available():
        # One small parity check before using fast path.
        probe = inflow[:30]
        probe_initial = initialize_steady_state(
            float(probe[0]),
            tau,
        )

        verify_fast_parity(
            probe,
            tau,
            substeps,
            probe_initial,
        )

        router = route_daily_fast
        router_name = "route_daily_fast"
    else:
        router = route_daily
        router_name = "route_daily"

    q_route, final_storage, mass_error = router(
        inflow,
        tau,
        substeps,
        initial_storage,
    )

    max_mass_error = float(
        np.max(np.abs(mass_error))
    )

    if max_mass_error > 1e-7:
        raise RuntimeError(
            f"Mass conservation failed: {max_mass_error}"
        )

    development["Q_R1_route"] = q_route

    # ----------------------------------------------------------
    # 4. Merge causal incremental forcing
    # ----------------------------------------------------------

    features = pd.read_csv(
        FEATURES_FILE,
        parse_dates=["date"],
    )

    if features["date"].duplicated().any():
        raise ValueError(
            "Duplicate dates in incremental features."
        )

    missing_features = set(FEATURES) - set(features.columns)

    if missing_features:
        raise ValueError(
            f"Missing forcing features: {missing_features}"
        )

    development = development.merge(
        features[["date", *FEATURES]],
        on="date",
        how="left",
        validate="one_to_one",
    )

    # ----------------------------------------------------------
    # 5. Residual target
    # ----------------------------------------------------------

    development["routing_residual"] = (
        development["Q_target_dsk"]
        - development["Q_R1_route"]
    )

    complete_features = (
        development[FEATURES].notna().all(axis=1)
    )

    target_available = (
        development["Q_target_dsk"].notna()
    )

    train_mask = (
        (development["split_candidate"] == "train")
        & complete_features
        & target_available
    )

    validation_mask = (
        (development["split_candidate"] == "validation")
        & complete_features
        & target_available
    )

    train = development.loc[train_mask].copy()
    validation = development.loc[validation_mask].copy()

    if train.empty or validation.empty:
        raise RuntimeError(
            "Train or validation subset is empty."
        )

    # ----------------------------------------------------------
    # 6. Fixed simple residual model
    # ----------------------------------------------------------

    model = LinearRegression()

    model.fit(
        train[FEATURES],
        train["routing_residual"],
    )

    development["incremental_residual_hat"] = np.nan
    development["Q_E4B1_raw"] = np.nan
    development["Q_E4B1"] = np.nan

    evaluable = complete_features

    residual_hat = model.predict(
        development.loc[evaluable, FEATURES]
    )

    development.loc[
        evaluable,
        "incremental_residual_hat",
    ] = residual_hat

    raw_prediction = (
        development.loc[evaluable, "Q_R1_route"].to_numpy(float)
        + residual_hat
    )

    development.loc[
        evaluable,
        "Q_E4B1_raw",
    ] = raw_prediction

    # Fixed physical non-negativity rule.
    corrected_prediction = np.maximum(
        raw_prediction,
        0.0,
    )

    development.loc[
        evaluable,
        "Q_E4B1",
    ] = corrected_prediction

    negative_before_clip = int(
        np.sum(raw_prediction < 0)
    )

    # ----------------------------------------------------------
    # 7. SAME-SUPPORT metrics
    # ----------------------------------------------------------

    rows = []

    for split_name, mask in [
        ("train", train_mask),
        ("validation", validation_mask),
    ]:
        obs = development.loc[
            mask,
            "Q_target_dsk",
        ].to_numpy(float)

        route_pred = development.loc[
            mask,
            "Q_R1_route",
        ].to_numpy(float)

        corrected = development.loc[
            mask,
            "Q_E4B1",
        ].to_numpy(float)

        route_metrics = metric_dict(
            obs,
            route_pred,
        )

        corrected_metrics = metric_dict(
            obs,
            corrected,
        )

        rows.append(
            {
                "model": "R1_routing_only",
                "split": split_name,
                **route_metrics,
            }
        )

        rows.append(
            {
                "model":
                    "R1_plus_incremental_forcing_OLS",
                "split": split_name,
                **corrected_metrics,
            }
        )

    metrics_df = pd.DataFrame(rows)

    metrics_df.to_csv(
        METRICS,
        index=False,
    )

    # ----------------------------------------------------------
    # 8. Coefficients
    # ----------------------------------------------------------

    coef = pd.DataFrame(
        {
            "feature": FEATURES,
            "coefficient": model.coef_,
        }
    )

    intercept_row = pd.DataFrame(
        {
            "feature": ["INTERCEPT"],
            "coefficient": [model.intercept_],
        }
    )

    coef = pd.concat(
        [intercept_row, coef],
        ignore_index=True,
    )

    coef.to_csv(
        COEFFICIENTS,
        index=False,
    )

    # ----------------------------------------------------------
    # 9. Save only train + validation predictions
    # ----------------------------------------------------------

    output_columns = [
        "date",
        "split_candidate",
        "Q_input_byblk",
        "Q_target_dsk",
        "Q_R1_route",
        *FEATURES,
        "routing_residual",
        "incremental_residual_hat",
        "Q_E4B1_raw",
        "Q_E4B1",
    ]

    development[
        output_columns
    ].to_csv(
        PREDICTIONS,
        index=False,
    )

    # ----------------------------------------------------------
    # 10. Summary
    # ----------------------------------------------------------

    train_r1 = metrics_df[
        (metrics_df.model == "R1_routing_only")
        & (metrics_df.split == "train")
    ].iloc[0]

    train_e4b1 = metrics_df[
        (metrics_df.model ==
         "R1_plus_incremental_forcing_OLS")
        & (metrics_df.split == "train")
    ].iloc[0]

    val_r1 = metrics_df[
        (metrics_df.model == "R1_routing_only")
        & (metrics_df.split == "validation")
    ].iloc[0]

    val_e4b1 = metrics_df[
        (metrics_df.model ==
         "R1_plus_incremental_forcing_OLS")
        & (metrics_df.split == "validation")
    ].iloc[0]

    val_rmse_change_pct = (
        (
            float(val_r1.RMSE)
            - float(val_e4b1.RMSE)
        )
        / float(val_r1.RMSE)
        * 100.0
    )

    val_nse_change = (
        float(val_e4b1.NSE)
        - float(val_r1.NSE)
    )

    report = f"""# VHS-BD1M Phase E4B1 Incremental Forcing Residual Diagnostic

## Protocol

Frozen routing backbone:

- R1 homogeneous 68-reach routing
- tau_global_days = {tau_global:.10g}
- required substeps/day = {substeps}
- router = {router_name}
- initialized once at 1978-01-01
- no state reset at 1982 validation
- max absolute mass error = {max_mass_error:.6g}

Incremental forcing:

- P_inc_3d
- P_inc_7d
- P_inc_30d
- T_inc_7d
- T_inc_30d
- all features are causal and based on t-1 or earlier

Residual definition:

routing_residual(t) = Q_DSK_obs(t) - Q_R1_route(t)

Correction model:

ordinary least squares fitted on 1978-1981 train only.

1983 test metrics are NOT calculated in E4B1.

## Sample counts

- train = {len(train)}
- validation = {len(validation)}

## Train

R1:

- NSE = {float(train_r1.NSE):.6f}
- KGE = {float(train_r1.KGE):.6f}
- RMSE = {float(train_r1.RMSE):.6f}
- MAE = {float(train_r1.MAE):.6f}

R1 + incremental forcing:

- NSE = {float(train_e4b1.NSE):.6f}
- KGE = {float(train_e4b1.KGE):.6f}
- RMSE = {float(train_e4b1.RMSE):.6f}
- MAE = {float(train_e4b1.MAE):.6f}

## Validation 1982

R1:

- NSE = {float(val_r1.NSE):.6f}
- KGE = {float(val_r1.KGE):.6f}
- RMSE = {float(val_r1.RMSE):.6f}
- MAE = {float(val_r1.MAE):.6f}

R1 + incremental forcing:

- NSE = {float(val_e4b1.NSE):.6f}
- KGE = {float(val_e4b1.KGE):.6f}
- RMSE = {float(val_e4b1.RMSE):.6f}
- MAE = {float(val_e4b1.MAE):.6f}

Validation change:

- RMSE reduction (%) = {val_rmse_change_pct:.6f}
- NSE change = {val_nse_change:.6f}

Physical bound:

- negative raw predictions before clipping = {negative_before_clip}

## Status

E4B0_INCREMENTAL_FORCING_FROZEN=true

E4B1_TRAIN_ONLY_FIT=true

E4B1_VALIDATION_EVALUATED=true

E4B1_TEST_1983_EVALUATED=false

READY_FOR_E4B2_ABLATION=true
"""

    REPORT.write_text(
        report,
        encoding="utf-8",
    )

    print("E4B1 complete")
    print(f"tau_global_days={tau_global:.10g}")
    print(f"substeps={substeps}")
    print(f"train_samples={len(train)}")
    print(f"validation_samples={len(validation)}")

    print(
        "validation_R1_RMSE="
        f"{float(val_r1.RMSE):.6f}"
    )

    print(
        "validation_E4B1_RMSE="
        f"{float(val_e4b1.RMSE):.6f}"
    )

    print(
        "validation_RMSE_reduction_pct="
        f"{val_rmse_change_pct:.6f}"
    )

    print(
        "validation_NSE_change="
        f"{val_nse_change:.6f}"
    )

    print(
        "E4B1_TEST_1983_EVALUATED=false"
    )

    print(
        "READY_FOR_E4B2_ABLATION=true"
    )


if __name__ == "__main__":
    main()