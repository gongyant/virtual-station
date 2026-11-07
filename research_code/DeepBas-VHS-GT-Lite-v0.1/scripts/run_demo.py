from __future__ import annotations

import argparse

from vhs.train import train_from_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an end-to-end synthetic virtual-station demo")
    parser.add_argument("--config", default="configs/demo.yaml")
    args = parser.parse_args()
    train_from_config(args.config)


if __name__ == "__main__":
    main()

