import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C

TOP_ISPS = ["Comcast", "Charter", "TimeWarner", "AT&T", "Verizon", "Cox",
            "Cablevision", "CenturyLink", "Frontier", "Windstream",
            "Mediacom", "Cincinnati Bell"]
COLORS = plt.get_cmap("tab20").colors


def _read(out):
    annual = pd.read_csv(out / "annual_national.csv")
    isp = pd.read_csv(out / "annual_isp.csv")
    tech = pd.read_csv(out / "annual_technology.csv")
    mix = pd.read_csv(out / "target_mix.csv")
    cov = pd.read_csv(out / "coverage.csv")
    monthly = pd.read_csv(out / "monthly_national.csv")
    return annual, isp, tech, mix, cov, monthly


def _fig(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_national(annual, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, direction in zip(axes, ("down", "up")):
        x = annual["year"]
        ax.plot(x, annual[f"avg_{direction}_med"], "-o", lw=2,
                label="median of per-unit average")
        ax.plot(x, annual[f"p95_{direction}_med"], "-s", lw=2,
                label="median of per-unit p95")
        ax.fill_between(x, annual[f"avg_{direction}_p25"],
                        annual[f"avg_{direction}_p75"], alpha=0.18)
        ax.set_yscale("log")
        ax.set_xlabel("collection year")
        ax.set_ylabel("Mbit/s (log scale)")
        ax.set_title(f"{'Download' if direction == 'down' else 'Upload'} throughput")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    fig.suptitle("FCC MBA gateway throughput, annual collection years")
    _fig(out / "figures" / "fig01_national_throughput.png", )


def plot_isp(isp, out):
    latest = isp["year"].max()
    order = (isp[isp["year"].eq(latest)]
             .sort_values("n_units", ascending=False)["isp"].tolist())
    keep = [x for x in TOP_ISPS if x in order] + [x for x in order
                                                  if x not in TOP_ISPS][:4]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for i, name in enumerate(keep):
        d = isp[isp["isp"].eq(name)].sort_values("year")
        if d.empty:
            continue
        axes[0].plot(d["year"], d["avg_down_med"], "-o", ms=3,
                     color=COLORS[i % len(COLORS)], label=name)
        axes[1].plot(d["year"], d["avg_up_med"], "-o", ms=3,
                     color=COLORS[i % len(COLORS)], label=name)
    for ax, label in zip(axes, ("download", "upload")):
        ax.set_yscale("log")
        ax.set_xlabel("collection year")
        ax.set_ylabel("median per-unit average Mbit/s")
        ax.set_title(f"{label} by ISP")
        ax.grid(alpha=0.25)
    axes[1].legend(fontsize=7, ncol=2)
    fig.suptitle("ISP gateway throughput trajectories")
    _fig(out / "figures" / "fig02_isp_throughput.png")


def plot_powerboost(annual, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    a = annual[annual["year"] <= 2015]
    axes[0].plot(a["year"], a["pb_down_med"], "-o", label="download")
    axes[0].plot(a["year"], a["pb_up_med"], "-s", label="upload")
    axes[0].set_title("Snapshot PowerBoost (2011-2015)")
    axes[0].set_ylabel("last / first interval throughput")
    axes[0].legend()
    axes[1].plot(annual["year"], annual["burst_down_med"], "-o", label="download")
    axes[1].plot(annual["year"], annual["burst_up_med"], "-s", label="upload")
    axes[1].set_title("Warmup burst ratio (all years)")
    axes[1].set_ylabel("final / warmup throughput")
    axes[1].legend()
    for ax in axes:
        ax.set_xlabel("collection year")
        ax.grid(alpha=0.25)
        ax.axhline(1.0, color="black", lw=0.8, alpha=0.4)
    fig.suptitle("Burst behaviour across the 2016 test-design change")
    _fig(out / "figures" / "fig03_powerboost_burst.png")


def plot_diurnal(isp, annual, out):
    latest = isp["year"].max()
    order = (isp[isp["year"].eq(latest)]
             .sort_values("n_units", ascending=False)["isp"].tolist())
    keep = [x for x in TOP_ISPS if x in order]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for i, name in enumerate(keep):
        d = isp[isp["isp"].eq(name)].sort_values("year")
        d = d[d["diurnal_down_pct_med"].notna()]
        if d.empty:
            continue
        ax.plot(d["year"], 100 * d["diurnal_down_pct_med"], "-o", ms=3,
                color=COLORS[i % len(COLORS)], label=name)
    ax.plot(annual["year"], 100 * annual["diurnal_down_pct_med"], "k--",
            lw=2, label="national median")
    ax.set_xlabel("collection year")
    ax.set_ylabel("evening vs night drop (%)")
    ax.set_title("Diurnal download congestion (20-22h vs 3-5h local time)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    _fig(out / "figures" / "fig04_diurnal.png")


def plot_latency(annual, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    axes[0].plot(annual["year"], annual["baseline_p10_ms_med"], "-o")
    axes[0].set_ylabel("p10 idle RTT (ms)")
    axes[0].set_title("Baseline latency")
    axes[1].plot(annual["year"], annual["underload_down_ratio_med"], "-o",
                 label="download load")
    axes[1].plot(annual["year"], annual["underload_up_ratio_med"], "-s",
                 label="upload load")
    axes[1].set_ylabel("under-load / idle median RTT")
    axes[1].set_title("Latency under load")
    axes[1].legend()
    for ax in axes:
        ax.set_xlabel("collection year")
        ax.grid(alpha=0.25)
    fig.suptitle("Gateway latency")
    _fig(out / "figures" / "fig05_latency.png")


def plot_loss_jitter(annual, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    axes[0].plot(annual["year"], 100 * annual["loss_idle_med"], "-o",
                 label="idle")
    axes[0].plot(annual["year"], 100 * annual["loss_down_med"], "-s",
                 label="download load")
    axes[0].plot(annual["year"], 100 * annual["loss_up_med"], "-^",
                 label="upload load")
    axes[0].set_ylabel("loss (%)")
    axes[0].set_title("Packet loss")
    axes[0].legend()
    axes[1].plot(annual["year"], annual["jitter_down_us_med"], "-o",
                 label="download")
    axes[1].plot(annual["year"], annual["jitter_up_us_med"], "-s",
                 label="upload")
    axes[1].set_ylabel("UDP jitter (microseconds)")
    axes[1].set_title("Jitter")
    axes[1].legend()
    for ax in axes:
        ax.set_xlabel("collection year")
        ax.grid(alpha=0.25)
    fig.suptitle("Gateway loss and jitter")
    _fig(out / "figures" / "fig06_loss_jitter.png")


def plot_targets(mix, cov, out):
    years = sorted(mix["year"].unique())
    shares = mix.groupby("year")[[c for c in mix.columns
                                  if c.startswith("share_")]].mean()
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    bottom = np.zeros(len(shares))
    labels = [c.replace("share_n_down_", "") for c in shares.columns]
    for i, c in enumerate(shares.columns):
        axes[0].bar([str(y) for y in shares.index], shares[c], bottom=bottom,
                    label=labels[i], color=COLORS[i % len(COLORS)])
        bottom += shares[c].fillna(0).to_numpy()
    axes[0].set_title("Download target mix")
    axes[0].set_ylabel("share of tests")
    axes[0].legend(fontsize=7)
    axes[0].tick_params(axis="x", rotation=60)
    c = cov.groupby("year")[["known_isp_frac", "known_tech_frac",
                             "tz_missing_frac"]].mean()
    axes[1].plot(c.index, 100 * c["known_isp_frac"], "-o", label="ISP known")
    axes[1].plot(c.index, 100 * c["known_tech_frac"], "-s", label="tech known")
    axes[1].plot(c.index, 100 * c["tz_missing_frac"], "-^", label="tz missing")
    axes[1].set_ylim(0, 105)
    axes[1].set_ylabel("percent of units / months")
    axes[1].set_title("Profile coverage")
    axes[1].legend()
    axes[1].grid(alpha=0.25)
    for ax in axes:
        ax.set_xlabel("collection year")
    fig.suptitle("Measurement targets and metadata coverage")
    _fig(out / "figures" / "fig07_targets_coverage.png")


def plot_units(tech, annual, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    axes[0].plot(annual["year"], annual["n_units"], "-o", label="all units")
    axes[0].plot(annual["year"], annual["n_active"], "-s", label="active (>20 tests)")
    axes[0].set_title("Units with data")
    axes[0].set_ylabel("count")
    axes[0].legend()
    keep = [t for t in ["Cable", "DSL", "Fiber", "Fixed Wireless", "Satellite"]
            if t in set(tech["technology"])]
    for i, t in enumerate(keep):
        d = tech[tech["technology"].eq(t)].sort_values("year")
        axes[1].plot(d["year"], d["n_units"], "-o", ms=3,
                     color=COLORS[i % len(COLORS)], label=t)
    axes[1].set_title("Units by technology")
    axes[1].set_ylabel("count")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.set_xlabel("collection year")
        ax.grid(alpha=0.25)
    fig.suptitle("Deployment coverage")
    _fig(out / "figures" / "fig08_units_technology.png")


def _fmt(x, digits=2):
    if pd.isna(x):
        return "n/a"
    return f"{x:.{digits}f}"


def write_report(annual, isp, tech, mix, cov, out, reports):
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "figures").mkdir(parents=True, exist_ok=True)
    for path in (out / "figures").glob("*.png"):
        (reports / "figures" / path.name).write_bytes(path.read_bytes())

    latest = annual.sort_values("year").iloc[-1]
    first = annual.sort_values("year").iloc[0]
    lines = []
    lines.append("# Multi-year FCC MBA gateway trends (2011-2023)\n")
    lines.append("This report extends the 2011 SIGCOMM gateway reproduction "
                 "to all available FCC Measuring Broadband America raw months. "
                 "The unit of analysis is the gateway measurement: active "
                 "throughput, idle and under-load latency, loss, jitter, and "
                 "diurnal throughput. All available raw tarballs are streamed "
                 "directly from the `mba-data` object store; no raw data are "
                 "stored in the repository.\n")
    lines.append("## Data and method\n")
    lines.append(f"- Collection years: {int(annual['year'].min())}-"
                 f"{int(annual['year'].max())}; "
                 f"{len(cov)} processed year-month files.\n")
    lines.append("- Per-unit monthly metrics are computed from "
                 "`curr_httpgetmt`, `curr_httppostmt`, `curr_ping`, "
                 "`curr_dlping`, `curr_ulping`, and `curr_udpjitter`.\n")
    lines.append("- Throughput is final `bytes_sec`; PowerBoost is the last "
                 "over the first 5-second interval for 2011-2015. From 2016 "
                 "each test is single-shot, so a warmup burst ratio "
                 "(final / warmup throughput) is reported instead.\n")
    lines.append("- Under-load latency ratios use average RTT during "
                 "download/upload probes divided by idle average RTT.\n")
    lines.append("- Local time uses the FCC profile timezone offsets, with "
                 "US DST applied; diurnal swing compares 20:00-22:00 with "
                 "03:00-05:00 local time.\n")
    lines.append("- Target classes are M-Lab, Level3, SamKnows, ISP-hosted, "
                 "and other. The mix changes sharply across years, so absolute "
                 "throughput is not a clean cross-era comparison; normalized "
                 "and within-unit metrics are the main trend evidence.\n")
    lines.append("\n## Key results\n")
    lines.append(f"- Median unit-month average download grew from "
                 f"{_fmt(first['avg_down_med'],1)} Mbit/s in "
                 f"{int(first['year'])} to {_fmt(latest['avg_down_med'],1)} "
                 f"Mbit/s in {int(latest['year'])}.\n")
    lines.append(f"- Median unit-month average upload grew from "
                 f"{_fmt(first['avg_up_med'],1)} to "
                 f"{_fmt(latest['avg_up_med'],1)} Mbit/s over the same period.\n")
    lines.append(f"- Median unit-month diurnal download drop fell from "
                 f"{_fmt(100*first['diurnal_down_pct_med'],1)}% to "
                 f"{_fmt(100*latest['diurnal_down_pct_med'],1)}%.\n")
    lines.append(f"- Median per-unit p10 baseline idle RTT moved from "
                 f"{_fmt(first['baseline_p10_ms_med'],1)} ms to "
                 f"{_fmt(latest['baseline_p10_ms_med'],1)} ms; median "
                 f"download under-load ratio from "
                 f"{_fmt(first['underload_down_ratio_med'],1)}x to "
                 f"{_fmt(latest['underload_down_ratio_med'],1)}x.\n")
    lines.append(f"- Median UDP jitter (sparse in 2011, broadly available "
                 f"from 2012) is "
                 f"{_fmt(latest['jitter_down_us_med'],0)} microseconds "
                 f"downstream in {int(latest['year'])}.\n")
    lines.append("\n## Figures\n")
    for name, caption in [
        ("fig01_national_throughput.png", "National throughput trend."),
        ("fig02_isp_throughput.png", "ISP throughput trajectories."),
        ("fig03_powerboost_burst.png", "PowerBoost and warmup burst ratios."),
        ("fig04_diurnal.png", "Diurnal congestion by ISP."),
        ("fig05_latency.png", "Baseline latency and latency under load."),
        ("fig06_loss_jitter.png", "Loss and jitter."),
        ("fig07_targets_coverage.png", "Target mix and profile coverage."),
        ("fig08_units_technology.png", "Units and technology mix."),
    ]:
        lines.append(f"![{caption}](figures/{name})\n")
    lines.append("\n## Caveats\n")
    lines.append("- Data availability: 2023-03 contains no gateway test "
                 "members; 2016-07 lacks upload under-load probes; 2020-01 "
                 "lacks download and upload under-load probes. A small number "
                 "of malformed multi-target rows in 2021-03 were skipped.\n")
    lines.append("- The 2011 paper's exact Dec 2010-Jan 2011 window is not in "
                 "the archive; the trend uses available collection months.\n")
    lines.append("- The 2016 test redesign removes the six-snapshot "
                 "PowerBoost; the warmup burst ratio is not identical.\n")
    lines.append("- ISP/technology labels come from each year's FCC profile. "
                 "Units absent from the profile are kept in national totals "
                 "but excluded from ISP/technology splits; coverage is shown "
                 "in Figure 7.\n")
    lines.append("- Target hostnames change by year and hosting network. "
                 "Absolute throughput levels partly reflect target changes.\n")
    lines.append("- No traceroute/first-hop data are used; latency is "
                 "gateway-to-target, not strictly last-mile.\n")
    lines.append("\n## Files\n")
    lines.append("- `output/trends/annual_national.csv`, "
                 "`annual_isp.csv`, `annual_technology.csv`, "
                 "`monthly_national.csv`, `target_mix.csv`, `coverage.csv`\n")
    lines.append("- `output/trends/unit_month_metrics.parquet` "
                 "(per-unit monthly metrics)\n")
    (reports / "REPORT.md").write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(C.OUT))
    ap.add_argument("--reports", default=str(C.REPORTS))
    args = ap.parse_args()
    out = Path(args.out)
    reports = Path(args.reports)
    annual, isp, tech, mix, cov, monthly = _read(out)
    plot_national(annual, out)
    plot_isp(isp, out)
    plot_powerboost(annual, out)
    plot_diurnal(isp, annual, out)
    plot_latency(annual, out)
    plot_loss_jitter(annual, out)
    plot_targets(mix, cov, out)
    plot_units(tech, annual, out)
    write_report(annual, isp, tech, mix, cov, out, reports)
    print(f"wrote figures and {reports/'REPORT.md'}")


if __name__ == "__main__":
    main()
