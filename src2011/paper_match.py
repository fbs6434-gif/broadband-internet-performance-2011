import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import ISP8, add_local_time, is_mlab, load_meta, load_tz, parquet

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "2011"
OUT = REPORTS / "fig14_paper_matched.png"
CSV = REPORTS / "paper_matched_metrics.csv"

START = pd.Timestamp("2011-02-01 00:00:00")
END = pd.Timestamp("2011-03-04 00:00:00")
MONTHS = ("feb", "mar")

PAPER_T2 = {
    "Comcast": (864, 560),
    "AT&T": (787, 335),
    "TimeWarner": (690, 381),
    "Verizon": (551, 256),
    "Cox": (381, 161),
    "Qwest": (265, 117),
    "Charter": (187, 51),
    "Cablevision": (104, 53),
}
PAPER_T4 = {
    "AT&T": (25.23, 0.48),
    "Comcast": (10.36, 0.27),
    "TimeWarner": (11.87, 0.33),
    "Verizon": (12.41, 0.51),
    "Charter": (11.87, 0.43),
    "Cox": (13.88, 1.11),
    "Qwest": (39.42, 0.33),
    "Cablevision": (10.21, 0.33),
}
PAPER_TOD = {"Cablevision": 40.0, "Cox": 20.0}

COLORS = {"paper": "#6c757d", "matched": "#1f77b4"}
LABELS = {"paper": "Paper (14 Dec-14 Jan)", "matched": "Matched (1 Feb-3 Mar)"}


def window_frame(month, kind, columns, numeric=()):
    d = pd.read_parquet(parquet(month, kind), columns=columns)
    d = d[(d["dtime"] >= START) & (d["dtime"] < END)].copy()
    for c in numeric:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def load_down():
    frames = [
        window_frame(
            m,
            "tests_down",
            ["unit_id", "dtime", "target", "mbps"],
            ("mbps",),
        )
        for m in MONTHS
    ]
    d = pd.concat(frames, ignore_index=True)
    return d[d["mbps"].notna()]


def active_table(down, meta):
    n = (
        down.merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
        .groupby(["unit_id", "isp"])
        .size()
        .rename("n")
        .reset_index()
    )
    active = n[n["n"] > 100].groupby("isp")["unit_id"].nunique()
    total = meta.groupby("isp")["unit_id"].nunique()
    paper = pd.DataFrame(
        PAPER_T2.values(), index=PAPER_T2.keys(), columns=["paper_total", "paper_active"]
    )
    t = paper.join(
        pd.DataFrame({"repro_total": total, "repro_active": active}), how="outer"
    )
    t = t.reindex(ISP8).fillna(0).astype(int)
    t["paper_share"] = 100.0 * t["paper_active"] / t["paper_total"]
    t["repro_share"] = 100.0 * t["repro_active"] / t["repro_total"]
    return t


def latency_table(meta):
    frames = [
        window_frame(
            m,
            "ping",
            ["unit_id", "dtime", "target", "rtt_avg", "successes", "failures"],
            ("rtt_avg", "successes", "failures"),
        )
        for m in MONTHS
    ]
    p = pd.concat(frames, ignore_index=True)
    p = p[(p["successes"] + p["failures"]) > 0]
    p = p[p["rtt_avg"].notna()].copy()
    p["rtt_ms"] = p["rtt_avg"] / 1000.0
    p["mlab"] = is_mlab(p["target"])

    g = (
        p.groupby(["unit_id", "target"])
        .agg(n=("rtt_ms", "size"), median=("rtt_ms", "median"), mlab=("mlab", "first"))
        .reset_index()
    )
    g = g[g["n"] > 100]
    chosen = (
        g.sort_values(["unit_id", "mlab", "median"])
        .groupby("unit_id", as_index=False)
        .first()
    )
    q = p.merge(chosen[["unit_id", "target"]], on=["unit_id", "target"], how="inner")
    u = (
        q.groupby("unit_id")
        .agg(
            latency_mean=("rtt_ms", "mean"),
            latency_p10=("rtt_ms", lambda x: x.quantile(0.10)),
            n=("rtt_ms", "size"),
        )
        .reset_index()
        .merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
    )
    u = u[u["n"] > 100]
    t = (
        u.groupby("isp")
        .agg(
            repro_latency=("latency_mean", "mean"),
            repro_latency_std=("latency_mean", "std"),
            repro_latency_p10=("latency_p10", "mean"),
            units=("unit_id", "nunique"),
        )
        .reindex(ISP8)
    )
    t["paper_latency"] = [PAPER_T4[i][0] for i in ISP8]
    return t


def loss_table(meta):
    frames = [
        window_frame(
            m,
            "udplatency",
            ["unit_id", "dtime", "target", "successes", "failures"],
            ("successes", "failures"),
        )
        for m in MONTHS
    ]
    p = pd.concat(frames, ignore_index=True)
    p = p[(p["successes"] + p["failures"]) > 0]
    p = p[is_mlab(p["target"])]
    u = (
        p.groupby("unit_id")
        .agg(sent=("successes", "sum"), failed=("failures", "sum"))
        .reset_index()
    )
    u["loss_pct"] = 100.0 * u["failed"] / u["sent"]
    u = u[u["sent"] > 100].merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
    t = (
        u.groupby("isp")
        .agg(
            repro_loss=("loss_pct", "mean"),
            repro_loss_std=("loss_pct", "std"),
            units=("unit_id", "nunique"),
        )
        .reindex(ISP8)
    )
    t["paper_loss"] = [PAPER_T4[i][1] for i in ISP8]
    return t


def tod_table(down, meta, tz):
    d = down.merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
    d = add_local_time(d, tz, "mar")
    p95 = d.groupby("unit_id")["mbps"].quantile(0.95).rename("p95")
    d = d.merge(p95, on="unit_id")
    d = d[d["p95"] > 0].copy()
    d["norm"] = d["mbps"] / d["p95"]
    uh = d.groupby(["unit_id", "isp", "local_hour"])["norm"].mean().reset_index()
    hh = uh.groupby(["isp", "local_hour"])["norm"].mean().unstack()
    drop = 100.0 * (1.0 - hh[20] / hh[3])
    return drop


def style(ax, title, ylabel, isps, rotate=25):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_xticks(np.arange(len(isps)))
    ax.set_xticklabels(isps, rotation=rotate, ha="right" if rotate else "center")
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)


def grouped(ax, paper, repro, isps, fmt="{:.1f}"):
    x = np.arange(len(isps))
    w = 0.34
    ax.bar(
        x - w / 2,
        [paper[i] for i in isps],
        w,
        label=LABELS["paper"],
        color=COLORS["paper"],
        edgecolor="white",
        linewidth=0.5,
    )
    ax.bar(
        x + w / 2,
        [repro[i] for i in isps],
        w,
        label=LABELS["matched"],
        color=COLORS["matched"],
        edgecolor="white",
        linewidth=0.5,
    )
    for xi, ri in zip(x + w / 2, [repro[i] for i in isps]):
        ax.text(xi, ri, fmt.format(ri), ha="center", va="bottom", fontsize=6.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--csv", default=str(CSV))
    args = ap.parse_args()

    meta = load_meta()
    tz = load_tz()
    down = load_down()
    active = active_table(down, meta)
    latency = latency_table(meta)
    loss = loss_table(meta)
    tod = tod_table(down, meta, tz)

    isps = ISP8
    paper_active = {i: PAPER_T2[i][1] for i in isps}
    repro_active = active["repro_active"].to_dict()
    paper_lat = {i: PAPER_T4[i][0] for i in isps}
    repro_lat = latency["repro_latency"].to_dict()
    paper_loss = {i: PAPER_T4[i][1] for i in isps}
    repro_loss = loss["repro_loss"].to_dict()
    paper_tod = PAPER_TOD
    repro_tod = tod.loc[["Cablevision", "Cox"]].to_dict()

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.5))
    fig.suptitle(
        "Paper-matched reproduction: 31-day window, paper metrics, closest target",
        fontsize=14,
        fontweight="bold",
        y=0.985,
    )

    grouped(axes[0, 0], paper_active, repro_active, isps, "{:.0f}")
    style(axes[0, 0], "(a) Active units (>100 download tests)", "Active units", isps)
    axes[0, 0].legend(frameon=False, fontsize=9)

    grouped(axes[0, 1], paper_lat, repro_lat, isps)
    style(axes[0, 1], "(b) Mean latency to closest available target", "Latency (ms)", isps)
    axes[0, 1].legend(frameon=False, fontsize=9)

    grouped(axes[1, 0], paper_loss, repro_loss, isps, "{:.2f}")
    style(axes[1, 0], "(c) Mean end-to-end UDP loss", "Loss (%)", isps)

    grouped(
        axes[1, 1],
        paper_tod,
        repro_tod,
        ["Cablevision", "Cox"],
        "{:.1f}",
    )
    style(
        axes[1, 1],
        "(d) Evening throughput drop (20:00 vs 03:00)",
        "Drop (%)",
        ["Cablevision", "Cox"],
        rotate=0,
    )
    axes[1, 1].legend(frameon=False, fontsize=9)

    fig.text(
        0.5,
        0.005,
        "Window: 2011-02-01 to 2011-03-04 (31 days), matching the paper's 31-day window. "
        "Active: >100 M-Lab download tests. Latency: mean ICMP RTT to the closest ISP "
        "target with >100 pings; first-hop/traceroute is unavailable, so this is an "
        "upper bound. Loss: end-to-end UDP to M-Lab, >100 packets, per-unit aggregate "
        "(the paper's target). Diurnal: local 20:00 vs 03:00.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=180, bbox_inches="tight")
    print(f"wrote {args.out}")

    out = pd.DataFrame(
        {
            "paper_total": [PAPER_T2[i][0] for i in isps],
            "paper_active": [PAPER_T2[i][1] for i in isps],
            "repro_active": [repro_active[i] for i in isps],
            "paper_active_share": [100.0 * PAPER_T2[i][1] / PAPER_T2[i][0] for i in isps],
            "repro_active_share": [active.loc[i, "repro_share"] for i in isps],
            "paper_latency_ms": [paper_lat[i] for i in isps],
            "repro_latency_ms": [repro_lat[i] for i in isps],
            "repro_latency_std": [latency.loc[i, "repro_latency_std"] for i in isps],
            "repro_latency_p10_ms": [latency.loc[i, "repro_latency_p10"] for i in isps],
            "paper_loss_pct": [paper_loss[i] for i in isps],
            "repro_loss_pct": [repro_loss[i] for i in isps],
            "repro_loss_std": [loss.loc[i, "repro_loss_std"] for i in isps],
        },
        index=isps,
    )
    out["paper_drop_pct"] = [PAPER_TOD.get(i, np.nan) for i in isps]
    out["repro_drop_pct"] = [tod.get(i, np.nan) for i in isps]
    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.csv, float_format="%.4f")
    print(f"wrote {args.csv}")
    print(out.round(2).to_string())


if __name__ == "__main__":
    main()
