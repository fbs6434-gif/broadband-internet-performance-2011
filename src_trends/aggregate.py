import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

METRICS = [
    "avg_down", "median_down", "p95_down", "std_down",
    "avg_up", "median_up", "p95_up", "std_up",
    "pb_down", "pb_up", "burst_down", "burst_up",
    "diurnal_down_pct", "diurnal_up_pct",
    "baseline_p10_ms", "baseline_median_ms",
    "underload_down_ratio", "underload_up_ratio",
    "loss_idle", "loss_down", "loss_up",
    "jitter_up_us", "jitter_down_us",
    "mlab_avg_down", "mlab_p95_down", "mlab_avg_up", "mlab_p95_up",
]

TARGET_COLS = ["n_down_mlab", "n_down_level3", "n_down_samknows",
               "n_down_isp", "n_down_other"]


def load_units():
    paths = sorted(C.UNITS.glob("*.parquet"))
    frames = []
    for path in paths:
        try:
            df = pd.read_parquet(path)
        except Exception:
            continue
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        raise SystemExit("no unit-month outputs found")
    df = pd.concat(frames, ignore_index=True)
    df["year"] = df["collection_year"]
    df["month"] = df["collection_month"]
    df["year_month"] = df["year_month"].astype(str)
    return df


def _summary(g, active=20):
    a = g[g["n_down"].fillna(0) >= active]
    if a.empty:
        a = g
    out = {
        "n_units": int(g["unit_id"].nunique()),
        "n_active": int(a["unit_id"].nunique()),
        "down_tests": int(g["n_down"].fillna(0).sum()),
        "up_tests": int(g["n_up"].fillna(0).sum()),
    }
    for m in METRICS:
        if m not in a.columns:
            continue
        x = pd.to_numeric(a[m], errors="coerce")
        out[f"{m}_med"] = float(x.median()) if x.notna().any() else np.nan
        out[f"{m}_p25"] = float(x.quantile(0.25)) if x.notna().any() else np.nan
        out[f"{m}_p75"] = float(x.quantile(0.75)) if x.notna().any() else np.nan
    for c in TARGET_COLS:
        if c in g.columns:
            out[c] = int(g[c].fillna(0).sum())
    out["known_isp_frac"] = float(g["isp"].ne("unknown").mean())
    out["known_tech_frac"] = float(g["technology"].ne("unknown").mean())
    return pd.Series(out)


def national(df):
    monthly = (df.groupby(["year", "month", "year_month"], sort=True)
               .apply(_summary, include_groups=False)
               .reset_index())
    annual = (df.groupby("year", sort=True)
              .apply(_summary, include_groups=False)
              .reset_index())
    return monthly, annual


def by_dimension(df, dim, active=20, min_units=10):
    d = df[df[dim].ne("unknown") & df[dim].notna()].copy()
    rows = []
    for (year, value), g in d.groupby(["year", dim], sort=True):
        if g["unit_id"].nunique() < min_units:
            continue
        s = _summary(g, active=active)
        s["year"] = year
        s[dim] = value
        rows.append(s)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out[["year", dim] + [c for c in out.columns
                                   if c not in ("year", dim)]]
    return out


def target_mix(df):
    d = df.groupby(["year", "month"], sort=True)[TARGET_COLS].sum().reset_index()
    total = d[TARGET_COLS].sum(axis=1)
    for c in TARGET_COLS:
        d[c.replace("n_down_", "share_")] = np.where(total > 0, d[c] / total, np.nan)
    d["total_tests"] = total
    return d


def coverage(df):
    c = (df.groupby(["year", "month"], sort=True)
         .agg(units=("unit_id", "nunique"),
              known_isp=("isp", lambda s: int(s.ne("unknown").sum())),
              known_tech=("technology", lambda s: int(s.ne("unknown").sum())),
              tz_missing=("tz_missing", "sum"))
         .reset_index())
    c["known_isp_frac"] = c["known_isp"] / c["units"]
    c["known_tech_frac"] = c["known_tech"] / c["units"]
    c["tz_missing_frac"] = c["tz_missing"] / c["units"]
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(C.OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    df = load_units()
    df.to_parquet(out / "unit_month_metrics.parquet", index=False,
                  compression="zstd")
    monthly, annual = national(df)
    monthly.to_csv(out / "monthly_national.csv", index=False)
    annual.to_csv(out / "annual_national.csv", index=False)

    isp = by_dimension(df, "isp", active=20, min_units=10)
    isp.to_csv(out / "annual_isp.csv", index=False)
    tech = by_dimension(df, "technology", active=20, min_units=10)
    tech.to_csv(out / "annual_technology.csv", index=False)
    mix = target_mix(df)
    mix.to_csv(out / "target_mix.csv", index=False)
    cov = coverage(df)
    cov.to_csv(out / "coverage.csv", index=False)

    monthly_isp = []
    d = df[df["isp"].ne("unknown") & df["isp"].notna()].copy()
    for (year, month, value), g in d.groupby(["year", "month", "isp"], sort=True):
        if g["unit_id"].nunique() < 10:
            continue
        s = _summary(g)
        s["year"] = year
        s["month"] = month
        s["isp"] = value
        monthly_isp.append(s)
    pd.DataFrame(monthly_isp).to_csv(out / "monthly_isp.csv", index=False)

    print(f"units={len(df)} months={df['year_month'].nunique()} "
          f"isp_rows={len(isp)} tech_rows={len(tech)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
