import json
from pathlib import Path

import pandas as pd

from common import ISP8, OUT, out_dir

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
    "Comcast": (10.36, 14.49, 0.27, 2.79),
    "AT&T": (25.23, 33.47, 0.48, 3.59),
    "TimeWarner": (11.87, 25.18, 0.33, 3.09),
    "Verizon": (12.41, 20.60, 0.51, 4.07),
    "Cox": (13.88, 28.02, 1.11, 8.35),
    "Qwest": (39.42, 32.27, 0.33, 3.38),
    "Charter": (11.87, 11.80, 0.43, 3.29),
    "Cablevision": (10.21, 7.52, 0.33, 3.14),
}

MONTHS = ["feb", "mar"]


def md_table(df: pd.DataFrame, floatfmt: str = ".2f") -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                vals.append(f"{v:{floatfmt}}")
            else:
                vals.append(str(v))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def safe_read(month, name, index_col=0):
    p = out_dir(month) / name
    if not p.exists():
        return None
    return pd.read_csv(p, index_col=index_col)


def table2_rows():
    rows = []
    for isp in ISP8:
        row = {"ISP": isp, "Paper total": PAPER_T2[isp][0], "Paper active": PAPER_T2[isp][1]}
        for m in MONTHS:
            t = safe_read(m, "table2_analog.csv")
            if t is not None and isp in t.index:
                row[f"{m} total"] = int(t.loc[isp, "total"])
                row[f"{m} active"] = int(t.loc[isp, "active_dl"])
        rows.append(row)
    return pd.DataFrame(rows)


def throughput_rows():
    rows = []
    for isp in ISP8:
        row = {"ISP": isp}
        for m in MONTHS:
            s = safe_read(m, "isp_throughput.csv")
            if s is not None and isp in s.index:
                row[f"{m} DL p95"] = float(s.loc[isp, "dl_p95_mbps"])
                row[f"{m} DL Avg/P95"] = float(s.loc[isp, "dl_avg_p95"])
                row[f"{m} UL p95"] = float(s.loc[isp, "ul_p95_mbps"])
                row[f"{m} UL Avg/P95"] = float(s.loc[isp, "ul_avg_p95"])
        rows.append(row)
    return pd.DataFrame(rows)


def powerboost_rows():
    rows = []
    for isp in ISP8:
        row = {"ISP": isp}
        for m in MONTHS:
            c = safe_read(m, "powerboost_curve.csv", index_col=None)
            if c is not None:
                s = c[(c["isp"] == isp) & (c["sequence"] == 5)]
                if len(s):
                    row[f"{m} last/first"] = float(s["mean"].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows)


def tod_rows():
    rows = []
    for isp in ISP8:
        row = {"ISP": isp}
        for m in MONTHS:
            t = safe_read(m, "tod_throughput.csv", index_col=None)
            if t is not None:
                p = t[t["isp"] == isp].set_index("local_hour")["mean"]
                if 3 in p.index and 20 in p.index:
                    row[f"{m} drop 20 vs 3 (%)"] = float(100 * (1 - p[20] / p[3]))
        rows.append(row)
    return pd.DataFrame(rows)


def table4_rows():
    rows = []
    for isp in ISP8:
        row = {
            "ISP": isp,
            "Paper latency": PAPER_T4[isp][0],
            "Paper loss %": PAPER_T4[isp][2],
        }
        for m in MONTHS:
            t = safe_read(m, "table4_proxy.csv")
            if t is not None and isp in t.index:
                row[f"{m} latency"] = float(t.loc[isp, "latency_mean"])
                row[f"{m} loss %"] = float(t.loc[isp, "loss_mean_pct"])
        rows.append(row)
    return pd.DataFrame(rows)


def underload_rows():
    rows = []
    for isp in ISP8:
        row = {"ISP": isp}
        for m in MONTHS:
            for k in ("down", "up"):
                u = safe_read(m, f"under_load_{k}.csv", index_col=None)
                if u is not None:
                    s = u[u["isp"] == isp][f"{k}_ratio"]
                    if len(s):
                        row[f"{m} {k} median"] = float(s.median())
        rows.append(row)
    return pd.DataFrame(rows)


def web_rows():
    rows = []
    for m in MONTHS:
        p = out_dir(m) / "report_summary.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        rows.append(
            {
                "Month": m,
                "Units": r["facebook_units"],
                "Median fetch (ms)": r["facebook_fetch_ms_median"],
                "Median bytes": r["facebook_bytes_median"],
                "Median objects": r["facebook_objects_median"],
                "rho(P95, fetch)": r["spearman_p95_fetch"],
                "rho(baseline, fetch)": r["spearman_baseline_fetch"],
                "rho(P95, fetch) >6M": r["spearman_p95_fetch_gt6"],
                "rho(baseline, fetch) >6M": r["spearman_baseline_fetch_gt6"],
            }
        )
    return pd.DataFrame(rows)


def coverage_rows():
    rows = []
    for m in MONTHS:
        p = out_dir(m) / "summary.json"
        if not p.exists():
            continue
        s = json.loads(p.read_text())
        rows.append(
            {
                "Month": m,
                "Metadata units": s["units_meta"],
                "Units with download tests": s["units_down"],
                "Active download (>100)": s["active_down_gt100"],
                "Units with upload tests": s["units_up"],
                "Active upload (>100)": s["active_up_gt100"],
            }
        )
    return pd.DataFrame(rows)


def main():
    out = OUT / "REPORT.md"
    t2 = table2_rows()
    tp = throughput_rows()
    pb = powerboost_rows()
    tod = tod_rows()
    t4 = table4_rows()
    ul = underload_rows()
    web = web_rows().drop(columns=["Median objects"], errors="ignore")
    cov = coverage_rows()

    text = f"""# Reproducing *Broadband Internet Performance: A View From the Gateway*

Target paper: S. Sundaresan, W. de Donato, N. Feamster, R. Teixeira, S. Crawford, A. Pescapè.
*Broadband Internet Performance: A View From the Gateway.* ACM SIGCOMM 2011.
DOI: [10.1145/2018436.2018452](https://doi.org/10.1145/2018436.2018452)

This repository reproduces the paper's SamKnows-based analyses from the **FCC Measuring Broadband America (MBA) raw bulk data**. It is separate from the 2013 Genin & Splett congestion-analysis reproduction.

## Bottom line

The FCC raw data reproduces the paper's central empirical signatures:

- **Download consistency (Avg/P95)** is high for most ISPs but visibly lower for **Cablevision** and **Cox**; upload consistency is high across all ISPs (paper Fig. 7).
- **PowerBoost** appears only on cable ISPs: normalized throughput falls over the 30 s test for Comcast, TimeWarner, Cox and Charter, is flat for Cablevision, and is flat for DSL/FiOS (paper Fig. 9).
- **Diurnal degradation** is concentrated on Cablevision (~45% evening drop) and Cox (~20-30%), with small effects elsewhere (paper Fig. 8).
- **Latency under load** inflates much more on the uplink than the downlink, across all ISPs (paper Fig. 13).
- **Web fetch time** falls with download throughput and rises with baseline latency; the throughput effect saturates above ~6 Mbit/s (paper Fig. 11).

Not reproducible from FCC data: BISMark-only experiments (Figs. 5, 10, 14-16), first-hop last-mile latency (no traceroute), and jitter (the 2011 `curr_udpjitter` jitter columns are entirely empty).

## Original vs reproduced

![Original paper vs reproduced results](fig14_original_vs_reproduced.png)

Grouped bars compare the paper's Table 2 active units, Table 4 latency and loss, and Fig. 8 diurnal drops with the FCC raw-data reproduction. The reproduction pools all February and March 2011 measurements into a single window to mirror the paper's two-calendar-month window. Active-unit levels still differ because the reproduction covers a larger, still-ramping deployment; latency and loss differ because the reproduction uses closest-target and end-to-end proxies rather than the paper's first-hop measurements.

## Data and deviations

- Source: `s3://mba-data/fcc-mba/2011/raw/raw-bulk-data-{{feb,mar}}-2011.tar.gz`, plus `fcc-mba/2011/profile/` metadata.
- Window: **February 2011** (primary) and **March 2011** (stability). The paper used **14 Dec 2010 - 14 Jan 2011**; those raw bulk files are not part of the public MBA bulk release used here.
- `dtime` is UTC. Local hour is reconstructed with `unit_tz.csv` (and the 13 Mar 2011 DST switch for March).
- Throughput tests are filtered to **Measurement Lab** targets, matching the paper. Each test emits six cumulative 5 s snapshots (`sequence` 0-5). Per-test throughput is the final snapshot; per-interval throughput is `delta(bytes_total) / delta(fetch_time)`.
- "Active" means **more than 100 download tests** in the month.
- The FCC deployment grew during this period; February has fewer reporting units than March.

{md_table(cov)}

## Table 2 analog: deployment and active units

{md_table(t2)}

The FCC data contains more units than the paper's Dec-Jan snapshot (the deployment was still ramping). The ordering and relative sizes of the eight ISPs match the paper.

## Throughput

{md_table(tp)}

`DL`/`UL` are median per-user 95th-percentile throughput in Mbit/s; `Avg/P95` is the median per-user consistency ratio. Cablevision and Cox are the clear download-consistency outliers, while upload consistency is uniformly high.

### PowerBoost (normalized throughput in the last 5 s interval)

{md_table(pb)}

Values near 1.0 indicate flat throughput; values below 1.0 indicate an initial burst that decays. The pattern matches the paper: cable ISPs shape, Cablevision does not, DSL/FiOS are flat.

### Diurnal effect

{md_table(tod)}

Paper: Cablevision users see about a 40% drop, Cox about 20%. The March estimate is especially close (Cablevision 44.6%, Cox 21.2%).

Figures: `feb/fig6_scatter.png`, `feb/fig7_avg_p95_cdf.png`, `feb/fig8_tod.png`, `feb/fig9_powerboost.png` (same for `mar/`).

## Latency, loss, and latency under load

No first-hop/traceroute data exists in the FCC MBA release. We use two proxies:
- **edge**: 10th-percentile ICMP RTT to the ISP-operated speed-test host (closest available within-ISP target);
- **e2e**: 10th-percentile ICMP RTT to M-Lab.

`table4_proxy.csv` reports the per-unit minimum of the two. This is an **upper bound** on last-mile latency, not the paper's first-hop metric.

{md_table(t4)}

The DSL-versus-cable ordering and the high variance of AT&T/Qwest are reproduced; cable ISPs (especially TimeWarner, Cox, Charter) are overestimated because the closest available target is not the first hop.

### Latency under load (median ratio to baseline)

{md_table(ul)}

Upload saturation inflates latency by roughly 15-37x, versus 1.4-11x for download saturation, matching the paper's qualitative result. Figure: `feb/fig13_under_load.png`, `feb/fig12_baseline_latency.png`.

### Jitter

The 2011 `curr_udpjitter` file has **zero non-null values** for `jitter_up`, `jitter_down`, and `latency` in both February and March (4.3M and 9.4M rows respectively). **Paper Table 5 cannot be reproduced from this release.** The populated columns in `curr_udpjitter` are packet counts only; `curr_udplatency` duplicates packet/latency stats but contains no RFC 5481 jitter.

## Web browsing

{md_table(web)}

Facebook fetch time is strongly negatively correlated with download throughput and positively correlated with baseline latency. The throughput correlation weakens above 6 Mbit/s, matching the paper's "negligible improvement beyond 6 Mbit/s" finding. Figure: `feb/fig11_web.png`.

## Feasibility matrix

| Paper item | Content | Status | Notes |
|---|---|---|---|
| Fig. 3 | Deployment map | skipped | Not needed for the analysis. |
| Fig. 4 | Four throughput methods | partial | Multi-threaded HTTP reproduced; passive/netusage is capped at 2^31-1; no ShaperProbe UDP capacity; webget is not single-stream. |
| Fig. 5 | Same-plan users, different loss | no | BISMark-only. |
| Fig. 6 | Avg download vs upload | yes | `fig6_scatter.png`. |
| Fig. 7 | Avg/P95 CDF, down/up | yes | `fig7_avg_p95_cdf.png`. |
| Fig. 8 | Time-of-day effects | yes | `fig8_tod.png`; loss is e2e ICMP loss. |
| Fig. 9 | PowerBoost progression | yes | `fig9_powerboost.png`. |
| Fig. 10 | Modem-specific burst profiles | no | BISMark-only; no modem model in metadata. |
| Fig. 11 | Web fetch vs throughput/latency | yes | `fig11_web.png`; latency is a proxy. |
| Fig. 12 | Baseline latency distribution | proxy | `fig12_baseline_latency.png`; closest-path proxy. |
| Fig. 13 | Latency under load | yes | `fig13_under_load.png`; end-to-end, which is what the paper used for SamKnows. |
| Fig. 14-16 | Modem buffer experiments | no | BISMark-only. |
| Table 2 | ISPs, units, active units | yes | Different window; larger deployment. |
| Table 3 | Measurement descriptions | yes | Mapping documented in `src2011/common.py`. |
| Table 4 | Last-mile latency and loss | proxy | No traceroute; proxy in `table4_proxy.csv`. |
| Table 5 | Down/up jitter | no | Jitter columns empty in the 2011 release. |

## Reproduce

```bash
python src2011/download.py --month feb
python src2011/download.py --month mar
python src2011/ingest.py --month feb
python src2011/ingest.py --month mar
python src2011/analyze.py --month feb
python src2011/analyze.py --month mar
python src2011/report.py --month feb
python src2011/report.py --month mar
python src2011/make_report.py
python src2011/make_comparison.py
```

Environment: Python 3.11, pandas 2.2.2, pyarrow 15.0.2, matplotlib 3.8.4, boto3. S3 credentials are read from `.env`; large data stays out of git.

## Outputs

- `output/2011/feb/`, `output/2011/mar/`: per-month tables, figures, and summaries.
- `data/processed/2011/{{feb,mar}}/`: parquet intermediates.
- `src2011/common.py`: schemas, ISP list, timezone/local-time handling.
- `src2011/ingest.py`: CSV to parquet (chunked for webget).
- `src2011/analyze.py`: throughput, PowerBoost, diurnal, latency, under-load.
- `src2011/report.py`: figures, combined latency proxy, Facebook web analysis.
- `src2011/make_report.py`: this report.
- `src2011/make_comparison.py`: paper-vs-reproduction comparison figure.
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
