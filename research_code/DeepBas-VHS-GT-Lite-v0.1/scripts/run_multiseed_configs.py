from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from vhs.train import train_from_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a base VHS config with additional seeds.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/virtual_station_mainline/multisite_2005"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    generated = args.output_root / "generated_configs"
    generated.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        config = dict(base)
        config["seed"] = int(seed)
        config["output_dir"] = str(args.output_root / f"{args.name}_seed{seed}")
        config_path = generated / f"{args.name}_seed{seed}.yaml"
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        print(f"running {config_path}")
        train_from_config(config_path)


if __name__ == "__main__":
    main()
