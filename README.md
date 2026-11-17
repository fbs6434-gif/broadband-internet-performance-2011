# Broadband Internet Performance: A View From the Gateway (2011) — Reproduction

Reproduction of S. Sundaresan, W. de Donato, N. Feamster, R. Teixeira,
S. Crawford, A. Pescapè, *Broadband Internet Performance: A View From the
Gateway*, ACM SIGCOMM 2011
([DOI 10.1145/2018436.2018452](https://doi.org/10.1145/2018436.2018452)),
using FCC Measuring Broadband America raw data for **February and March 2011**.

This repository is separate from the 2013 Genin & Splett congestion-analysis
reproduction (`where-congestion-occurs-2013`).

**Full write-up, tables, and figures:** [reports/2011/REPORT.md](reports/2011/REPORT.md)

**Paper-matched comparison (31-day Feb–Mar 2011 window):** [reports/2011/fig14_paper_matched.png](reports/2011/fig14_paper_matched.png)

**Earlier pooled comparison:** [reports/2011/fig14_original_vs_reproduced.png](reports/2011/fig14_original_vs_reproduced.png)

## Main findings

- Download consistency (Avg/P95) is high for most ISPs but clearly lower for
  **Cablevision** and **Cox**; upload consistency is uniformly high.
- **PowerBoost** is visible only on cable ISPs (Comcast, TimeWarner, Cox,
  Charter), is flat for Cablevision, and is flat for DSL/FiOS.
- Evening throughput drops are concentrated on **Cablevision (~44%)** and
  **Cox (~24%)** in the pooled Feb–Mar window (separate two-ISP analysis;
  omitted from the headline comparison).
- **Latency under load** inflates 15–37× on the uplink versus 1.4–11× on the
  downlink.
- Web fetch time falls with throughput (saturating above ~6 Mbit/s) and rises
  with baseline latency.

Not reproducible from the FCC release: BISMark-only experiments (Figs. 5, 10,
14–16), first-hop last-mile latency (no traceroute), and Table 5 jitter (the
2011 `curr_udpjitter` jitter columns are entirely empty).

## Paper-matching choices

The primary comparison is `reports/2011/fig14_paper_matched.png`; its numbers are
in `reports/2011/paper_matched_metrics.csv`. To make it more faithful to the paper:

- **31-day window:** 1 Feb–3 Mar 2011 matches the length of the paper's
  14 Dec 2010–14 Jan 2011 window; the paper's exact months are not in the
  public FCC bulk release.
- **Active units:** more than 100 M-Lab download tests in the window, matching
  the paper's Table 2 rule.
- **Metric filters:** each reported metric uses only units with more than 100
  measurements, matching the paper's per-metric sample rule.
- **Loss target:** end-to-end UDP to M-Lab, not edge or first-hop loss. This is
  the paper's SamKnows loss metric (Table 3), even though Table 4's title says
  "last-mile latency and loss."
- **Latency target:** mean ICMP RTT to the closest available ISP target with
  more than 100 pings. The paper used first-hop traceroute, which is absent
  from the FCC release; this is therefore an upper bound, not a direct match.
- **Scope:** only the eight ISPs with the most gateways; evening drop is omitted
  from the headline comparison because it covers only Cablevision and Cox.

## Pipeline

```bash
python src2011/download.py --month feb
python src2011/download.py --month mar
python src2011/ingest.py  --month feb
python src2011/ingest.py  --month mar
python src2011/analyze.py --month feb
python src2011/analyze.py --month mar
python src2011/report.py  --month feb
python src2011/report.py  --month mar
python src2011/make_report.py
python src2011/publish.py
python src2011/paper_match.py
```

S3 credentials are read from `.env`. Large raw/processed data and scratch
outputs are gitignored; published figures and summary tables are under
`reports/2011/`.

See [src2011/README.md](src2011/README.md) for schema and timezone notes.

## Multi-year extension (2011–2023)

The `src_trends/` pipeline extends the gateway analysis to all 141 available
FCC MBA raw months (2011–2023). It streams the tarballs from S3, computes
per-unit monthly metrics, and writes the aggregate tables and report.

**Trend report (2011–2023):** [reports/trends/REPORT.md](reports/trends/REPORT.md)

```bash
export TRENDS_CHUNK_ROWS=1000000
python -m src_trends.run_all --workers 3
python -m src_trends.aggregate
python -m src_trends.report
```

Outputs are written to `output/trends/` and `reports/trends/`; both are
gitignored except for the published report and figures under
`reports/trends/`. S3 credentials are read from `.env` (or the environment).
