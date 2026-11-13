from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "2011"
REPORTS = ROOT / "reports" / "2011"
OUT = REPORTS / "fig14_original_vs_reproduced.png"

MONTHS = ("feb", "mar")

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

COLORS = {"paper": "#6c757d", "pooled": "#1f77b4"}
LABELS = {
    "paper": "Paper (Dec 2010-Jan 2011)",
    "pooled": "Reproduced Feb-Mar 2011 (pooled)",
}


def read(month, name):
    return pd.read_csv(DATA / month / name)


def pooled_active():
    frames = []
    for month in MONTHS:
        d = read(month, "unit_throughput.csv")[["unit_id", "isp", "down_n"]]
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d = d.groupby("unit_id", as_index=False).agg(
        isp=("isp", "first"), down_n=("down_n", "sum")
    )
    d = d[d["down_n"] > 100]
    counts = d.groupby("isp")["unit_id"].nunique()
    return {isp: float(counts.get(isp, 0)) for isp in ISPS}


def pooled_weighted(name, col, ncol):
    frames = []
    for month in MONTHS:
        d = read(month, name)[["unit_id", "isp", col, ncol]].copy()
        d[col] = pd.to_numeric(d[col], errors="coerce")
        d[ncol] = pd.to_numeric(d[ncol], errors="coerce")
        d = d[d[ncol].gt(0) & d[col].notna()]
        d["_w"] = d[col] * d[ncol]
        g = d.groupby(["unit_id", "isp"], as_index=False).agg(
            _w=("_w", "sum"), n=(ncol, "sum")
        )
        g[col] = g["_w"] / g["n"]
        frames.append(g[["unit_id", "isp", col, "n"]])
    d = pd.concat(frames, ignore_index=True)
    d["_w"] = d[col] * d["n"]
    g = d.groupby(["unit_id", "isp"], as_index=False).agg(
        _w=("_w", "sum"), n=("n", "sum")
    )
    g[col] = g["_w"] / g["n"]
    return g[["unit_id", "isp", col, "n"]]


def pooled_latency_loss():
    e2e = pooled_weighted("latency_e2e_unit.csv", "e2e_baseline", "e2e_n")
    edge = pooled_weighted("latency_edge_unit.csv", "edge_baseline", "edge_n")
    e2e_loss = pooled_weighted("latency_e2e_unit.csv", "e2e_loss", "e2e_n")
    edge_loss = pooled_weighted("latency_edge_unit.csv", "edge_loss", "edge_n")
    for frame in (e2e, edge, e2e_loss, edge_loss):
        frame.drop(columns="n", inplace=True)
    d = e2e.merge(edge, on=["unit_id", "isp"], how="outer")
    d = d.merge(e2e_loss, on=["unit_id", "isp"], how="outer")
    d = d.merge(edge_loss, on=["unit_id", "isp"], how="outer")
    d["baseline_proxy"] = d[["e2e_baseline", "edge_baseline"]].min(axis=1)
    d["loss_proxy"] = d["e2e_loss"].fillna(d["edge_loss"])
    g = d.groupby("isp", as_index=False).agg(
        latency=("baseline_proxy", "mean"),
        loss=("loss_proxy", "mean"),
    )
    latency = {r.isp: float(r.latency) for r in g.itertuples()}
    loss = {r.isp: float(100.0 * r.loss) for r in g.itertuples()}
    return latency, loss


def pooled_tod(isp):
    frames = []
    for month in MONTHS:
        d = read(month, "tod_throughput.csv")
        frames.append(d[["isp", "local_hour", "mean", "count"]])
    d = pd.concat(frames, ignore_index=True)
    d["_w"] = d["mean"] * d["count"]
    g = d.groupby(["isp", "local_hour"], as_index=False).agg(
        _w=("_w", "sum"), count=("count", "sum")
    )
    g["mean"] = g["_w"] / g["count"]
    p = g[g["isp"] == isp].set_index("local_hour")["mean"]
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
    w = 0.34
    for i, key in enumerate(("paper", "pooled")):
        vals = [values[key][isp] for isp in isps]
        ax.bar(x + (i - 0.5) * w, vals, w, label=LABELS[key],
               color=COLORS[key], edgecolor="white", linewidth=0.5)


def main():
    active = pooled_active()
    latency, loss = pooled_latency_loss()
    diurnal_isps = ["Cablevision", "Cox"]
    diurnal = {isp: pooled_tod(isp) for isp in diurnal_isps}

    active_values = {"paper": PAPER_ACTIVE, "pooled": active}
    latency_values = {"paper": PAPER_LATENCY, "pooled": latency}
    loss_values = {"paper": PAPER_LOSS, "pooled": loss}
    diurnal_values = {
        "paper": PAPER_TOD,
        "pooled": diurnal,
    }

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.5))
    fig.suptitle(
        "2011 SIGCOMM gateway results: original paper vs Feb-Mar 2011 reproduction",
        fontsize=15, fontweight="bold", y=0.985,
    )

    grouped(axes[0, 0], active_values, ISPS)
    style(axes[0, 0], "(a) Active units by ISP", "Active units", ISPS)
    axes[0, 0].legend(frameon=False, fontsize=9)

    grouped(axes[0, 1], latency_values, ISPS)
    style(axes[0, 1], "(b) Baseline latency by ISP", "Latency (ms)", ISPS)

    grouped(axes[1, 0], loss_values, ISPS)
    style(axes[1, 0], "(c) Mean loss by ISP", "Loss (%)", ISPS)

    grouped(axes[1, 1], diurnal_values, diurnal_isps)
    style(axes[1, 1], "(d) Evening throughput drop (20:00 vs 03:00)",
          "Drop (%)", diurnal_isps, rotate=0)
    axes[1, 1].legend(frameon=False, fontsize=9)

    fig.text(
        0.5, 0.005,
        "Paper: Table 2 (active units), Table 4 (latency, loss), Fig. 8 text "
        "(Cablevision ~40%, Cox ~20%). Reproduction pools all February and "
        "March 2011 measurements into one window to mirror the paper's "
        "two-calendar-month window. Reproduced latency and loss are "
        "closest-target/e2e proxies, not the paper's first-hop metric; "
        "active-unit levels also reflect a larger, still-ramping deployment.",
        ha="center", va="bottom", fontsize=8.5, color="#444444",
    )

    fig.tight_layout(rect=(0, 0.045, 1, 0.965))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=180, bbox_inches="tight")
    print(OUT)
    print("pooled active", active)
    print("pooled latency", latency)
    print("pooled loss", loss)
    print("pooled diurnal", diurnal)


if __name__ == "__main__":
    main()
