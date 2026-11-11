# 2011 Gateway Reproduction

Code for reproducing Sundaresan et al., *Broadband Internet Performance: A View
From the Gateway* (SIGCOMM 2011), from FCC Measuring Broadband America raw data.

The consolidated write-up is `reports/2011/REPORT.md` (or `output/2011/REPORT.md`).

## Pipeline

```bash
python src2011/download.py --month feb   # S3 raw tarball -> data/raw/2011/feb
python src2011/download.py --month mar
python src2011/ingest.py  --month feb    # CSV -> data/processed/2011/feb/*.parquet
python src2011/ingest.py  --month mar
python src2011/analyze.py --month feb    # unit/ISP tables, PowerBoost, diurnal, latency
python src2011/analyze.py --month mar
python src2011/report.py  --month feb    # figures, web analysis
python src2011/report.py  --month mar
python src2011/make_report.py            # output/2011/REPORT.md
python src2011/publish.py                # copy report/figures/tables to reports/2011
```

`download.py` reads S3 credentials from the repository `.env`.
Large data (`data/`) and scratch outputs (`output/`) are gitignored; published
figures and summary tables live under `reports/2011/`.

## Notes

- `dtime` in the FCC files is UTC; local time uses `unit_tz.csv` (plus the
  2011-03-13 DST switch for March).
- Throughput tests are restricted to Measurement Lab targets. A test has six
  cumulative 5 s snapshots (`sequence` 0-5); the final snapshot is the test
  throughput, and interval throughput is `delta(bytes_total)/delta(fetch_time)`.
- The 2011 `curr_udpjitter` jitter columns are empty in both February and
  March, so Table 5 is not reproducible from this release.
- Last-mile latency is unavailable (no traceroute); the report uses ISP-hosted
  and M-Lab ICMP baselines as proxies.
