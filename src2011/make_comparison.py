from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "2011"
OUT = REPORTS / "fig14_original_vs_reproduced.png"

ISPS = [
    "Comcast", "AT&T", "TimeWarner", "Verizon",
    "Cox", "Qwest", "Charter", "Cablevision",
]

PAPER_ACTIVE = {
    "Comcast": 560,
    "AT&T": 335,
    "TimeWarner": 381,
    "Verizon": 256,
    "Cox": 161,
    "Qwest": 117,
    "Charter": 51,
    "Cablevision": 53,
}

PAPER_LATENCY = {
    "Comcast": 10.36,
    "AT&T": 25.23,
    "TimeWarner": 11.87,
    "Verizon": 12.41,
    "Cox": 13.88,
    "Qwest": 39.42,
    "Charter": 11.87,
    "Cablevision": 10.21,
}

PAPER_LOSS = {
    "Comcast": 0.27,
    "AT&T": 0.48,
    "TimeWarner": 0.33,
    "Verizon": 0.51,
    "Cox": 1.11,
    "Qwest": 0.33,
    "Charter": 0.43,
    "Cablevision": 0.33,
}

PAPER_TOD = {"Cablevision": 40.0, "Cox": 20.0}

COLORS = {"paper": "#6c757d", "feb": "#1f77b4", "mar": "#2ca02c"}
LABELS = {
    "paper": "Paper (Dec 2010-Jan 2011)",
    "feb": "Reproduced Feb 2011",
    "mar": "Reproduced Mar 2011",
}


def table(month, name):
    return pd.read_csv(REPORTS / month / name, index_col=0)


def tod_drop(month, isp):
    t = pd.read_csv(REPORTS / month / "tod_throughput.csv")
    p = t[t["isp"] == isp].set_index("local_hour")["mean"]
    return float(100.0 * (1.0 - p[20] / p[3]))


def style(ax, title, ylabel, isps, rotate=25):
    ax.set_title(title, fontweight="bold", pad=10)
    ax.set_ylabel(ylabel)
    ax.set_xticks(np.arange(len(isps)))
    ax.set_xticklabels(isps, rotation=rotate, ha="right")
    ax.grid(axis="y", alpha=0.25, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def grouped(ax, values, isps):
    x = np.arange(len(isps))
    w = 0.26
    for i, key in enumerate(("paper", "feb", "mar")):
        vals = [values[key][isp] for isp in isps]
        ax.bar(x + (i - 1) * w, vals, w, label=LABELS[key],
               color=COLORS[key], edgecolor="white", linewidth=0.5)


def main():
    t2_feb = table("feb", "table2_analog.csv")
    t2_mar = table("mar", "table2_analog.csv")
    t4_feb = table("feb", "table4_proxy.csv")
    t4_mar = table("mar", "table4_proxy.csv")

    active = {
        "paper": PAPER_ACTIVE,
        "feb": {isp: float(t2_feb.loc[isp, "active_dl"]) for isp in ISPS},
        "mar": {isp: float(t2_mar.loc[isp, "active_dl"]) for isp in ISPS},
    }
    latency = {
        "paper": PAPER_LATENCY,
        "feb": {isp: float(t4_feb.loc[isp, "latency_mean"]) for isp in ISPS},
        "mar": {isp: float(t4_mar.loc[isp, "latency_mean"]) for isp in ISPS},
    }
    loss = {
        "paper": PAPER_LOSS,
        "feb": {isp: float(t4_feb.loc[isp, "loss_mean_pct"]) for isp in ISPS},
        "mar": {isp: float(t4_mar.loc[isp, "loss_mean_pct"]) for isp in ISPS},
    }

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.5))
    fig.suptitle(
        "2011 SIGCOMM gateway results: original paper vs FCC raw-data reproduction",
        fontsize=15, fontweight="bold", y=0.985,
    )

    grouped(axes[0, 0], active, ISPS)
    style(axes[0, 0], "(a) Active units by ISP", "Active units", ISPS)
    axes[0, 0].legend(frameon=False, fontsize=9)

    grouped(axes[0, 1], latency, ISPS)
    style(axes[0, 1], "(b) Median latency by ISP", "Latency (ms)", ISPS)

    grouped(axes[1, 0], loss, ISPS)
    style(axes[1, 0], "(c) Mean loss by ISP", "Loss (%)", ISPS)

    diurnal_isps = ["Cablevision", "Cox"]
    diurnal = {
        "paper": PAPER_TOD,
        "feb": {isp: tod_drop("feb", isp) for isp in diurnal_isps},
        "mar": {isp: tod_drop("mar", isp) for isp in diurnal_isps},
    }
    grouped(axes[1, 1], diurnal, diurnal_isps)
    style(axes[1, 1], "(d) Evening throughput drop (20:00 vs 03:00)",
          "Drop (%)", diurnal_isps, rotate=0)
    axes[1, 1].legend(frameon=False, fontsize=9)

    fig.text(
        0.5, 0.005,
        "Paper: Table 2 (active units), Table 4 (latency, loss), Fig. 8 text "
        "(Cablevision ~40%, Cox ~20%). Reproduction: FCC MBA raw bulk data, "
        "Feb/Mar 2011. Reproduced latency and loss are closest-target/e2e "
        "proxies, not the paper's first-hop metric; active-unit levels also "
        "reflect a larger, still-ramping deployment.",
        ha="center", va="bottom", fontsize=8.5, color="#444444",
    )

    fig.tight_layout(rect=(0, 0.045, 1, 0.965))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=180, bbox_inches="tight")
    print(OUT)


if __name__ == "__main__":
    main()
