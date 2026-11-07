from __future__ import annotations

import importlib.util
import platform
import sys


def installed(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> None:
    print(f"Python: {sys.version.split()[0]}")
    print(f"System: {platform.system()} {platform.release()}")
    for package in ["numpy", "pandas", "yaml", "sklearn", "torch", "xarray", "geopandas"]:
        print(f"{package:10s}: {'OK' if installed(package) else 'MISSING'}")

    if not installed("torch"):
        print("\nPyTorch 尚未安装；请先按 README 安装 CPU 或 CUDA 版本。")
        return

    import torch

    print(f"\nPyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA runtime: {torch.version.cuda}")
        for index in range(torch.cuda.device_count()):
            prop = torch.cuda.get_device_properties(index)
            memory_gb = prop.total_memory / 1024**3
            print(f"GPU {index}: {prop.name}, {memory_gb:.1f} GB")
        print("建议配置：device=auto, batch_size=32；显存不足时改为 8 或 16。")
    else:
        print("未发现可用 CUDA；演示和小型站点图仍可使用 CPU，只是训练更慢。")


if __name__ == "__main__":
    main()
