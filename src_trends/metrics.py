from array import array
from collections import defaultdict

import numpy as np
import pandas as pd

from .io import classify_targets, local_hour

FLOAT_KEYS = [
    "down", "up", "down_pb", "up_pb", "down_burst", "up_burst",
    "down_mlab", "up_mlab", "down_pb_mlab", "up_pb_mlab",
    "down_burst_mlab", "up_burst_mlab",
    "idle", "dl", "ul", "idle_mlab", "dl_mlab", "ul_mlab",
    "idle_loss", "dl_loss", "ul_loss",
    "jitter_up", "jitter_down",
]
INT_KEYS = ["down_hour", "up_hour", "down_class", "up_class", "idle_class"]


def new_acc():
    return defaultdict(lambda: {k: array("f") for k in FLOAT_KEYS} | {
        k: array("b") for k in INT_KEYS
    })


def _num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _valid(vals):
    return np.isfinite(vals) & (vals > 0.01) & (vals < 100000.0)


def _clean_units(df):
    s = pd.to_numeric(df["unit_id"], errors="coerce")
    df = df[s.notna()].copy()
    df["unit_id"] = s[s.notna()].astype("int64")
    return df


def _target_codes(s):
    uniq = pd.Index(pd.unique(s))
    codes = classify_targets(uniq)
    mapping = dict(zip(uniq, codes))
    return s.map(mapping).to_numpy(dtype=np.int8)


def _append_test_rows(acc, tests, direction):
    if tests.empty:
        return
    tests = tests[np.isfinite(tests["final_mbps"]) & _valid(tests["final_mbps"])]
    if tests.empty:
        return
    codes, uniques = pd.factorize(tests["unit_id"], sort=False)
    tests = tests.assign(_u=codes)
    for code, sub in tests.groupby("_u", sort=False):
        unit = uniques[code]
        a = acc[unit]
        vals = sub["final_mbps"].to_numpy(dtype=np.float32)
        hours = sub["local_hour"].to_numpy(dtype=np.int8)
        cls = sub["target_class"].to_numpy(dtype=np.int8)
        a[f"{direction}"].extend(vals)
        a[f"{direction}_hour"].extend(hours)
        a[f"{direction}_class"].extend(cls)
        mlab = cls == 1
        if mlab.any():
            a[f"{direction}_mlab"].extend(vals[mlab])
        pb = sub["pb_ratio"].to_numpy(dtype=np.float32)
        ok = np.isfinite(pb) & (pb > 0.01) & (pb < 100.0)
        if ok.any():
            a[f"{direction}_pb"].extend(pb[ok])
            m = ok & mlab
            if m.any():
                a[f"{direction}_pb_mlab"].extend(pb[m])
        burst = sub["burst_ratio"].to_numpy(dtype=np.float32)
        ok = np.isfinite(burst) & (burst > 0.01) & (burst < 100.0)
        if ok.any():
            a[f"{direction}_burst"].extend(burst[ok])
            m = ok & mlab
            if m.any():
                a[f"{direction}_burst_mlab"].extend(burst[m])


def add_throughput(acc, chunk, year, profile):
    chunk = _num(chunk, ["fetch_time", "bytes_total", "bytes_sec",
                         "bytes_sec_interval", "warmup_time", "warmup_bytes",
                         "sequence", "threads", "successes", "failures"])
    chunk = chunk[
        (chunk["successes"].fillna(0) > 0)
        & (chunk["failures"].fillna(0) == 0)
        & (chunk["bytes_sec"].fillna(0) > 0)
        & (chunk["fetch_time"].fillna(0) > 0)
    ].copy()
    if chunk.empty:
        return
    chunk = _clean_units(chunk)
    chunk["local_hour"] = local_hour(chunk, profile)
    chunk["target_class"] = _target_codes(chunk["target"])
    chunk["final_mbps"] = chunk["bytes_sec"] * 8.0 / 1e6
    chunk["warmup_mbps"] = np.where(
        chunk["warmup_time"].fillna(0) > 0,
        chunk["warmup_bytes"] * 8.0 / chunk["warmup_time"],
        np.nan,
    )
    chunk["burst_ratio"] = chunk["final_mbps"] / chunk["warmup_mbps"]

    snapshot = year <= 2015 and (chunk["sequence"].fillna(0) > 0).any()
    if snapshot:
        prev = chunk[["unit_id", "dtime", "target"]].shift()
        change = (chunk["unit_id"].ne(prev["unit_id"])
                  | chunk["dtime"].ne(prev["dtime"])
                  | chunk["target"].ne(prev["target"]))
        chunk["test_id"] = change.cumsum()
        g = chunk.groupby("test_id", sort=False)
        chunk["seq_min"] = g["sequence"].transform("min")
        chunk["seq_max"] = g["sequence"].transform("max")
        if "bytes_sec_interval" in chunk.columns:
            interval = chunk["bytes_sec_interval"] * 8.0 / 1e6
        else:
            interval = pd.Series(np.nan, index=chunk.index)
        if interval.notna().sum() > 0:
            chunk["int_mbps"] = interval
        else:
            db = g["bytes_total"].diff()
            dt = g["fetch_time"].diff()
            chunk["int_mbps"] = db * 8.0 / dt
        first = chunk[
            chunk["sequence"].eq(1) & chunk["seq_min"].eq(0)
        ][["test_id", "int_mbps"]].rename(columns={"int_mbps": "first_int"})
        last = chunk[
            chunk["sequence"].eq(chunk["seq_max"]) & chunk["seq_max"].ge(5)
        ][["test_id", "unit_id", "dtime", "target", "final_mbps", "int_mbps",
           "burst_ratio", "local_hour", "target_class"]].rename(
            columns={"int_mbps": "last_int"})
        if first.empty or last.empty:
            return
        tests = last.merge(first, on="test_id", how="inner")
        tests["pb_ratio"] = tests["last_int"] / tests["first_int"]
        tests = tests[
            _valid(tests["first_int"].to_numpy(dtype=float))
            & _valid(tests["last_int"].to_numpy(dtype=float))
        ]
    else:
        tests = chunk[["unit_id", "final_mbps", "burst_ratio",
                       "local_hour", "target_class"]].copy()
        tests["pb_ratio"] = np.nan

    return tests


def add_throughput_direction(acc, tests, direction):
    _append_test_rows(acc, tests, direction)


def add_ping(acc, chunk, kind):
    chunk = _num(chunk, ["rtt_avg", "rtt_min", "successes", "failures"])
    if "rtt_min" not in chunk.columns:
        chunk["rtt_min"] = np.nan
    chunk["rtt_ms"] = chunk["rtt_avg"] / 1000.0
    fallback = chunk["rtt_ms"].isna() | (chunk["rtt_ms"] <= 0)
    chunk.loc[fallback, "rtt_ms"] = chunk.loc[fallback, "rtt_min"] / 1000.0
    total = chunk["successes"].fillna(0) + chunk["failures"].fillna(0)
    chunk = chunk[
        (total > 0)
        & chunk["rtt_ms"].notna()
        & (chunk["rtt_ms"] > 0.1)
        & (chunk["rtt_ms"] < 10000.0)
    ].copy()
    if chunk.empty:
        return
    chunk = _clean_units(chunk)
    chunk["loss"] = chunk["failures"].fillna(0) / total.loc[chunk.index]
    chunk["target_class"] = _target_codes(chunk["target"])
    codes, uniques = pd.factorize(chunk["unit_id"], sort=False)
    chunk["_u"] = codes
    for code, sub in chunk.groupby("_u", sort=False):
        unit = uniques[code]
        a = acc[unit]
        rtt = sub["rtt_ms"].to_numpy(dtype=np.float32)
        loss = sub["loss"].to_numpy(dtype=np.float32)
        cls = sub["target_class"].to_numpy(dtype=np.int8)
        if kind == "ping":
            a["idle"].extend(rtt)
            a["idle_loss"].extend(loss)
            a["idle_class"].extend(cls)
            mlab = cls == 1
            if mlab.any():
                a["idle_mlab"].extend(rtt[mlab])
        elif kind == "dlping":
            a["dl"].extend(rtt)
            a["dl_loss"].extend(loss)
            mlab = cls == 1
            if mlab.any():
                a["dl_mlab"].extend(rtt[mlab])
        elif kind == "ulping":
            a["ul"].extend(rtt)
            a["ul_loss"].extend(loss)
            mlab = cls == 1
            if mlab.any():
                a["ul_mlab"].extend(rtt[mlab])


def add_jitter(acc, chunk):
    chunk = _num(chunk, ["jitter_up", "jitter_down"])
    if "jitter_up" not in chunk.columns or "jitter_down" not in chunk.columns:
        return
    chunk = chunk[
        np.isfinite(chunk["jitter_up"])
        & np.isfinite(chunk["jitter_down"])
        & (chunk["jitter_up"] > 0)
        & (chunk["jitter_down"] > 0)
    ].copy()
    if chunk.empty:
        return
    chunk = _clean_units(chunk)
    codes, uniques = pd.factorize(chunk["unit_id"], sort=False)
    chunk["_u"] = codes
    for code, sub in chunk.groupby("_u", sort=False):
        unit = uniques[code]
        a = acc[unit]
        a["jitter_up"].extend(sub["jitter_up"].to_numpy(dtype=np.float32))
        a["jitter_down"].extend(sub["jitter_down"].to_numpy(dtype=np.float32))


def _vals(a, key):
    arr = a.get(key)
    if arr is None or len(arr) == 0:
        return np.array([], dtype=np.float32)
    return np.frombuffer(arr, dtype=np.float32)


def _ints(a, key):
    arr = a.get(key)
    if arr is None or len(arr) == 0:
        return np.array([], dtype=np.int8)
    return np.frombuffer(arr, dtype=np.int8)


def _med(x):
    return float(np.median(x)) if x.size else np.nan


def _q(x, q):
    return float(np.quantile(x, q)) if x.size else np.nan


def _mean(x):
    return float(np.mean(x)) if x.size else np.nan


def _std(x):
    return float(np.std(x, ddof=1)) if x.size > 1 else np.nan


def _diurnal(vals, hours):
    if vals.size == 0 or hours.size != vals.size:
        return np.nan, np.nan, np.nan
    eve = vals[(hours >= 20) & (hours <= 22)]
    night = vals[(hours >= 3) & (hours <= 5)]
    if eve.size == 0 or night.size == 0:
        return np.nan, np.nan, np.nan
    e, n = _med(eve), _med(night)
    pct = 1.0 - (e / n) if n and n > 0 else np.nan
    return pct, e, n


def _ratio(num, den):
    if num is None or den is None:
        return np.nan
    if not np.isfinite(num) or not np.isfinite(den) or den <= 0:
        return np.nan
    r = num / den
    return r if 0 <= r <= 1000 else np.nan


def finalize(acc, year, month, profile):
    prof = profile.set_index("unit_id") if profile is not None and not profile.empty else None
    rows = []
    for unit, a in acc.items():
        down = _vals(a, "down")
        up = _vals(a, "up")
        dh = _ints(a, "down_hour")
        uh = _ints(a, "up_hour")
        dc = _ints(a, "down_class")
        d_pct, d_eve, d_night = _diurnal(down, dh)
        u_pct, u_eve, u_night = _diurnal(up, uh)
        idle = _vals(a, "idle")
        dl = _vals(a, "dl")
        ul = _vals(a, "ul")
        base_p10 = _q(idle, 0.10)
        base_med = _med(idle)
        rec = {
            "unit_id": unit,
            "collection_year": int(year),
            "collection_month": int(month),
            "year_month": f"{year}-{month:02d}",
            "n_down": int(down.size),
            "avg_down": _mean(down),
            "median_down": _med(down),
            "p95_down": _q(down, 0.95),
            "std_down": _std(down),
            "n_up": int(up.size),
            "avg_up": _mean(up),
            "median_up": _med(up),
            "p95_up": _q(up, 0.95),
            "std_up": _std(up),
            "pb_down": _med(_vals(a, "down_pb")),
            "pb_up": _med(_vals(a, "up_pb")),
            "n_pb_down": int(_vals(a, "down_pb").size),
            "n_pb_up": int(_vals(a, "up_pb").size),
            "burst_down": _med(_vals(a, "down_burst")),
            "burst_up": _med(_vals(a, "up_burst")),
            "n_burst_down": int(_vals(a, "down_burst").size),
            "n_burst_up": int(_vals(a, "up_burst").size),
            "diurnal_down_pct": d_pct,
            "diurnal_up_pct": u_pct,
            "evening_down": d_eve,
            "night_down": d_night,
            "evening_up": u_eve,
            "night_up": u_night,
            "baseline_p10_ms": base_p10,
            "baseline_median_ms": base_med,
            "n_idle": int(idle.size),
            "loss_idle": _mean(_vals(a, "idle_loss")),
            "dl_median_ms": _med(dl),
            "ul_median_ms": _med(ul),
            "underload_down_ratio": _ratio(_med(dl), base_med),
            "underload_up_ratio": _ratio(_med(ul), base_med),
            "loss_down": _mean(_vals(a, "dl_loss")),
            "loss_up": _mean(_vals(a, "ul_loss")),
            "jitter_up_us": _med(_vals(a, "jitter_up")),
            "jitter_down_us": _med(_vals(a, "jitter_down")),
            "n_jitter": int(_vals(a, "jitter_up").size),
            "mlab_n_down": int(_vals(a, "down_mlab").size),
            "mlab_avg_down": _mean(_vals(a, "down_mlab")),
            "mlab_p95_down": _q(_vals(a, "down_mlab"), 0.95),
            "mlab_pb_down": _med(_vals(a, "down_pb_mlab")),
            "mlab_burst_down": _med(_vals(a, "down_burst_mlab")),
            "mlab_n_up": int(_vals(a, "up_mlab").size),
            "mlab_avg_up": _mean(_vals(a, "up_mlab")),
            "mlab_p95_up": _q(_vals(a, "up_mlab"), 0.95),
            "mlab_pb_up": _med(_vals(a, "up_pb_mlab")),
            "mlab_burst_up": _med(_vals(a, "up_burst_mlab")),
            "mlab_n_idle": int(_vals(a, "idle_mlab").size),
            "mlab_baseline_p10_ms": _q(_vals(a, "idle_mlab"), 0.10),
            "mlab_underload_down_ratio": _ratio(_med(_vals(a, "dl_mlab")),
                                                _med(_vals(a, "idle_mlab"))),
            "mlab_underload_up_ratio": _ratio(_med(_vals(a, "ul_mlab")),
                                              _med(_vals(a, "idle_mlab"))),
        }
        for code, name in ((0, "other"), (1, "mlab"), (2, "level3"),
                           (3, "samknows"), (4, "isp")):
            rec[f"n_down_{name}"] = int(np.count_nonzero(dc == code))
        isp = tech = None
        tz = dst = np.nan
        if prof is not None and unit in prof.index:
            row = prof.loc[unit]
            isp, tech = row.get("isp"), row.get("technology")
            tz, dst = row.get("tz"), row.get("dst")
        rec["isp"] = isp if isinstance(isp, str) and isp else "unknown"
        rec["technology"] = tech if isinstance(tech, str) and tech else "unknown"
        rec["tz"] = tz
        rec["dst"] = dst
        rec["tz_missing"] = bool(pd.isna(tz))
        rows.append(rec)
    return pd.DataFrame(rows)
