# Reproducing *Broadband Internet Performance: A View From the Gateway*

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

## Data and deviations

- Source: `s3://mba-data/fcc-mba/2011/raw/raw-bulk-data-{feb,mar}-2011.tar.gz`, plus `fcc-mba/2011/profile/` metadata.
- Window: **February 2011** (primary) and **March 2011** (stability). The paper used **14 Dec 2010 - 14 Jan 2011**; those raw bulk files are not part of the public MBA bulk release used here.
- `dtime` is UTC. Local hour is reconstructed with `unit_tz.csv` (and the 13 Mar 2011 DST switch for March).
- Throughput tests are filtered to **Measurement Lab** targets, matching the paper. Each test emits six cumulative 5 s snapshots (`sequence` 0-5). Per-test throughput is the final snapshot; per-interval throughput is `delta(bytes_total) / delta(fetch_time)`.
- "Active" means **more than 100 download tests** in the month.
- The FCC deployment grew during this period; February has fewer reporting units than March.

| Month | Metadata units | Units with download tests | Active download (>100) | Units with upload tests | Active upload (>100) |
|---|---|---|---|---|---|
| feb | 7377 | 5477 | 3715 | 5481 | 3708 |
| mar | 7377 | 7250 | 6301 | 7253 | 6301 |

## Table 2 analog: deployment and active units

| ISP | Paper total | Paper active | feb total | feb active | mar total | mar active |
|---|---|---|---|---|---|---|
| Comcast | 864 | 560 | 1135 | 842 | 1135 | 1047 |
| AT&T | 787 | 335 | 1156 | 681 | 1156 | 999 |
| TimeWarner | 690 | 381 | 1270 | 578 | 1270 | 1108 |
| Verizon | 551 | 256 | 943 | 415 | 943 | 749 |
| Cox | 381 | 161 | 614 | 354 | 614 | 519 |
| Qwest | 265 | 117 | 359 | 228 | 359 | 310 |
| Charter | 187 | 51 | 641 | 199 | 641 | 599 |
| Cablevision | 104 | 53 | 169 | 80 | 169 | 148 |

The FCC data contains more units than the paper's Dec-Jan snapshot (the deployment was still ramping). The ordering and relative sizes of the eight ISPs match the paper.

## Throughput

| ISP | feb DL p95 | feb DL Avg/P95 | feb UL p95 | feb UL Avg/P95 | mar DL p95 | mar DL Avg/P95 | mar UL p95 | mar UL Avg/P95 |
|---|---|---|---|---|---|---|---|---|
| Comcast | 15.08 | 0.97 | 3.18 | 0.97 | 15.08 | 0.97 | 3.09 | 0.97 |
| AT&T | 5.14 | 0.98 | 0.67 | 0.98 | 5.13 | 0.98 | 0.66 | 0.98 |
| TimeWarner | 12.10 | 0.96 | 0.99 | 0.98 | 12.11 | 0.96 | 0.97 | 0.98 |
| Verizon | 25.61 | 0.99 | 5.75 | 1.00 | 20.48 | 0.99 | 4.72 | 0.99 |
| Cox | 18.13 | 0.86 | 2.43 | 0.96 | 19.50 | 0.91 | 2.50 | 0.96 |
| Qwest | 5.91 | 0.98 | 0.78 | 0.98 | 5.88 | 0.98 | 0.78 | 0.97 |
| Charter | 18.77 | 0.94 | 2.15 | 0.99 | 14.57 | 0.96 | 1.11 | 0.99 |
| Cablevision | 15.77 | 0.71 | 2.14 | 0.99 | 15.76 | 0.72 | 2.14 | 0.99 |

`DL`/`UL` are median per-user 95th-percentile throughput in Mbit/s; `Avg/P95` is the median per-user consistency ratio. Cablevision and Cox are the clear download-consistency outliers, while upload consistency is uniformly high.

### PowerBoost (normalized throughput in the last 5 s interval)

| ISP | feb last/first | mar last/first |
|---|---|---|
| Comcast | 0.86 | 0.84 |
| AT&T | 1.00 | 1.00 |
| TimeWarner | 0.94 | 0.94 |
| Verizon | 1.00 | 1.01 |
| Cox | 0.94 | 0.93 |
| Qwest | 1.01 | 1.01 |
| Charter | 0.98 | 0.98 |
| Cablevision | 1.02 | 1.02 |

Values near 1.0 indicate flat throughput; values below 1.0 indicate an initial burst that decays. The pattern matches the paper: cable ISPs shape, Cablevision does not, DSL/FiOS are flat.

### Diurnal effect

| ISP | feb drop 20 vs 3 (%) | mar drop 20 vs 3 (%) |
|---|---|---|
| Comcast | 6.68 | 5.49 |
| AT&T | 7.29 | 6.71 |
| TimeWarner | 7.61 | 7.24 |
| Verizon | 3.05 | 2.33 |
| Cox | 30.53 | 21.17 |
| Qwest | 9.77 | 10.14 |
| Charter | 12.89 | 10.19 |
| Cablevision | 44.07 | 44.61 |

Paper: Cablevision users see about a 40% drop, Cox about 20%. The March estimate is especially close (Cablevision 44.6%, Cox 21.2%).

Figures: `feb/fig6_scatter.png`, `feb/fig7_avg_p95_cdf.png`, `feb/fig8_tod.png`, `feb/fig9_powerboost.png` (same for `mar/`).

## Latency, loss, and latency under load

No first-hop/traceroute data exists in the FCC MBA release. We use two proxies:
- **edge**: 10th-percentile ICMP RTT to the ISP-operated speed-test host (closest available within-ISP target);
- **e2e**: 10th-percentile ICMP RTT to M-Lab.

`table4_proxy.csv` reports the per-unit minimum of the two. This is an **upper bound** on last-mile latency, not the paper's first-hop metric.

| ISP | Paper latency | Paper loss % | feb latency | feb loss % | mar latency | mar loss % |
|---|---|---|---|---|---|---|
| Comcast | 10.36 | 0.27 | 14.58 | 0.81 | 13.34 | 1.93 |
| AT&T | 25.23 | 0.48 | 26.63 | 1.15 | 26.00 | 1.81 |
| TimeWarner | 11.87 | 0.33 | 21.54 | 0.70 | 21.01 | 1.71 |
| Verizon | 12.41 | 0.51 | 19.61 | 0.84 | 20.08 | 1.39 |
| Cox | 13.88 | 1.11 | 20.11 | 0.76 | 20.40 | 1.60 |
| Qwest | 39.42 | 0.33 | 41.45 | 0.60 | 42.54 | 2.43 |
| Charter | 11.87 | 0.43 | 26.27 | 0.65 | 25.27 | 1.51 |
| Cablevision | 10.21 | 0.33 | 10.10 | 0.56 | 10.34 | 0.82 |

The DSL-versus-cable ordering and the high variance of AT&T/Qwest are reproduced; cable ISPs (especially TimeWarner, Cox, Charter) are overestimated because the closest available target is not the first hop.

### Latency under load (median ratio to baseline)

| ISP | feb down median | feb up median | mar down median | mar up median |
|---|---|---|---|---|
| Comcast | 4.65 | 21.92 | 5.07 | 22.76 |
| AT&T | 3.64 | 21.85 | 4.06 | 22.59 |
| TimeWarner | 4.80 | 37.40 | 3.58 | 36.19 |
| Verizon | 10.67 | 20.88 | 8.89 | 18.10 |
| Cox | 1.92 | 28.59 | 1.84 | 25.00 |
| Qwest | 4.45 | 15.10 | 3.93 | 13.87 |
| Charter | 1.41 | 20.14 | 1.40 | 20.92 |
| Cablevision | 4.86 | 31.01 | 4.50 | 29.70 |

Upload saturation inflates latency by roughly 15-37x, versus 1.4-11x for download saturation, matching the paper's qualitative result. Figure: `feb/fig13_under_load.png`, `feb/fig12_baseline_latency.png`.

### Jitter

The 2011 `curr_udpjitter` file has **zero non-null values** for `jitter_up`, `jitter_down`, and `latency` in both February and March (4.3M and 9.4M rows respectively). **Paper Table 5 cannot be reproduced from this release.** The populated columns in `curr_udpjitter` are packet counts only; `curr_udplatency` duplicates packet/latency stats but contains no RFC 5481 jitter.

## Web browsing

| Month | Units | Median fetch (ms) | Median bytes | rho(P95, fetch) | rho(baseline, fetch) | rho(P95, fetch) >6M | rho(baseline, fetch) >6M |
|---|---|---|---|---|---|---|---|
| feb | 5499 | 748.45 | 196228.00 | -0.67 | 0.45 | -0.30 | 0.32 |
| mar | 7269 | 705.88 | 156515.00 | -0.66 | 0.43 | -0.28 | 0.24 |

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
```

Environment: Python 3.11, pandas 2.2.2, pyarrow 15.0.2, matplotlib 3.8.4, boto3. S3 credentials are read from `.env`; large data stays out of git.

## Outputs

- `output/2011/feb/`, `output/2011/mar/`: per-month tables, figures, and summaries.
- `data/processed/2011/{feb,mar}/`: parquet intermediates.
- `src2011/common.py`: schemas, ISP list, timezone/local-time handling.
- `src2011/ingest.py`: CSV to parquet (chunked for webget).
- `src2011/analyze.py`: throughput, PowerBoost, diurnal, latency, under-load.
- `src2011/report.py`: figures, combined latency proxy, Facebook web analysis.
- `src2011/make_report.py`: this report.
