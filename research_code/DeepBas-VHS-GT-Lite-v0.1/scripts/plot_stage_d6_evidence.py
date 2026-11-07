import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "diagnosis_2005_snapshot"
OUT = BASE / "stage_d6" / "plots" / "model_evidence_overview"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_csv(BASE / "stage_d6" / "experiment_registry_A_to_D5.csv")
    key_ids = ["A_PHY", "A_GNN", "A_NG", "B1_G1_self_loops", "C_K10_LEGACY", "C_KERNEL_LEGACY", "D4B_primary", "D5R2_M0", "D5R2_M1", "D5R2_M2", "D5R4_M2C"]
    labels = ["MQ\n2005", "GNN\n2005", "No graph\n2005", "Self-loop\n2005", "K10\nlegacy", "Kernel\nlegacy", "K10\n2011", "M0\nLOYO", "M1\nLOYO", "M2\nLOYO", "M2C\nLOYO"]
    picked = [next(r for r in rows if r["experiment_id"] == i) for i in key_ids]
    vals = [float(r["NSE"]) for r in picked]
    colors = ["#6b7280"] * 4 + ["#2563eb", "#2563eb", "#dc2626"] + ["#7c3aed"] * 4
    fig, ax = plt.subplots(figsize=(12, 5.6))
    bars = ax.bar(np.arange(len(vals)), vals, color=colors)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_ylabel("NSE (existing recorded metric)")
    ax.set_title("Evidence overview - protocols differ; bars are not one ranking table")
    ax.set_xticks(np.arange(len(vals)))
    ax.set_xticklabels(labels)
    ax.grid(axis="y", alpha=0.25)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + (0.025 if v >= 0 else -0.04), "{:.3f}".format(v), ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    fig.tight_layout()
    fig.savefig(str(OUT / "nse_evidence_by_protocol.png"), dpi=180)
    plt.close(fig)

    r2 = read_csv(BASE / "stage_d5_round2" / "outer_year_metrics.csv")
    r4 = read_csv(BASE / "stage_d5_round4" / "m2c_nested_loyo_results.csv")
    by_model = {}
    for model in ["M0", "M2"]:
        by_model[model] = {int(x["year"]): float(x["rmse"]) for x in r2 if x["row_type"] == "year" and x["model"] == model}
    by_model["M2C"] = {int(x["year"]): float(x["rmse"]) for x in r4 if x["row_type"] == "year"}
    years = sorted(by_model["M0"])
    fig, ax = plt.subplots(figsize=(9.5, 5.3))
    for model, color in [("M0", "#6b7280"), ("M2", "#2563eb"), ("M2C", "#dc2626")]:
        ax.plot(years, [by_model[model][y] for y in years], marker="o", label=model, color=color)
    ax.set_title("Cross-year RMSE: improvements are not uniform")
    ax.set_xlabel("Held-out year")
    ax.set_ylabel("RMSE (m3/s)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(OUT / "loyo_rmse_by_year.png"), dpi=180)
    plt.close(fig)

    labels = [">=2 years DSK stage", "control state", "interval inflow Q", "new untouched full year"]
    fig, ax = plt.subplots(figsize=(8.2, 2.8))
    ax.imshow(np.array([[0, 0, 0, 0]]), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_yticks([0])
    ax.set_yticklabels(["available in project"])
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=18, ha="right")
    for i in range(len(labels)):
        ax.text(i, 0, "NO", ha="center", va="center", color="white", fontweight="bold")
    ax.set_title("Information gate for further model expansion")
    fig.tight_layout()
    fig.savefig(str(OUT / "new_information_gate.png"), dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
