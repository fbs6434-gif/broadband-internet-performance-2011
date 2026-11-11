import shutil
from pathlib import Path

from common import OUT, ROOT

DEST = ROOT / "reports" / "2011"
KEEP = [
    "fig*.png",
    "table2_analog.csv",
    "table4_analog.csv",
    "table4_proxy.csv",
    "isp_throughput.csv",
    "powerboost_curve.csv",
    "tod_throughput.csv",
    "tod_loss.csv",
    "under_load_*.csv",
    "summary.json",
    "report_summary.json",
]


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT / "REPORT.md", DEST / "REPORT.md")
    for month in ("feb", "mar"):
        src = OUT / month
        if not src.exists():
            continue
        dst = DEST / month
        dst.mkdir(parents=True, exist_ok=True)
        for pat in KEEP:
            for f in src.glob(pat):
                shutil.copy2(f, dst / f.name)
    print(f"published to {DEST}")


if __name__ == "__main__":
    main()
