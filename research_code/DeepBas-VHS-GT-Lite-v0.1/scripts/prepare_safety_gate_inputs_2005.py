from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Separate gate inputs from sealed DSK labels.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/processed/virtual_station_multisite/multisite_discharge_2005.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/virtual_station_multisite/safety_gate_2005"),
    )
    args = parser.parse_args()
    frame = pd.read_csv(args.source, dtype={"station_id": str})
    target = frame.station_id == "00705700"
    gate_input = frame[[
        "date", "station_id", "station_code", "observed_q_m3s", "physical_reference_q_m3s"
    ]].copy()
    gate_input.loc[target, "observed_q_m3s"] = pd.NA
    label = frame.loc[target, ["date", "station_id", "observed_q_m3s"]].copy()
    label = label.rename(columns={"observed_q_m3s": "sealed_observed_q_m3s"})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gate_input.to_csv(args.output_dir / "gate_inputs_without_dsk_labels.csv", index=False)
    label.to_csv(args.output_dir / "sealed_dsk_labels.csv", index=False)
    print(f"gate rows={len(gate_input)}, sealed labels={len(label)}")


if __name__ == "__main__":
    main()

