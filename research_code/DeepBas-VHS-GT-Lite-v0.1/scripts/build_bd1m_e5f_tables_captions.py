from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

protected = list((ROOT / "outputs/vhs_bd1m").rglob("e4*")) + list((ROOT / "outputs/vhs_bd1m/paper").glob("e5a*"))
before = {p: digest(p) for p in protected if p.is_file()}
manifest = json.loads((ROOT / "outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json").read_text(encoding="utf-8"))
for item in manifest["source_files"].values():
    p = ROOT / item["path"]
    if not p.is_file() or digest(p) != item["sha256"]:
        raise RuntimeError(f"E5F BUILD FAILED: frozen source hash mismatch: {p}")
method = manifest["final_method"]
if not (manifest["results_frozen_for_writeup"] and method["routing"] == "R1_HOMOGENEOUS_68_REACH" and method["correction"] == "B2_FOURIER6_SEASONAL" and method["fourier_harmonics"] == 6 and not method["test_based_model_selection"] and not method["validation_refit_before_test"] and not manifest["evidence_boundaries"]["external_monthly_official_independent_validation"]):
    raise RuntimeError("E5F BUILD FAILED: freeze protocol mismatch")

PAPER = ROOT / "outputs/vhs_bd1m/paper"

KEY_FILE = PAPER / "e5a_key_results.csv"

TABLE1_CSV = (
    PAPER / "e5f_table1_diagnostic_evidence.csv"
)

TABLE2_CSV = (
    PAPER / "e5f_table2_final_evaluation.csv"
)

TABLES_MD = (
    PAPER / "e5f_tables.md"
)

CAPTIONS_MD = (
    PAPER / "e5f_figure_captions.md"
)

STATUS_FILE = (
    PAPER / "e5f_status.txt"
)


# =========================================================
# Utilities
# =========================================================

def fail(message: str):
    raise RuntimeError(
        f"E5F BUILD FAILED: {message}"
    )


def fmt_num(
    value,
    digits=6,
):
    if pd.isna(value):
        return ""

    return f"{float(value):.{digits}f}"


def md_escape(value):
    text = str(value)

    return (
        text
        .replace("|", r"\|")
        .replace("\n", " ")
    )


def markdown_table(
    df: pd.DataFrame,
) -> str:

    cols = list(df.columns)

    lines = []

    lines.append(
        "| "
        + " | ".join(
            md_escape(c)
            for c in cols
        )
        + " |"
    )

    lines.append(
        "| "
        + " | ".join(
            "---"
            for _ in cols
        )
        + " |"
    )

    for _, row in df.iterrows():

        lines.append(
            "| "
            + " | ".join(
                md_escape(row[c])
                for c in cols
            )
            + " |"
        )

    return "\n".join(lines)


# =========================================================
# Load frozen E5A key registry
# =========================================================

if not KEY_FILE.exists():
    fail(
        f"Missing frozen E5A registry: "
        f"{KEY_FILE}"
    )


key = pd.read_csv(
    KEY_FILE
)
print("columns=" + ", ".join(key.columns))
print(key[["result_id", "model", "period", "RMSE", "NSE", "KGE", "MAE", "Bias", "Pearson", "RMSE_gain_pct"]].to_string(index=False))


required_columns = {
    "phase",
    "result_id",
    "model",
    "period",
    "temporal_scale",
    "NSE",
    "KGE",
    "RMSE",
    "MAE",
    "Bias",
    "Pearson",
    "RMSE_gain_pct",
    "aux_name",
    "aux_value",
    "evidence_role",
    "source_file",
    "interpretation",
}

missing = (
    required_columns
    - set(key.columns)
)

if missing:
    fail(
        f"Missing E5A columns: "
        f"{sorted(missing)}"
    )


key = key.set_index(
    "result_id",
    drop=False,
)


def get(
    result_id: str,
):
    if result_id not in key.index:
        fail(
            f"Missing key result: "
            f"{result_id}"
        )

    row = key.loc[result_id]

    if isinstance(
        row,
        pd.DataFrame,
    ):
        fail(
            f"Duplicate key result: "
            f"{result_id}"
        )

    return row


# =========================================================
# Hard integrity gates
# =========================================================

required_ids = [
    "routing_R1",
    "routing_R2_best",

    "A0_R1",
    "A1_mean",
    "A2_monthly",
    "A3_P",
    "A4_T",
    "A5_PT",

    "Fourier6_seasonal_null",
    "best_temperature_anomaly",

    "T7_stability",
    "T7_bootstrap",

    "1983_R1",
    "1983_Fourier6",

    "external_R1",
    "external_Fourier6",
]

for result_id in required_ids:
    get(result_id)


# Frozen numerical sanity checks

if not np.isclose(
    float(
        get(
            "1983_Fourier6"
        )["RMSE"]
    ),
    45.034412,
    atol=1e-5,
    rtol=0,
):
    fail(
        "1983 Fourier6 RMSE changed."
    )


if not np.isclose(
    float(
        get(
            "external_Fourier6"
        )["RMSE"]
    ),
    34.929611,
    atol=1e-5,
    rtol=0,
):
    fail(
        "External monthly Fourier6 "
        "RMSE changed."
    )


# =========================================================
# Table 1
# Diagnostic evidence and model-selection logic
# =========================================================

table1_rows = []


def add_table1(
    *,
    stage,
    evidence,
    period,
    RMSE="",
    NSE="",
    diagnostic,
    decision,
):

    table1_rows.append(
        {
            "Stage": stage,
            "Evidence / model": evidence,
            "Evaluation period": period,
            "RMSE": RMSE,
            "NSE": NSE,
            "Diagnostic interpretation":
                diagnostic,
            "Selection implication":
                decision,
        }
    )


r1 = get(
    "routing_R1"
)

r2 = get(
    "routing_R2_best"
)


add_table1(
    stage="Routing diagnosis",
    evidence="R1 homogeneous routing",
    period="1978–1981 training",
    RMSE=fmt_num(
        r1["RMSE"]
    ),
    NSE="",
    diagnostic=(
        "Low-capacity routing baseline."
    ),
    decision=(
        "Retained as routing backbone."
    ),
)


add_table1(
    stage="Routing diagnosis",
    evidence="Best heterogeneous R2",
    period="1978–1981 training",
    RMSE=fmt_num(
        r2["RMSE"]
    ),
    NSE="",
    diagnostic=(
        f"Only {float(r2['RMSE_gain_pct']):.6f}% RMSE improvement "
        "over R1; additional routing "
        "heterogeneity provided "
        "negligible fit gain."
    ),
    decision=(
        "Additional routing complexity was not retained in the final model."
    ),
)


diagnostic_rows = [
    (
        "A0_R1",
        "R1 routing only",
        (
            "Large routing-only error "
            "and negative downstream bias."
        ),
        (
            "Search for unresolved "
            "downstream contribution."
        ),
    ),

    (
        "A1_mean",
        "Mean residual correction",
        (
            "Large improvement from a "
            "constant residual correction."
        ),
        (
            "Supports a substantial "
            "systematic missing component."
        ),
    ),

    (
        "A2_monthly",
        "Monthly residual climatology",
        (
            "Seasonal baseline improves "
            "substantially over R1."
        ),
        (
            "Seasonality becomes a "
            "strong null hypothesis."
        ),
    ),

    (
        "A3_P",
        "Precipitation-only",
        (
            "Worse than the monthly "
            "seasonal baseline."
        ),
        (
            "Tested precipitation history "
            "does not explain the residual "
            "better than seasonality."
        ),
    ),

    (
        "A4_T",
        "Raw temperature-only",
        (
            "Strongest single-year RMSE "
            "among the simple 1982 "
            "ablation models."
        ),
        (
            "Treated as a diagnostic "
            "seasonal proxy; not selected "
            "from 1982 alone."
        ),
    ),

    (
        "A5_PT",
        "Precipitation + temperature",
        (
            "Did not improve over the "
            "seasonal null."
        ),
        (
            "No justification for a "
            "combined forcing model."
        ),
    ),
]


for (
    result_id,
    label,
    diagnostic,
    decision,
) in diagnostic_rows:

    row = get(
        result_id
    )

    add_table1(
        stage="1982 forcing ablation",
        evidence=label,
        period="1982 development validation",
        RMSE=fmt_num(
            row["RMSE"]
        ),
        NSE=fmt_num(
            row["NSE"]
        ),
        diagnostic=diagnostic,
        decision=decision,
    )


fourier = get(
    "Fourier6_seasonal_null"
)

anom = get(
    "best_temperature_anomaly"
)


add_table1(
    stage="Seasonality diagnostic",
    evidence="Six-harmonic Fourier",
    period="1982 development validation",
    RMSE=fmt_num(
        fourier["RMSE"]
    ),
    NSE=fmt_num(
        fourier["NSE"]
    ),
    diagnostic=(
        "Smooth seasonal model provides "
        "a strong low-capacity null."
    ),
    decision=(
        "Candidate frozen correction."
    ),
)


add_table1(
    stage="Seasonality diagnostic",
    evidence=(
        "Fourier + best "
        "temperature anomaly"
    ),
    period="1982 development validation",
    RMSE=fmt_num(
        anom["RMSE"]
    ),
    NSE=fmt_num(
        anom["NSE"]
    ),
    diagnostic=(
        "RMSE gain relative to Fourier "
        f"was {float(anom['RMSE_gain_pct']):.6f}%; "
        "temperature anomaly added no "
        "detectable benefit."
    ),
    decision=(
        "No detectable incremental predictive benefit beyond seasonality "
        "was supported under the tested specification."
    ),
)


stability = get(
    "T7_stability"
)

bootstrap = get(
    "T7_bootstrap"
)


add_table1(
    stage="Cross-year stability",
    evidence="Raw T7 vs Fourier6",
    period="1978–1981 LOYO",
    RMSE="",
    NSE="",
    diagnostic=(
        f"T7 wins / median RMSE gain (%) = {stability['aux_value']}. "
        "Only one of four held-out training years improved."
    ),
    decision=(
        "Raw temperature advantage "
        "not stable across years."
    ),
)


add_table1(
    stage="Uncertainty check",
    evidence="T7 vs Fourier6 bootstrap",
    period="1982 supportive bootstrap",
    RMSE="",
    NSE="",
    diagnostic=(
        "ΔRMSE = RMSE(Fourier6) - RMSE(T7); positive favors T7. "
        f"95% CI crossed zero: {bootstrap['aux_value']}."
    ),
    decision=(
        "No robust basis to prefer "
        "raw T7."
    ),
)


table1 = pd.DataFrame(
    table1_rows
)


table1.to_csv(
    TABLE1_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Table 2
# Final frozen evaluation
# =========================================================

table2_rows = []


def add_table2(
    *,
    evaluation,
    model,
    NSE,
    KGE,
    RMSE,
    MAE,
    Bias,
    Pearson,
    improvement,
    evidence_level,
):

    table2_rows.append(
        {
            "Evaluation": evaluation,
            "Model": model,
            "NSE": fmt_num(NSE),
            "KGE": fmt_num(KGE),
            "RMSE": fmt_num(RMSE),
            "MAE": fmt_num(MAE),
            "Bias": fmt_num(Bias),
            "Pearson r": fmt_num(
                Pearson
            ),
            "RMSE improvement vs R1 (%)":
                improvement,
            "Evidence level":
                evidence_level,
        }
    )


C_R1 = get(
    "1983_R1"
)

C_FINAL = get(
    "1983_Fourier6"
)

D_R1 = get(
    "external_R1"
)

D_FINAL = get(
    "external_Fourier6"
)


add_table2(
    evaluation="1983 daily holdout",
    model="R1 routing only",
    NSE=C_R1["NSE"],
    KGE=C_R1["KGE"],
    RMSE=C_R1["RMSE"],
    MAE=C_R1["MAE"],
    Bias=C_R1["Bias"],
    Pearson=C_R1["Pearson"],
    improvement="0.000",
    evidence_level=(
        "Fixed-method E4 holdout"
    ),
)


add_table2(
    evaluation="1983 daily holdout",
    model="R1 + frozen Fourier6",
    NSE=C_FINAL["NSE"],
    KGE=C_FINAL["KGE"],
    RMSE=C_FINAL["RMSE"],
    MAE=C_FINAL["MAE"],
    Bias=C_FINAL["Bias"],
    Pearson=C_FINAL["Pearson"],
    improvement=fmt_num(
        C_FINAL[
            "RMSE_gain_pct"
        ]
    ),
    evidence_level=(
        "Fixed-method E4 holdout"
    ),
)


add_table2(
    evaluation=(
        "1983 external monthly series"
    ),
    model="R1 routing only",
    NSE=D_R1["NSE"],
    KGE=D_R1["KGE"],
    RMSE=D_R1["RMSE"],
    MAE=D_R1["MAE"],
    Bias=D_R1["Bias"],
    Pearson=D_R1["Pearson"],
    improvement="0.000",
    evidence_level=(
        "External monthly-series consistency only"
    ),
)


add_table2(
    evaluation=(
        "1983 external monthly series"
    ),
    model="R1 + frozen Fourier6",
    NSE=D_FINAL["NSE"],
    KGE=D_FINAL["KGE"],
    RMSE=D_FINAL["RMSE"],
    MAE=D_FINAL["MAE"],
    Bias=D_FINAL["Bias"],
    Pearson=D_FINAL["Pearson"],
    improvement=fmt_num(
        D_FINAL[
            "RMSE_gain_pct"
        ]
    ),
    evidence_level=(
        "External monthly-series consistency only"
    ),
)


table2 = pd.DataFrame(
    table2_rows
)


table2.to_csv(
    TABLE2_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Markdown tables
# =========================================================

tables_md = f"""# E5F Paper Tables

## Table 1. Diagnostic evidence guiding model selection and method freeze

The table summarizes role-specific evidence from the
routing-complexity, forcing-ablation, seasonality, and
stability analyses. Metrics from different periods are
not interpreted as a single cross-period model ranking.

{markdown_table(table1)}

**Table 1 caption.**
Diagnostic evidence used to distinguish routing
complexity, unresolved downstream contribution,
meteorological forcing, and seasonal structure.
The raw temperature-only model achieved the lowest RMSE in the single
1982 development-validation year, but final model selection did not rely on
that ranking alone. Temperature-anomaly analysis,
leave-one-year-out stability, and bootstrap uncertainty
did not support a stable predictive contribution beyond
seasonality. The six-harmonic Fourier correction was
therefore frozen before the 1983 holdout evaluation.


## Table 2. Final fixed-method evaluation

{markdown_table(table2)}

**Table 2 caption.**
Performance of the frozen routing-plus-seasonal
reconstruction after method selection. The 1983 daily
evaluation used the fixed E4 holdout and involved no
routing refit, Fourier refit, harmonic re-selection, or
test-based model selection. The external monthly
comparison used the same frozen predictions after
monthly aggregation. Because the primary provenance
and explicit unit metadata of the external workbook
remain unresolved, the latter is reported only as an
external monthly-series consistency evaluation and not
as official independent validation.
"""


TABLES_MD.write_text(
    tables_md,
    encoding="utf-8",
)


# =========================================================
# Figure captions
# =========================================================

captions = """# E5F Figure Captions

## Figure 1

**Figure 1. Fixed-method daily holdout evaluation for
1983.** Observed DSK discharge is compared with the R1
homogeneous 68-reach routing baseline and the frozen
R1 + Fourier6 reconstruction. The routing parameter and
six-harmonic residual correction were determined before
the 1983 evaluation; no routing refit, Fourier refit,
harmonic re-selection, or test-based model selection was
performed. The seasonal correction recovers much of the
broad annual rise and recession that is absent from the
routing-only simulation, whereas sharp event-scale
summer peaks remain imperfectly represented.


## Figure 2

**Figure 2. Mechanism ablation during the 1982
development-validation period.** Bars show RMSE for
routing only (R1), mean-residual correction, monthly
residual climatology, precipitation-only correction,
raw temperature-only correction, combined
precipitation–temperature correction, six-harmonic
Fourier seasonality, and Fourier seasonality augmented
with the best temperature-anomaly term. Although raw
temperature achieved the lowest RMSE in this single
validation year, temperature anomalies provided no
improvement beyond the Fourier seasonal baseline.
Cross-year LOYO analysis did not support stable superiority of T7: T7 won in only one of four
held-out training years. T-only was therefore not retained as
the final model; this comparison does not establish a temperature
causal mechanism. Fourier6 was frozen following the anomaly,
stability, and uncertainty diagnostics.


## Figure 3

**Figure 3. External monthly-series consistency
evaluation for 1983.** The separately stored monthly DSK
series is compared with monthly means of the R1
routing-only prediction and the frozen R1 + Fourier6
prediction. No model parameter or bias correction was
estimated from this monthly series. The seasonal
correction reproduces the broad annual hydrograph
pattern substantially better than routing alone, while
remaining positively biased during several summer
months. The external monthly series is numerically
distinct from the daily DSK label series, but its primary
provider and explicit unit metadata remain unresolved;
the comparison is therefore interpreted as a consistency
evaluation rather than official independent hydrological
validation.


## Figure S1

**Figure S1. Leave-one-year-out stability of the raw T7
temperature proxy relative to Fourier6.** Each bar shows
the percentage RMSE gain of raw T7 relative to the
six-harmonic seasonal model for one held-out training
year from 1978–1981. Positive values indicate lower RMSE
for T7. T7 improved over Fourier6 in only one of four
held-out years, demonstrating that its apparent advantage
was not stable across years.


## Figure S2

**Figure S2. Moving-block bootstrap uncertainty for the
1982 T7–Fourier6 comparison.** The plotted quantity is
ΔRMSE = RMSE(Fourier6) − RMSE(T7), so positive values
favor T7. Uncertainty was estimated using a 30-day
moving-block bootstrap. The 95% confidence interval
crossed zero, indicating that the apparent T7 advantage
during 1982 was not robust enough to justify replacing
the seasonal correction.
"""


CAPTIONS_MD.write_text(
    captions,
    encoding="utf-8",
)


# =========================================================
# Final checks
# =========================================================

outputs = [
    TABLE1_CSV,
    TABLE2_CSV,
    TABLES_MD,
    CAPTIONS_MD,
]

for path in outputs:

    if (
        not path.exists()
        or path.stat().st_size == 0
    ):
        fail(
            f"Missing output: {path}"
        )


for path in outputs:
    content = path.read_text(encoding="utf-8-sig")
    if re.search(r"粘贴的文本|ChatGPT|Codex|TODO|provides official independent validation", content, re.I):
        fail(f"Internal audit marker or unsupported validation claim: {path.name}")
for p, old_hash in before.items():
    if digest(p) != old_hash:
        fail(f"Frozen result changed during E5F: {p}")
if len(table1) != 12 or len(table2) != 4:
    fail("Unexpected table row counts")
print("frozen_source_hashes_verified=" + str(len(manifest['source_files'])))
print("frozen_files_unchanged=" + str(len(before)))
print("text_cleanliness=PASS")
print(tables_md)
print(captions)

status = """E5F_TABLE1_BUILT=true
E5F_TABLE2_BUILT=true
E5F_MAIN_FIGURE_CAPTIONS_BUILT=true
E5F_SUPPLEMENTARY_CAPTIONS_BUILT=true
TABLE1_IS_CROSS_PERIOD_RANKING=false
TEST_BASED_MODEL_SELECTION=false
EXTERNAL_MONTHLY_OFFICIAL_VALIDATION=false
RESULTS_CHANGED_DURING_E5F=false
READY_FOR_E5G_INTRODUCTION=true
"""


STATUS_FILE.write_text(
    status,
    encoding="utf-8",
)


print("E5F complete")
print(
    f"table1_rows={len(table1)}"
)
print(
    f"table2_rows={len(table2)}"
)
print(
    "main_figure_captions=3"
)
print(
    "supplementary_figure_captions=2"
)
print(
    "RESULTS_CHANGED_DURING_E5F=false"
)
print(
    "READY_FOR_E5G_INTRODUCTION=true"
)

(PAPER / "e5f_console.log").write_text(
    "columns=" + ", ".join(key.columns) + "\n"
    + key[["result_id", "model", "period", "RMSE", "NSE", "KGE", "MAE", "Bias", "Pearson", "RMSE_gain_pct"]].to_string(index=False)
    + f"\nfrozen_source_hashes_verified={len(manifest['source_files'])}\nfrozen_files_unchanged={len(before)}\ntext_cleanliness=PASS\n"
    + tables_md + "\n" + captions
    + "\nE5F complete\ntable1_rows=12\ntable2_rows=4\nmain_figure_captions=3\nsupplementary_figure_captions=2\nRESULTS_CHANGED_DURING_E5F=false\nREADY_FOR_E5G_INTRODUCTION=true\n",
    encoding="utf-8",
)
