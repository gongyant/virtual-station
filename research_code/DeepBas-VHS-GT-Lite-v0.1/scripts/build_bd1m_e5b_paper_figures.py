from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]

EXP = ROOT / "outputs/vhs_bd1m/experiments"
PAPER = ROOT / "outputs/vhs_bd1m/paper"
FIG = PAPER / "figures"

FIG.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Inputs
# =========================================================

E5A_KEY = PAPER / "e5a_key_results.csv"

E4C_DAILY = (
    EXP / "e4c_1983_daily_predictions.csv"
)

E4D1_MONTHLY = (
    EXP / "e4d1_1983_monthly_comparison.csv"
)

E4B2C_YEARWISE = (
    EXP / "e4b2c_yearwise_stability.csv"
)

E4B2C_BOOT = (
    EXP / "e4b2c_validation_bootstrap_summary.csv"
)


# =========================================================
# Publication style
# =========================================================

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.labelsize": 10,
        "axes.titlesize": 11,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 600,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def save_figure(
    fig,
    stem: str,
):
    png = FIG / f"{stem}.png"
    pdf = FIG / f"{stem}.pdf"

    fig.savefig(
        png,
        dpi=600,
        bbox_inches="tight",
    )

    fig.savefig(
        pdf,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(
        f"saved: {png.relative_to(ROOT)}"
    )

    print(
        f"saved: {pdf.relative_to(ROOT)}"
    )


# =========================================================
# Figure 1
# Frozen 1983 daily holdout hydrograph
# =========================================================

def figure_1():

    df = pd.read_csv(
        E4C_DAILY,
        parse_dates=["date"],
    )

    required = {
        "date",
        "Q_target_dsk",
        "Q_R1_route",
        "Q_Fourier6_final",
    }

    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            f"Figure 1 missing columns: {missing}"
        )

    if len(df) != 365:
        raise RuntimeError(
            f"Expected 365 daily rows, got {len(df)}"
        )

    fig, ax = plt.subplots(
        figsize=(7.2, 3.5)
    )

    ax.plot(
        df["date"],
        df["Q_target_dsk"],
        label="Observed DSK",
        linewidth=1.5,
    )

    ax.plot(
        df["date"],
        df["Q_R1_route"],
        label="R1 routing only",
        linewidth=1.1,
        alpha=0.85,
    )

    ax.plot(
        df["date"],
        df["Q_Fourier6_final"],
        label="R1 + frozen Fourier6",
        linewidth=1.3,
        alpha=0.95,
    )

    ax.set_xlabel("Date")
    ax.set_ylabel(
        "Discharge"
    )

    ax.set_title(
        "1983 fixed-method daily holdout"
    )

    ax.legend(
        frameon=False,
        ncol=3,
        loc="upper right",
    )

    ax.grid(
        axis="y",
        alpha=0.20,
        linewidth=0.6,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "fig1_1983_daily_holdout",
    )


# =========================================================
# Figure 2
# Mechanism / ablation RMSE
# =========================================================

def figure_2():

    key = pd.read_csv(
        E5A_KEY
    )

    order = [
        "A0_R1",
        "A1_mean",
        "A2_monthly",
        "A3_P",
        "A4_T",
        "A5_PT",
        "Fourier6_seasonal_null",
        "best_temperature_anomaly",
    ]

    labels = {
        "A0_R1":
            "R1",

        "A1_mean":
            "Mean\nresidual",

        "A2_monthly":
            "Monthly\nclimatology",

        "A3_P":
            "P only",

        "A4_T":
            "T only",

        "A5_PT":
            "P + T",

        "Fourier6_seasonal_null":
            "Fourier6",

        "best_temperature_anomaly":
            "Fourier6 +\nT anomaly",
    }

    sub = (
        key[
            key["result_id"].isin(order)
        ]
        .copy()
    )

    sub["result_id"] = pd.Categorical(
        sub["result_id"],
        categories=order,
        ordered=True,
    )

    sub = sub.sort_values(
        "result_id"
    )

    if len(sub) != len(order):
        raise RuntimeError(
            "Figure 2 key-results rows incomplete."
        )

    rmse = pd.to_numeric(
        sub["RMSE"],
        errors="raise",
    ).to_numpy()

    x = np.arange(len(sub))

    fig, ax = plt.subplots(
        figsize=(7.2, 3.8)
    )

    bars = ax.bar(
        x,
        rmse,
        width=0.72,
    )

    ax.set_xticks(x)

    ax.set_xticklabels(
        [
            labels[str(x)]
            for x in sub["result_id"]
        ],
        rotation=20,
        ha="right",
    )

    ax.set_ylabel("RMSE")

    ax.set_title(
        "1982 development-validation mechanism ablation"
    )

    ax.grid(
        axis="y",
        alpha=0.20,
        linewidth=0.6,
    )

    ymax = float(
        np.nanmax(rmse)
    )

    ax.set_ylim(
        0,
        ymax * 1.18,
    )

    for bar, value in zip(
        bars,
        rmse,
    ):

        ax.text(
            bar.get_x()
            + bar.get_width() / 2,
            bar.get_height()
            + ymax * 0.018,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=7.5,
        )

    # Explicitly annotate the important diagnostic.
    fourier_rmse = float(
        sub[
            sub["result_id"]
            == "Fourier6_seasonal_null"
        ]["RMSE"].iloc[0]
    )

    anomaly_rmse = float(
        sub[
            sub["result_id"]
            == "best_temperature_anomaly"
        ]["RMSE"].iloc[0]
    )

    gain = (
        (fourier_rmse - anomaly_rmse)
        / fourier_rmse
        * 100.0
    )

    ax.text(
        0.99,
        0.97,
        (
            "T anomaly gain vs Fourier6: "
            f"{gain:.2f}%"
        ),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "fig2_mechanism_ablation",
    )


# =========================================================
# Figure 3
# External monthly consistency
# =========================================================

def figure_3():

    df = pd.read_csv(
        E4D1_MONTHLY,
        parse_dates=["month"],
    )

    required = {
        "month",
        "Q_external_monthly",
        "Q_R1_monthly",
        "Q_Fourier6_monthly",
    }

    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            f"Figure 3 missing columns: {missing}"
        )

    if len(df) != 12:
        raise RuntimeError(
            f"Expected 12 months, got {len(df)}"
        )

    fig, ax = plt.subplots(
        figsize=(7.2, 3.5)
    )

    ax.plot(
        df["month"],
        df["Q_external_monthly"],
        marker="o",
        linewidth=1.6,
        label="External monthly DSK",
    )

    ax.plot(
        df["month"],
        df["Q_R1_monthly"],
        marker="s",
        linewidth=1.2,
        label="R1 routing only",
    )

    ax.plot(
        df["month"],
        df["Q_Fourier6_monthly"],
        marker="^",
        linewidth=1.4,
        label="R1 + frozen Fourier6",
    )

    ax.set_xlabel("Month")
    ax.set_ylabel("Monthly discharge")

    ax.set_title(
        "1983 external monthly-series consistency"
    )

    ax.legend(
        frameon=False,
        ncol=3,
        loc="upper right",
    )

    ax.grid(
        axis="y",
        alpha=0.20,
        linewidth=0.6,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "fig3_external_monthly_consistency",
    )


# =========================================================
# Supplementary Figure S1
# T7 LOYO stability
# =========================================================

def figure_s1():

    df = pd.read_csv(
        E4B2C_YEARWISE
    )

    years = [
        1978,
        1979,
        1980,
        1981,
    ]

    gains = []

    for year in years:

        g = df[
            pd.to_numeric(
                df["holdout_year"],
                errors="coerce",
            )
            == year
        ]

        fourier = g[
            g["model"]
            == "C2_fourier6"
        ]

        t7 = g[
            g["model"]
            == "C3_T7_proxy"
        ]

        if (
            len(fourier) != 1
            or len(t7) != 1
        ):
            raise RuntimeError(
                f"Invalid LOYO rows for {year}"
            )

        f = float(
            fourier.iloc[0]["RMSE"]
        )

        t = float(
            t7.iloc[0]["RMSE"]
        )

        gain = (
            (f - t)
            / f
            * 100.0
        )

        gains.append(gain)

    fig, ax = plt.subplots(
        figsize=(5.5, 3.3)
    )

    x = np.arange(
        len(years)
    )

    bars = ax.bar(
        x,
        gains,
        width=0.62,
    )

    ax.axhline(
        0,
        linewidth=0.9,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(
        [str(x) for x in years]
    )

    ax.set_xlabel(
        "Held-out training year"
    )

    ax.set_ylabel(
        "T7 RMSE gain vs Fourier6 (%)"
    )

    ax.set_title(
        "Leave-one-year-out stability of the raw T7 proxy"
    )

    for bar, value in zip(
        bars,
        gains,
    ):
        y = (
            value + 0.35
            if value >= 0
            else value - 0.35
        )

        va = (
            "bottom"
            if value >= 0
            else "top"
        )

        ax.text(
            bar.get_x()
            + bar.get_width() / 2,
            y,
            f"{value:.1f}%",
            ha="center",
            va=va,
            fontsize=8,
        )

    ax.grid(
        axis="y",
        alpha=0.20,
        linewidth=0.6,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "figS1_T7_LOYO_stability",
    )


# =========================================================
# Supplementary Figure S2
# Bootstrap ΔRMSE uncertainty
# =========================================================

def figure_s2():

    df = pd.read_csv(
        E4B2C_BOOT
    )

    if len(df) != 1:
        raise RuntimeError(
            "Expected one bootstrap summary row."
        )

    row = df.iloc[0]

    center = float(
        row["mean_delta_rmse"]
    )

    low = float(
        row["ci_2_5"]
    )

    high = float(
        row["ci_97_5"]
    )

    fig, ax = plt.subplots(
        figsize=(5.5, 2.4)
    )

    ax.errorbar(
        [center],
        [0],
        xerr=[
            [
                center - low
            ],
            [
                high - center
            ],
        ],
        fmt="o",
        capsize=5,
    )

    ax.axvline(
        0,
        linewidth=1.0,
        linestyle="--",
    )

    ax.set_yticks([])

    ax.set_xlabel(
        "ΔRMSE = RMSE(Fourier6) − RMSE(T7)"
    )

    ax.set_title(
        "30-day moving-block bootstrap uncertainty"
    )

    ax.text(
        center,
        0.08,
        (
            f"95% CI [{low:.2f}, {high:.2f}]"
        ),
        ha="center",
        va="bottom",
        fontsize=8,
    )

    ax.set_ylim(
        -0.3,
        0.3,
    )

    ax.grid(
        axis="x",
        alpha=0.20,
        linewidth=0.6,
    )

    fig.tight_layout()

    save_figure(
        fig,
        "figS2_T7_bootstrap_delta_RMSE",
    )


# =========================================================
# Main
# =========================================================

def main():

    figure_1()
    figure_2()
    figure_3()
    figure_s1()
    figure_s2()

    expected = [
        "fig1_1983_daily_holdout",
        "fig2_mechanism_ablation",
        "fig3_external_monthly_consistency",
        "figS1_T7_LOYO_stability",
        "figS2_T7_bootstrap_delta_RMSE",
    ]

    for stem in expected:

        for ext in [
            ".png",
            ".pdf",
        ]:

            p = FIG / f"{stem}{ext}"

            if (
                not p.exists()
                or p.stat().st_size == 0
            ):
                raise RuntimeError(
                    f"Missing figure: {p}"
                )

    print()
    print("E5B complete")
    print("main_figures=3")
    print("supplementary_figures=2")
    print(
        "MODEL_REFIT_DURING_E5B=false"
    )
    print(
        "RESULTS_CHANGED_DURING_E5B=false"
    )
    print(
        "READY_FOR_E5C_RESULTS_WRITING=true"
    )


if __name__ == "__main__":
    main()