from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

EXP = ROOT / "outputs/vhs_bd1m/experiments"
PAPER = ROOT / "outputs/vhs_bd1m/paper"

PAPER.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Source files
# =========================================================

FILES = {
    "e4a2_r1":
        EXP / "e4a2_r1_train_fit.csv",

    "e4a2_r2":
        EXP / "e4a2_r2_multistart_train_fit.csv",

    "e4a2_identifiability":
        EXP / "e4a2_parameter_identifiability_report.md",

    "e4b1_metrics":
        EXP / "e4b1_incremental_residual_metrics.csv",

    "e4b2a":
        EXP / "e4b2a_forcing_ablation_metrics.csv",

    "e4b2b":
        EXP / "e4b2b_temperature_seasonality_metrics.csv",

    "e4b2b_report":
        EXP / "e4b2b_temperature_seasonality_report.md",

    "e4b2c_yearwise":
        EXP / "e4b2c_yearwise_stability.csv",

    "e4b2c_bootstrap":
        EXP / "e4b2c_validation_bootstrap_summary.csv",

    "e4b2c_report":
        EXP / "e4b2c_stability_report.md",

    "freeze":
        EXP / "e4b3_method_freeze.json",

    "freeze_report":
        EXP / "e4b3_method_freeze_report.md",

    "e4c":
        EXP / "e4c_1983_holdout_metrics.csv",

    "e4c_report":
        EXP / "e4c_1983_holdout_report.md",

    "e4d1":
        EXP / "e4d1_external_monthly_metrics.csv",

    "e4d1_report":
        EXP / "e4d1_external_monthly_report.md",

    "external_workbook":
        ROOT / "data/raw/runoff/Q-dsk-byblk.xlsx",
}


MASTER_OUT = PAPER / "e5a_master_results.csv"
KEY_OUT = PAPER / "e5a_key_results.csv"
CLAIM_OUT = PAPER / "e5a_claim_ledger.csv"

MANIFEST_OUT = (
    PAPER
    / "e5a_reproducibility_manifest.json"
)

SUMMARY_OUT = PAPER / "e5a_summary.md"


# =========================================================
# Utilities
# =========================================================

def fail(message: str) -> None:
    raise RuntimeError(
        f"E5A BUILD FAILED: {message}"
    )


def sha256(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as f:

        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def as_bool(series: pd.Series) -> pd.Series:

    return (
        series
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(
            [
                "true",
                "1",
                "yes",
            ]
        )
    )


def fvalue(
    row,
    name,
):
    if name not in row.index:
        return np.nan

    value = pd.to_numeric(
        pd.Series([row[name]]),
        errors="coerce",
    ).iloc[0]

    if pd.isna(value):
        return np.nan

    return float(value)


def ivalue(
    row,
    candidates,
):

    for name in candidates:

        if name in row.index:

            value = pd.to_numeric(
                pd.Series([row[name]]),
                errors="coerce",
            ).iloc[0]

            if not pd.isna(value):
                return int(value)

    return None


def require_model_prefix(
    df: pd.DataFrame,
    prefix: str,
    split: str | None = None,
):

    work = df.copy()

    if split is not None:

        if "split" not in work.columns:
            fail(
                f"split column absent "
                f"while finding {prefix}"
            )

        work = work[
            work["split"].astype(str)
            == split
        ]

    rows = work[
        work["model"]
        .astype(str)
        .str.startswith(prefix)
    ]

    if len(rows) != 1:

        fail(
            f"Expected exactly one row for "
            f"model prefix {prefix}, split={split}; "
            f"got {len(rows)}"
        )

    return rows.iloc[0]


def require_model_exact(
    df: pd.DataFrame,
    model: str,
    split: str | None = None,
):

    work = df.copy()

    if split is not None:
        work = work[
            work["split"].astype(str)
            == split
        ]

    rows = work[
        work["model"].astype(str)
        == model
    ]

    if len(rows) != 1:

        fail(
            f"Expected exactly one row for "
            f"{model}, split={split}; "
            f"got {len(rows)}"
        )

    return rows.iloc[0]


def pct_improvement(
    baseline: float,
    candidate: float,
) -> float:

    return (
        (baseline - candidate)
        / baseline
        * 100.0
    )


# =========================================================
# 0. Source existence gate
# =========================================================

for key, path in FILES.items():

    if not path.exists():
        fail(
            f"Required source missing: "
            f"{key} -> {path}"
        )


# =========================================================
# 1. Freeze compliance gates
# =========================================================

freeze = json.loads(
    FILES["freeze"].read_text(
        encoding="utf-8"
    )
)

if freeze.get(
    "freeze_status"
) is not True:
    fail("freeze_status != true")


final_model = (
    freeze[
        "final_correction_model"
    ]["name"]
)

if final_model != "B2_FOURIER6_SEASONAL":
    fail(
        f"Unexpected final model: "
        f"{final_model}"
    )


harmonics = int(
    freeze[
        "final_correction_model"
    ]["harmonics"]
)

if harmonics != 6:
    fail(
        f"Unexpected harmonic count: "
        f"{harmonics}"
    )


if (
    freeze[
        "final_correction_model"
    ][
        "refit_using_validation_before_test"
    ]
    is not False
):
    fail(
        "Validation refit before test "
        "must remain false."
    )


tau_global_days = float(
    freeze[
        "routing_backbone"
    ]["tau_global_days"]
)

required_substeps = int(
    freeze[
        "routing_backbone"
    ][
        "required_substeps_per_day"
    ]
)


# Text-level scientific gates

b2b_report = FILES[
    "e4b2b_report"
].read_text(
    encoding="utf-8"
)

if (
    "TEMPERATURE_SIGNAL_BEYOND_SEASONALITY=false"
    not in b2b_report
):
    fail(
        "Temperature-vs-seasonality gate changed."
    )


b2c_report = FILES[
    "e4b2c_report"
].read_text(
    encoding="utf-8"
)

required_b2c = [
    "T7_SEASONAL_PROXY_STABLE=false",
    (
        "RECOMMENDED_FINAL_CORRECTION_MODEL="
        "B2_FOURIER6_SEASONAL"
    ),
    "E4B2C_TEST_1983_EVALUATED=false",
]

for item in required_b2c:

    if item not in b2c_report:
        fail(
            f"E4B2C gate missing: {item}"
        )


e4c_report = FILES[
    "e4c_report"
].read_text(
    encoding="utf-8"
)

if (
    "E4C_TEST_USED_FOR_MODEL_SELECTION=false"
    not in e4c_report
):
    fail(
        "1983 test-selection gate changed."
    )


e4d1_report = FILES[
    "e4d1_report"
].read_text(
    encoding="utf-8"
)

required_d1 = [
    "E4D1_EXTERNAL_MONTHLY_SERIES_EVALUATED=true",
    "E4D1_PRIMARY_PROVENANCE_RESOLVED=false",
    "E4D1_OFFICIAL_INDEPENDENT_VALIDATION=false",
    "E4D1_MODEL_CHANGED=false",
]

for item in required_d1:

    if item not in e4d1_report:
        fail(
            f"E4D1 gate missing: {item}"
        )


# =========================================================
# 2. Load source metric tables
# =========================================================

r1_df = pd.read_csv(
    FILES["e4a2_r1"]
)

r2_df = pd.read_csv(
    FILES["e4a2_r2"]
)

b1 = pd.read_csv(
    FILES["e4b1_metrics"]
)

b2a = pd.read_csv(
    FILES["e4b2a"]
)

b2b = pd.read_csv(
    FILES["e4b2b"]
)

b2c = pd.read_csv(
    FILES["e4b2c_yearwise"]
)

boot = pd.read_csv(
    FILES["e4b2c_bootstrap"]
)

e4c = pd.read_csv(
    FILES["e4c"]
)

e4d1 = pd.read_csv(
    FILES["e4d1"]
)


# =========================================================
# 3. E4A2 routing-only evidence
# =========================================================

if len(r1_df) != 1:
    fail(
        "E4A2 R1 must contain exactly one row."
    )

r1 = r1_df.iloc[0]

r1_rmse = float(
    r1["train_RMSE"]
)


if "numerically_admissible" not in r2_df.columns:
    fail(
        "R2 numerically_admissible column missing."
    )

r2_ok = r2_df[
    as_bool(
        r2_df[
            "numerically_admissible"
        ]
    )
].copy()

r2_ok["train_RMSE"] = pd.to_numeric(
    r2_ok["train_RMSE"],
    errors="coerce",
)

r2_ok = r2_ok[
    np.isfinite(
        r2_ok["train_RMSE"]
    )
].copy()

if r2_ok.empty:
    fail(
        "No admissible R2 solution."
    )

r2_best = (
    r2_ok
    .sort_values(
        "train_RMSE"
    )
    .iloc[0]
)

r2_rmse = float(
    r2_best["train_RMSE"]
)

r2_gain_pct = pct_improvement(
    r1_rmse,
    r2_rmse,
)


# =========================================================
# 4. Development validation evidence
# =========================================================

# E4B2A — match by A0..A5 prefixes,
# avoiding dependence on long exact labels.

A0 = require_model_prefix(
    b2a,
    "A0",
    "validation",
)

A1 = require_model_prefix(
    b2a,
    "A1",
    "validation",
)

A2 = require_model_prefix(
    b2a,
    "A2",
    "validation",
)

A3 = require_model_prefix(
    b2a,
    "A3",
    "validation",
)

A4 = require_model_prefix(
    b2a,
    "A4",
    "validation",
)

A5 = require_model_prefix(
    b2a,
    "A5",
    "validation",
)


# E4B2B

B2 = require_model_exact(
    b2b,
    "B2_fourier6",
    "validation",
)

B3 = require_model_exact(
    b2b,
    "B3_T7",
    "validation",
)


anomaly_rows = b2b[
    (
        b2b["split"].astype(str)
        == "validation"
    )
    &
    (
        b2b["model"]
        .astype(str)
        .str.startswith(
            (
                "B6_",
                "B7_",
                "B8_",
            )
        )
    )
].copy()

if anomaly_rows.empty:
    fail(
        "Temperature anomaly models missing."
    )

anomaly_rows["RMSE"] = pd.to_numeric(
    anomaly_rows["RMSE"],
    errors="coerce",
)

best_anomaly = (
    anomaly_rows
    .sort_values("RMSE")
    .iloc[0]
)

temperature_anomaly_gain_pct = (
    pct_improvement(
        float(B2["RMSE"]),
        float(best_anomaly["RMSE"]),
    )
)


# =========================================================
# 5. E4B2C stability evidence
# =========================================================

years = sorted(
    int(x)
    for x in
    pd.to_numeric(
        b2c["holdout_year"],
        errors="coerce",
    )
    .dropna()
    .unique()
)

if years != [
    1978,
    1979,
    1980,
    1981,
]:
    fail(
        f"Unexpected LOYO years: {years}"
    )


loyo_gains = []

for year in years:

    g = b2c[
        pd.to_numeric(
            b2c["holdout_year"],
            errors="coerce",
        )
        == year
    ]

    fourier = g[
        g["model"].astype(str)
        == "C2_fourier6"
    ]

    t7 = g[
        g["model"].astype(str)
        == "C3_T7_proxy"
    ]

    if len(fourier) != 1 or len(t7) != 1:
        fail(
            f"LOYO model rows invalid "
            f"for year {year}"
        )

    f_rmse = float(
        fourier.iloc[0]["RMSE"]
    )

    t_rmse = float(
        t7.iloc[0]["RMSE"]
    )

    gain = pct_improvement(
        f_rmse,
        t_rmse,
    )

    loyo_gains.append(
        {
            "year": year,
            "gain_pct": gain,
            "T7_better": t_rmse < f_rmse,
        }
    )


loyo_gain_values = [
    x["gain_pct"]
    for x in loyo_gains
]

loyo_wins = sum(
    x["T7_better"]
    for x in loyo_gains
)

loyo_median_gain = float(
    np.median(
        loyo_gain_values
    )
)


if len(boot) != 1:
    fail(
        "Bootstrap summary must have one row."
    )

boot_row = boot.iloc[0]

bootstrap_ci_low = float(
    boot_row["ci_2_5"]
)

bootstrap_ci_high = float(
    boot_row["ci_97_5"]
)

prob_cols = [
    c
    for c in boot.columns
    if c.lower().startswith("prob")
]

bootstrap_prob_t7_better = (
    float(
        boot_row[
            prob_cols[0]
        ]
    )
    if prob_cols
    else np.nan
)


# =========================================================
# 6. E4C fixed 1983 holdout
# =========================================================

C_R1 = require_model_exact(
    e4c,
    "R1_ROUTING_ONLY",
    "test_1983",
)

C_MONTH = require_model_exact(
    e4c,
    "MONTHLY_RESIDUAL_CLIMATOLOGY",
    "test_1983",
)

C_FINAL = require_model_exact(
    e4c,
    "B2_FOURIER6_SEASONAL_FINAL",
    "test_1983",
)


if int(C_FINAL["n_samples"]) != 365:
    fail(
        "E4C test must contain 365 samples."
    )


c_gain_pct = pct_improvement(
    float(C_R1["RMSE"]),
    float(C_FINAL["RMSE"]),
)


# =========================================================
# 7. E4D1 external monthly consistency
# =========================================================

D_LABEL = require_model_exact(
    e4d1,
    "DAILY_LABEL_MONTHLY_MEAN",
)

D_R1 = require_model_exact(
    e4d1,
    "R1_ROUTING_ONLY_MONTHLY",
)

D_MONTH = require_model_exact(
    e4d1,
    "MONTHLY_CLIMATOLOGY_MONTHLY",
)

D_FINAL = require_model_exact(
    e4d1,
    "FOURIER6_FINAL_MONTHLY",
)


if int(D_FINAL["n_months"]) != 12:
    fail(
        "E4D1 must contain exactly 12 months."
    )


d_gain_pct = pct_improvement(
    float(D_R1["RMSE"]),
    float(D_FINAL["RMSE"]),
)


# =========================================================
# 8. Build MASTER RESULTS
# =========================================================

master_rows = []


def add_master(
    *,
    phase,
    experiment,
    model,
    model_role,
    split,
    period,
    temporal_scale,
    observation_source,
    evaluation_role,
    n_samples=None,
    NSE=np.nan,
    KGE=np.nan,
    RMSE=np.nan,
    MAE=np.nan,
    Bias=np.nan,
    Pearson=np.nan,
    baseline_model="",
    RMSE_gain_vs_baseline_pct=np.nan,
    selected_final_model=False,
    used_for_model_selection=False,
    provenance_level="",
    claim_level="",
    source_file="",
    notes="",
):

    master_rows.append(
        {
            "phase": phase,
            "experiment": experiment,
            "model": model,
            "model_role": model_role,
            "split": split,
            "period": period,
            "temporal_scale": temporal_scale,
            "observation_source":
                observation_source,
            "evaluation_role":
                evaluation_role,
            "n_samples": n_samples,
            "NSE": NSE,
            "KGE": KGE,
            "RMSE": RMSE,
            "MAE": MAE,
            "Bias": Bias,
            "Pearson": Pearson,
            "baseline_model":
                baseline_model,
            "RMSE_gain_vs_baseline_pct":
                RMSE_gain_vs_baseline_pct,
            "selected_final_model":
                selected_final_model,
            "used_for_model_selection":
                used_for_model_selection,
            "provenance_level":
                provenance_level,
            "claim_level":
                claim_level,
            "source_file":
                source_file,
            "notes": notes,
        }
    )


# E4A2

add_master(
    phase="E4A2",
    experiment="routing_train_only",
    model="R1_HOMOGENEOUS_68_REACH",
    model_role="routing_baseline",
    split="train",
    period="1978-1981",
    temporal_scale="daily",
    observation_source="existing_daily_DSK",
    evaluation_role="mechanism_diagnostic",
    RMSE=r1_rmse,
    used_for_model_selection=True,
    provenance_level="existing_daily_observation",
    claim_level="diagnostic",
    source_file="e4a2_r1_train_fit.csv",
    notes=(
        "One shared routing residence-time parameter."
    ),
)

add_master(
    phase="E4A2",
    experiment="routing_train_only",
    model="R2_BEST_MULTISTART",
    model_role="routing_heterogeneity_candidate",
    split="train",
    period="1978-1981",
    temporal_scale="daily",
    observation_source="existing_daily_DSK",
    evaluation_role="mechanism_diagnostic",
    RMSE=r2_rmse,
    baseline_model="R1_HOMOGENEOUS_68_REACH",
    RMSE_gain_vs_baseline_pct=r2_gain_pct,
    used_for_model_selection=True,
    provenance_level="existing_daily_observation",
    claim_level="diagnostic",
    source_file="e4a2_r2_multistart_train_fit.csv",
    notes=(
        "Best numerically admissible multistart R2; "
        "parameters not interpreted as physical laws."
    ),
)


# Generic metric-table loader

def append_metric_table(
    df,
    *,
    phase,
    experiment,
    temporal_scale,
    observation_source,
    evaluation_role,
    provenance_level,
    claim_level,
    source_file,
    default_period,
    used_for_model_selection,
):

    for _, row in df.iterrows():

        model = str(
            row.get(
                "model",
                "UNKNOWN",
            )
        )

        split = str(
            row.get(
                "split",
                "",
            )
        )

        period = default_period

        if (
            "holdout_year"
            in row.index
            and not pd.isna(
                row["holdout_year"]
            )
        ):
            period = str(
                int(
                    float(
                        row[
                            "holdout_year"
                        ]
                    )
                )
            )

            split = "train_LOYO"

        n_samples = ivalue(
            row,
            [
                "n_samples",
                "n_months",
                "n",
            ],
        )

        add_master(
            phase=phase,
            experiment=experiment,
            model=model,
            model_role="candidate",
            split=split,
            period=period,
            temporal_scale=temporal_scale,
            observation_source=
                observation_source,
            evaluation_role=
                evaluation_role,
            n_samples=n_samples,
            NSE=fvalue(row, "NSE"),
            KGE=fvalue(row, "KGE"),
            RMSE=fvalue(row, "RMSE"),
            MAE=fvalue(row, "MAE"),
            Bias=fvalue(row, "Bias"),
            Pearson=fvalue(
                row,
                "Pearson",
            ),
            selected_final_model=(
                model
                in {
                    "B2_fourier6",
                    "B2_FOURIER6_SEASONAL_FINAL",
                    "FOURIER6_FINAL_MONTHLY",
                }
            ),
            used_for_model_selection=
                used_for_model_selection,
            provenance_level=
                provenance_level,
            claim_level=claim_level,
            source_file=source_file,
        )


append_metric_table(
    b1,
    phase="E4B1",
    experiment="incremental_residual_diagnostic",
    temporal_scale="daily",
    observation_source="existing_daily_DSK",
    evaluation_role="development_diagnostic",
    provenance_level="existing_daily_observation",
    claim_level="diagnostic",
    source_file="e4b1_incremental_residual_metrics.csv",
    default_period="1978-1982",
    used_for_model_selection=True,
)

append_metric_table(
    b2a,
    phase="E4B2A",
    experiment="forcing_ablation",
    temporal_scale="daily",
    observation_source="existing_daily_DSK",
    evaluation_role="development_validation",
    provenance_level="existing_daily_observation",
    claim_level="development_evidence",
    source_file="e4b2a_forcing_ablation_metrics.csv",
    default_period="1978-1982",
    used_for_model_selection=True,
)

append_metric_table(
    b2b,
    phase="E4B2B",
    experiment="temperature_vs_seasonality",
    temporal_scale="daily",
    observation_source="existing_daily_DSK",
    evaluation_role="development_validation",
    provenance_level="existing_daily_observation",
    claim_level="development_evidence",
    source_file="e4b2b_temperature_seasonality_metrics.csv",
    default_period="1978-1982",
    used_for_model_selection=True,
)

append_metric_table(
    b2c,
    phase="E4B2C",
    experiment="train_only_LOYO_stability",
    temporal_scale="daily",
    observation_source="existing_daily_DSK",
    evaluation_role="train_only_stability",
    provenance_level="existing_daily_observation",
    claim_level="stability_evidence",
    source_file="e4b2c_yearwise_stability.csv",
    default_period="1978-1981",
    used_for_model_selection=True,
)

append_metric_table(
    e4c,
    phase="E4C",
    experiment="fixed_1983_holdout",
    temporal_scale="daily",
    observation_source="existing_daily_DSK",
    evaluation_role="frozen_holdout",
    provenance_level="existing_daily_observation",
    claim_level="holdout_evidence",
    source_file="e4c_1983_holdout_metrics.csv",
    default_period="1983",
    used_for_model_selection=False,
)

append_metric_table(
    e4d1,
    phase="E4D1",
    experiment="external_monthly_consistency",
    temporal_scale="monthly",
    observation_source="Q-dsk-byblk.xlsx_DSK",
    evaluation_role="external_consistency",
    provenance_level=(
        "numerically_distinct_"
        "primary_provenance_unresolved"
    ),
    claim_level="external_consistency_only",
    source_file="e4d1_external_monthly_metrics.csv",
    default_period="1983",
    used_for_model_selection=False,
)


master = pd.DataFrame(
    master_rows
)

master.to_csv(
    MASTER_OUT,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# 9. Build KEY RESULTS
# =========================================================

key_rows = []


def key(
    phase,
    result_id,
    model,
    period,
    scale,
    *,
    NSE=np.nan,
    KGE=np.nan,
    RMSE=np.nan,
    MAE=np.nan,
    Bias=np.nan,
    Pearson=np.nan,
    gain=np.nan,
    aux_name="",
    aux_value="",
    evidence_role="",
    source_file="",
    interpretation="",
):

    key_rows.append(
        {
            "phase": phase,
            "result_id": result_id,
            "model": model,
            "period": period,
            "temporal_scale": scale,
            "NSE": NSE,
            "KGE": KGE,
            "RMSE": RMSE,
            "MAE": MAE,
            "Bias": Bias,
            "Pearson": Pearson,
            "RMSE_gain_pct": gain,
            "aux_name": aux_name,
            "aux_value": aux_value,
            "evidence_role": evidence_role,
            "source_file": source_file,
            "interpretation": interpretation,
        }
    )


key(
    "E4A2",
    "routing_R1",
    "R1_HOMOGENEOUS_68_REACH",
    "1978-1981",
    "daily",
    RMSE=r1_rmse,
    evidence_role="diagnostic",
    source_file="e4a2_r1_train_fit.csv",
    interpretation="Homogeneous routing baseline.",
)

key(
    "E4A2",
    "routing_R2_best",
    "R2_BEST_MULTISTART",
    "1978-1981",
    "daily",
    RMSE=r2_rmse,
    gain=r2_gain_pct,
    evidence_role="diagnostic",
    source_file="e4a2_r2_multistart_train_fit.csv",
    interpretation=(
        "Reach heterogeneity produced negligible "
        "train improvement."
    ),
)


for rid, row, label in [
    (
        "A0_R1",
        A0,
        "Routing only",
    ),
    (
        "A1_mean",
        A1,
        "Mean residual correction",
    ),
    (
        "A2_monthly",
        A2,
        "Monthly residual climatology",
    ),
    (
        "A3_P",
        A3,
        "Precipitation-only residual model",
    ),
    (
        "A4_T",
        A4,
        "Temperature-only residual model",
    ),
    (
        "A5_PT",
        A5,
        "Precipitation + temperature model",
    ),
]:

    key(
        "E4B2A",
        rid,
        str(row["model"]),
        "1982 validation",
        "daily",
        NSE=fvalue(row, "NSE"),
        KGE=fvalue(row, "KGE"),
        RMSE=fvalue(row, "RMSE"),
        MAE=fvalue(row, "MAE"),
        Bias=fvalue(row, "Bias"),
        Pearson=fvalue(
            row,
            "Pearson",
        ),
        evidence_role="development_validation",
        source_file="e4b2a_forcing_ablation_metrics.csv",
        interpretation=label,
    )


key(
    "E4B2B",
    "Fourier6_seasonal_null",
    str(B2["model"]),
    "1982 validation",
    "daily",
    NSE=fvalue(B2, "NSE"),
    KGE=fvalue(B2, "KGE"),
    RMSE=fvalue(B2, "RMSE"),
    MAE=fvalue(B2, "MAE"),
    Bias=fvalue(B2, "Bias"),
    Pearson=fvalue(B2, "Pearson"),
    evidence_role="development_validation",
    source_file="e4b2b_temperature_seasonality_metrics.csv",
    interpretation="Strong smooth seasonal null.",
)

key(
    "E4B2B",
    "best_temperature_anomaly",
    str(best_anomaly["model"]),
    "1982 validation",
    "daily",
    NSE=fvalue(
        best_anomaly,
        "NSE",
    ),
    KGE=fvalue(
        best_anomaly,
        "KGE",
    ),
    RMSE=fvalue(
        best_anomaly,
        "RMSE",
    ),
    gain=temperature_anomaly_gain_pct,
    evidence_role="mechanism_diagnostic",
    source_file="e4b2b_temperature_seasonality_metrics.csv",
    interpretation=(
        "Temperature anomaly does not improve "
        "over seasonal Fourier null."
    ),
)

key(
    "E4B2C",
    "T7_stability",
    "T7_SEASONAL_PROXY",
    "1978-1981 LOYO",
    "daily",
    aux_name="LOYO_wins / median_gain_pct",
    aux_value=(
        f"{loyo_wins}/4 / "
        f"{loyo_median_gain:.6f}"
    ),
    evidence_role="train_only_stability",
    source_file="e4b2c_yearwise_stability.csv",
    interpretation=(
        "Raw T7 advantage is not stable across years."
    ),
)

key(
    "E4B2C",
    "T7_bootstrap",
    "T7_vs_Fourier6",
    "1982 descriptive bootstrap",
    "daily",
    aux_name="delta_RMSE_95CI",
    aux_value=(
        f"[{bootstrap_ci_low:.6f}, "
        f"{bootstrap_ci_high:.6f}]"
    ),
    evidence_role="supportive_descriptive",
    source_file="e4b2c_validation_bootstrap_summary.csv",
    interpretation=(
        "Bootstrap CI crosses zero."
    ),
)


key(
    "E4C",
    "1983_R1",
    str(C_R1["model"]),
    "1983 holdout",
    "daily",
    NSE=fvalue(C_R1, "NSE"),
    KGE=fvalue(C_R1, "KGE"),
    RMSE=fvalue(C_R1, "RMSE"),
    MAE=fvalue(C_R1, "MAE"),
    Bias=fvalue(C_R1, "Bias"),
    Pearson=fvalue(
        C_R1,
        "Pearson",
    ),
    evidence_role="frozen_holdout",
    source_file="e4c_1983_holdout_metrics.csv",
    interpretation="Frozen routing-only baseline.",
)

key(
    "E4C",
    "1983_Fourier6",
    str(C_FINAL["model"]),
    "1983 holdout",
    "daily",
    NSE=fvalue(C_FINAL, "NSE"),
    KGE=fvalue(C_FINAL, "KGE"),
    RMSE=fvalue(C_FINAL, "RMSE"),
    MAE=fvalue(C_FINAL, "MAE"),
    Bias=fvalue(C_FINAL, "Bias"),
    Pearson=fvalue(
        C_FINAL,
        "Pearson",
    ),
    gain=c_gain_pct,
    evidence_role="frozen_holdout",
    source_file="e4c_1983_holdout_metrics.csv",
    interpretation=(
        "Frozen Fourier6 substantially improves "
        "over routing-only."
    ),
)


key(
    "E4D1",
    "external_daily_label_monthly",
    str(D_LABEL["model"]),
    "1983",
    "monthly",
    NSE=fvalue(D_LABEL, "NSE"),
    KGE=fvalue(D_LABEL, "KGE"),
    RMSE=fvalue(D_LABEL, "RMSE"),
    MAE=fvalue(D_LABEL, "MAE"),
    Bias=fvalue(D_LABEL, "Bias"),
    Pearson=fvalue(
        D_LABEL,
        "Pearson",
    ),
    evidence_role="external_consistency",
    source_file="e4d1_external_monthly_metrics.csv",
    interpretation=(
        "Reference consistency between existing "
        "daily labels and external monthly series."
    ),
)

key(
    "E4D1",
    "external_R1",
    str(D_R1["model"]),
    "1983",
    "monthly",
    NSE=fvalue(D_R1, "NSE"),
    KGE=fvalue(D_R1, "KGE"),
    RMSE=fvalue(D_R1, "RMSE"),
    MAE=fvalue(D_R1, "MAE"),
    Bias=fvalue(D_R1, "Bias"),
    Pearson=fvalue(D_R1, "Pearson"),
    evidence_role="external_consistency",
    source_file="e4d1_external_monthly_metrics.csv",
    interpretation="Monthly routing-only baseline.",
)

key(
    "E4D1",
    "external_Fourier6",
    str(D_FINAL["model"]),
    "1983",
    "monthly",
    NSE=fvalue(D_FINAL, "NSE"),
    KGE=fvalue(D_FINAL, "KGE"),
    RMSE=fvalue(D_FINAL, "RMSE"),
    MAE=fvalue(D_FINAL, "MAE"),
    Bias=fvalue(D_FINAL, "Bias"),
    Pearson=fvalue(
        D_FINAL,
        "Pearson",
    ),
    gain=d_gain_pct,
    evidence_role="external_consistency",
    source_file="e4d1_external_monthly_metrics.csv",
    interpretation=(
        "External monthly-series consistency only; "
        "not official independent validation."
    ),
)


key_df = pd.DataFrame(
    key_rows
)

key_df.to_csv(
    KEY_OUT,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# 10. Claim ledger
# =========================================================

monthly_rmse = float(
    A2["RMSE"]
)

p_rmse = float(
    A3["RMSE"]
)

mean_rmse = float(
    A1["RMSE"]
)

a0_rmse = float(
    A0["RMSE"]
)


claim_rows = [
    {
        "claim_id": "C1",
        "claim": (
            "Adding reach-scale routing heterogeneity "
            "materially improves reconstruction."
        ),
        "status": "NOT_SUPPORTED",
        "evidence": (
            f"R1 train RMSE={r1_rmse:.6f}; "
            f"best R2 RMSE={r2_rmse:.6f}; "
            f"gain={r2_gain_pct:.4f}%."
        ),
        "allowed_wording": (
            "Under the tested parameterization, "
            "reach-scale heterogeneity provided "
            "negligible additional fit."
        ),
        "prohibited_wording": (
            "Routing heterogeneity never matters."
        ),
    },

    {
        "claim_id": "C2",
        "claim": (
            "Routing-only reconstruction misses a "
            "substantial downstream contribution."
        ),
        "status": "SUPPORTED",
        "evidence": (
            f"1982 R1 RMSE={a0_rmse:.6f}; "
            f"mean-residual correction RMSE="
            f"{mean_rmse:.6f}."
        ),
        "allowed_wording": (
            "A substantial systematic component "
            "remains unexplained by routing alone."
        ),
        "prohibited_wording": (
            "The exact physical source of all residual "
            "flow has been identified."
        ),
    },

    {
        "claim_id": "C3",
        "claim": (
            "Recent incremental precipitation alone "
            "explains the missing contribution."
        ),
        "status": "NOT_SUPPORTED",
        "evidence": (
            f"P-only RMSE={p_rmse:.6f}; "
            f"monthly seasonal baseline RMSE="
            f"{monthly_rmse:.6f}."
        ),
        "allowed_wording": (
            "The tested precipitation windows did not "
            "outperform the seasonal null."
        ),
        "prohibited_wording": (
            "Precipitation has no hydrological effect."
        ),
    },

    {
        "claim_id": "C4",
        "claim": (
            "Temperature anomalies provide predictive "
            "information beyond expected seasonality."
        ),
        "status": "NOT_SUPPORTED",
        "evidence": (
            f"Fourier6 RMSE={float(B2['RMSE']):.6f}; "
            f"best season+T-anomaly RMSE="
            f"{float(best_anomaly['RMSE']):.6f}; "
            f"gain={temperature_anomaly_gain_pct:.4f}%."
        ),
        "allowed_wording": (
            "No incremental temperature-anomaly signal "
            "beyond the seasonal null was detected."
        ),
        "prohibited_wording": (
            "Temperature does not affect streamflow."
        ),
    },

    {
        "claim_id": "C5",
        "claim": (
            "The missing incremental contribution "
            "contains a strong seasonal structure."
        ),
        "status": "SUPPORTED",
        "evidence": (
            f"1982 Fourier6 RMSE="
            f"{float(B2['RMSE']):.6f}; "
            f"1983 frozen-test RMSE="
            f"{float(C_FINAL['RMSE']):.6f}; "
            f"external monthly RMSE="
            f"{float(D_FINAL['RMSE']):.6f}."
        ),
        "allowed_wording": (
            "The routing residual exhibits a "
            "persistent seasonal structure."
        ),
        "prohibited_wording": (
            "The Fourier terms identify the exact "
            "physical seasonal process."
        ),
    },

    {
        "claim_id": "C6",
        "claim": (
            "Raw T7 is a stable hydrological-state "
            "proxy across years."
        ),
        "status": "NOT_STABLY_SUPPORTED",
        "evidence": (
            f"T7 LOYO wins={loyo_wins}/4; "
            f"median RMSE gain="
            f"{loyo_median_gain:.6f}%; "
            f"bootstrap CI=["
            f"{bootstrap_ci_low:.6f}, "
            f"{bootstrap_ci_high:.6f}]."
        ),
        "allowed_wording": (
            "Raw temperature can act as a seasonal "
            "proxy in some periods, but the advantage "
            "was not stable."
        ),
        "prohibited_wording": (
            "Temperature is the causal driver."
        ),
    },

    {
        "claim_id": "C7",
        "claim": (
            "The frozen seasonal correction retains "
            "improvement on the 1983 holdout."
        ),
        "status": "SUPPORTED",
        "evidence": (
            f"R1 RMSE={float(C_R1['RMSE']):.6f}; "
            f"Fourier6 RMSE="
            f"{float(C_FINAL['RMSE']):.6f}; "
            f"RMSE gain={c_gain_pct:.4f}%."
        ),
        "allowed_wording": (
            "The frozen correction retained substantial "
            "improvement on the E4 1983 holdout."
        ),
        "prohibited_wording": (
            "1983 proves universal generalization."
        ),
    },

    {
        "claim_id": "C8",
        "claim": (
            "The frozen model remains consistent with "
            "the numerically distinct external monthly "
            "DSK series."
        ),
        "status": "SUPPORTED_AT_CONSISTENCY_LEVEL",
        "evidence": (
            f"External R1 RMSE="
            f"{float(D_R1['RMSE']):.6f}; "
            f"Fourier6 RMSE="
            f"{float(D_FINAL['RMSE']):.6f}; "
            f"gain={d_gain_pct:.4f}%."
        ),
        "allowed_wording": (
            "External monthly-series consistency "
            "evaluation."
        ),
        "prohibited_wording": (
            "Official independent hydrological "
            "validation."
        ),
    },

    {
        "claim_id": "C9",
        "claim": (
            "The Q-dsk-byblk workbook constitutes "
            "official independent validation."
        ),
        "status": "NOT_ESTABLISHED",
        "evidence": (
            "Numerical lineage is distinct, but the "
            "primary provider and explicit unit "
            "metadata remain unresolved."
        ),
        "allowed_wording": (
            "Numerically distinct external monthly "
            "series with unresolved primary provenance."
        ),
        "prohibited_wording": (
            "Official hydrological-yearbook validation."
        ),
    },
]


claims = pd.DataFrame(
    claim_rows
)

claims.to_csv(
    CLAIM_OUT,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# 11. Reproducibility manifest
# =========================================================

source_hashes = {}

for key, path in FILES.items():

    if path.is_file():

        source_hashes[key] = {
            "path": str(
                path.relative_to(ROOT)
            ),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }


manifest = {
    "protocol":
        "VHS-BD1M-PHASE-E5A-RESULTS-FREEZE",

    "results_frozen_for_writeup": True,

    "final_model": final_model,

    "final_method": {
        "routing":
            "R1_HOMOGENEOUS_68_REACH",

        "tau_global_days":
            tau_global_days,

        "required_substeps_per_day":
            required_substeps,

        "correction":
            "B2_FOURIER6_SEASONAL",

        "fourier_harmonics":
            harmonics,

        "train_period":
            "1978-1981",

        "development_validation_period":
            "1982",

        "e4_fixed_holdout_period":
            "1983",

        "validation_refit_before_test":
            False,

        "test_based_model_selection":
            False,
    },

    "evidence_boundaries": {
        "1982_role":
            (
                "development validation; used "
                "during E4B model development"
            ),

        "1983_role":
            (
                "fixed-method E4 holdout after "
                "method freeze"
            ),

        "external_monthly_role":
            "external monthly-series consistency",

        "external_monthly_primary_provenance_resolved":
            False,

        "external_monthly_official_independent_validation":
            False,
    },

    "routing_diagnostic": {
        "R1_train_RMSE":
            r1_rmse,

        "best_R2_train_RMSE":
            r2_rmse,

        "R2_gain_vs_R1_pct":
            r2_gain_pct,
    },

    "stability_diagnostic": {
        "T7_LOYO_wins":
            loyo_wins,

        "T7_LOYO_total":
            4,

        "T7_LOYO_median_gain_pct":
            loyo_median_gain,

        "bootstrap_delta_RMSE_CI":
            [
                bootstrap_ci_low,
                bootstrap_ci_high,
            ],

        "bootstrap_probability_T7_better":
            bootstrap_prob_t7_better,
    },

    "fixed_holdout_1983": {
        "R1_RMSE":
            float(C_R1["RMSE"]),

        "Fourier6_RMSE":
            float(C_FINAL["RMSE"]),

        "Fourier6_NSE":
            float(C_FINAL["NSE"]),

        "Fourier6_RMSE_gain_pct":
            c_gain_pct,
    },

    "external_monthly_1983": {
        "months":
            int(D_FINAL["n_months"]),

        "R1_RMSE":
            float(D_R1["RMSE"]),

        "Fourier6_RMSE":
            float(D_FINAL["RMSE"]),

        "Fourier6_NSE":
            float(D_FINAL["NSE"]),

        "Fourier6_RMSE_gain_pct":
            d_gain_pct,
    },

    "source_files":
        source_hashes,

    "next_phase":
        "E5B_PAPER_FIGURES",
}


MANIFEST_OUT.write_text(
    json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# 12. Human-readable summary
# =========================================================

summary = f"""# VHS-BD1M E5A Results Freeze

## Final method

- routing:
  R1 homogeneous 68-reach routing

- tau_global_days:
  {tau_global_days:.10f}

- correction:
  B2_FOURIER6_SEASONAL

- Fourier harmonics:
  {harmonics}

- fit period:
  1978-1981

- development validation:
  1982

- fixed E4 holdout:
  1983

## Routing diagnosis

- R1 train RMSE:
  {r1_rmse:.6f}

- best R2 train RMSE:
  {r2_rmse:.6f}

- R2 RMSE gain vs R1:
  {r2_gain_pct:.6f}%

Interpretation:

Reach-scale heterogeneity produced only negligible
additional training fit under the tested parameterization.

## Seasonality / temperature diagnosis

- 1982 Fourier6 RMSE:
  {float(B2["RMSE"]):.6f}

- best temperature-anomaly RMSE:
  {float(best_anomaly["RMSE"]):.6f}

- anomaly RMSE gain:
  {temperature_anomaly_gain_pct:.6f}%

- T7 LOYO wins:
  {loyo_wins}/4

- T7 LOYO median RMSE gain:
  {loyo_median_gain:.6f}%

- bootstrap delta-RMSE 95% CI:
  [{bootstrap_ci_low:.6f},
   {bootstrap_ci_high:.6f}]

Interpretation:

Raw temperature may behave as a seasonal proxy,
but an independent temperature-anomaly contribution
beyond seasonality was not supported.

## 1983 frozen daily holdout

### R1

- NSE:
  {float(C_R1["NSE"]):.6f}

- RMSE:
  {float(C_R1["RMSE"]):.6f}

### Frozen Fourier6

- NSE:
  {float(C_FINAL["NSE"]):.6f}

- KGE:
  {float(C_FINAL["KGE"]):.6f}

- RMSE:
  {float(C_FINAL["RMSE"]):.6f}

- RMSE improvement vs R1:
  {c_gain_pct:.6f}%

## External monthly-series consistency

### R1

- NSE:
  {float(D_R1["NSE"]):.6f}

- RMSE:
  {float(D_R1["RMSE"]):.6f}

### Frozen Fourier6

- NSE:
  {float(D_FINAL["NSE"]):.6f}

- KGE:
  {float(D_FINAL["KGE"]):.6f}

- RMSE:
  {float(D_FINAL["RMSE"]):.6f}

- RMSE improvement vs R1:
  {d_gain_pct:.6f}%

Important:

The external monthly workbook is numerically distinct
from the current daily-label series, but its primary
official provenance and explicit unit metadata remain
unresolved.

Therefore:

EXTERNAL_MONTHLY_OFFICIAL_VALIDATION=false

## Write-up boundary

The following claims are frozen:

1. Routing heterogeneity did not materially improve
   reconstruction under the tested formulation.

2. Routing-only predictions leave a substantial
   systematic downstream residual component.

3. The tested precipitation windows do not explain
   this component better than the seasonal null.

4. Temperature anomalies do not provide detectable
   information beyond expected seasonality.

5. The residual contains a persistent seasonal
   structure.

6. The frozen Fourier6 seasonal correction retained
   substantial improvement on the E4 1983 holdout.

7. The result also retained consistency against a
   numerically distinct external monthly DSK series,
   but this is not described as official independent
   validation.

## Status

E5A_MASTER_RESULTS_BUILT=true

E5A_KEY_RESULTS_BUILT=true

E5A_CLAIM_LEDGER_BUILT=true

E5A_REPRODUCIBILITY_MANIFEST_BUILT=true

FINAL_MODEL=B2_FOURIER6_SEASONAL

TEST_BASED_MODEL_SELECTION=false

EXTERNAL_MONTHLY_OFFICIAL_VALIDATION=false

RESULTS_FROZEN_FOR_WRITEUP=true

READY_FOR_E5B_FIGURES=true
"""


SUMMARY_OUT.write_text(
    summary,
    encoding="utf-8",
)


# =========================================================
# 13. Final integrity checks
# =========================================================

outputs = [
    MASTER_OUT,
    KEY_OUT,
    CLAIM_OUT,
    MANIFEST_OUT,
    SUMMARY_OUT,
]

for path in outputs:

    if (
        not path.exists()
        or path.stat().st_size == 0
    ):
        fail(
            f"Output was not created: {path}"
        )


print("E5A complete")

print(
    f"master_rows={len(master)}"
)

print(
    f"key_results={len(key_df)}"
)

print(
    f"claims={len(claims)}"
)

print(
    f"R1_train_RMSE={r1_rmse:.6f}"
)

print(
    f"best_R2_train_RMSE={r2_rmse:.6f}"
)

print(
    "R2_gain_vs_R1_pct="
    f"{r2_gain_pct:.6f}"
)

print(
    "T7_LOYO_wins="
    f"{loyo_wins}/4"
)

print(
    "T7_LOYO_median_gain_pct="
    f"{loyo_median_gain:.6f}"
)

print(
    "1983_Fourier6_RMSE="
    f"{float(C_FINAL['RMSE']):.6f}"
)

print(
    "1983_Fourier6_NSE="
    f"{float(C_FINAL['NSE']):.6f}"
)

print(
    "1983_Fourier6_gain_vs_R1_pct="
    f"{c_gain_pct:.6f}"
)

print(
    "external_monthly_Fourier6_RMSE="
    f"{float(D_FINAL['RMSE']):.6f}"
)

print(
    "external_monthly_Fourier6_NSE="
    f"{float(D_FINAL['NSE']):.6f}"
)

print(
    "external_monthly_gain_vs_R1_pct="
    f"{d_gain_pct:.6f}"
)

print(
    "RESULTS_FROZEN_FOR_WRITEUP=true"
)

print(
    "READY_FOR_E5B_FIGURES=true"
)