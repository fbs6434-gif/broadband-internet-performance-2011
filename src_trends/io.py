import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

_MEMBER_RE = re.compile(
    r"^curr_(httpgetmt|httppostmt|ping|dlping|ulping|udpjitter)"
    r"(_\d{4}_\d{2})?\.csv$"
)


def load_env():
    candidates = [
        C.ROOT / ".env",
        C.ROOT.parent / ".env",
        Path("/home/jovyan/work/project/.env"),
        Path("/home/jovyan/work/project/.env.local"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def s3():
    load_env()
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=C.ENDPOINT,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(retries={"max_attempts": 8, "mode": "standard"},
                      max_pool_connections=32),
    )


def member_kind(name):
    m = _MEMBER_RE.match(name)
    return m.group(1) if m else None


def parse_key(key):
    name = Path(key).name
    m = re.match(r"^data-raw-(\d{4})-([a-z]+)\.tar\.gz$", name)
    if m:
        year, mon = int(m.group(1)), C.MONTH_NUM.get(m.group(2).lower())
    else:
        m = re.match(r"^raw-bulk-data-([a-z]+)-(\d{4})\.tar\.gz$", name)
        if not m:
            return None
        mon, year = C.MONTH_NUM.get(m.group(1).lower()), int(m.group(2))
    if mon is None:
        return None
    return {"year": year, "month": mon, "key": key, "name": name}


def inventory(refresh=False):
    path = C.DATA / "inventory.json"
    if path.exists() and not refresh:
        rows = json.loads(path.read_text())
        out = []
        for r in rows:
            p = parse_key(r["key"])
            if p:
                r.update(p)
                out.append(r)
        return out
    client = s3()
    rows = []
    token = None
    while True:
        kwargs = {"Bucket": C.BUCKET, "Prefix": "fcc-mba/"}
        if token:
            kwargs["ContinuationToken"] = token
        page = client.list_objects_v2(**kwargs)
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if "/raw/" not in key or not key.endswith(".tar.gz"):
                continue
            parsed = parse_key(key)
            if not parsed:
                continue
            parsed["size"] = obj["Size"]
            rows.append(parsed)
        token = page.get("NextContinuationToken")
        if not token:
            break
    rows.sort(key=lambda r: (r["year"], r["month"]))
    path.write_text(json.dumps([
        {k: r[k] for k in ("year", "month", "key", "name", "size")} for r in rows
    ], indent=2))
    return rows


def _profile_entry(year, month):
    entries = C.PROFILE_MAP.get(year, [])
    chosen = None
    for entry in entries:
        if entry[0] == month:
            return entry
        if entry[0] is None:
            chosen = entry
    return chosen


def _download(key, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    client = s3()
    tmp = dest.with_suffix(dest.suffix + f".{os.getpid()}.part")
    if tmp.exists():
        tmp.unlink()
    client.download_file(C.BUCKET, key, str(tmp))
    os.replace(tmp, dest)
    return dest


def _read_table(path, engine):
    errors = []
    engines = []
    if engine:
        engines.append(engine)
    engines += ["openpyxl", "xlrd", "odf", "calamine"]
    seen = set()
    for eng in engines:
        if not eng or eng in seen:
            continue
        seen.add(eng)
        try:
            if path.suffix.lower() in (".csv", ".txt"):
                return pd.read_csv(path)
            return pd.read_excel(path, engine=eng)
        except Exception as exc:
            errors.append(f"{eng}: {exc}")
    raise RuntimeError(f"could not read {path}: {'; '.join(errors)}")


def _parse_offset(value):
    if value is None:
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    s = str(value).strip().upper()
    if not s or s in ("NAN", "NONE"):
        return np.nan
    m = re.search(r"([+-])\s*(\d{1,2})(?::?(\d{2}))?", s)
    if m:
        hours = float(m.group(2)) + (float(m.group(3) or 0) / 60.0)
        return -hours if m.group(1) == "-" else hours
    try:
        return float(s)
    except ValueError:
        return np.nan


def _unit_ids(series):
    s = series.astype("string").str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().all():
        return num.astype("int64")
    return s


def _canon(value, table, fallback_title=True):
    if pd.isna(value):
        return "unknown"
    s = str(value).strip()
    if not s:
        return "unknown"
    key = re.sub(r"\s+", " ", s.lower())
    if key in table:
        return table[key]
    return s.title() if fallback_title else s


def _find_col(df, candidates):
    lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def load_profile(year, month):
    if year == 2011:
        meta_dest = _download("fcc-mba/2011/profile/unit_metadata.csv",
                              C.PROFILES / "2011" / "unit_metadata.csv")
        tz_dest = _download("fcc-mba/2011/profile/unit_tz.csv",
                            C.PROFILES / "2011" / "unit_tz.csv")
        meta = pd.read_csv(meta_dest)
        tz = pd.read_csv(tz_dest)
        meta = meta.rename(columns={"UnitID": "unit_id", "ISP": "isp",
                                    "TECHNOLOGY": "technology"})
        tz = tz.rename(columns={"unit_id": "unit_id", "tz": "tz", "dst": "dst"})
        keep = ["unit_id", "isp", "technology"]
        prof = meta[[c for c in keep if c in meta.columns]].copy()
        prof["unit_id"] = _unit_ids(prof["unit_id"])
        tz["unit_id"] = _unit_ids(tz["unit_id"])
        prof = prof.drop_duplicates("unit_id")
        tz = tz[["unit_id", "tz", "dst"]].drop_duplicates("unit_id")
        prof = prof.merge(tz, on="unit_id", how="outer")
    else:
        entry = _profile_entry(year, month)
        if entry is None:
            return pd.DataFrame(columns=["unit_id", "isp", "technology", "tz", "dst"])
        _, fname, key, engine, mapping = entry
        dest = _download(key, C.PROFILES / str(year) / fname)
        raw = _read_table(dest, engine)
        raw.columns = [str(c).strip() for c in raw.columns]
        prof = pd.DataFrame()
        candidates = {
            "unit_id": ["unit_id", "Unit ID", "UnitID", "UNIT_ID"],
            "isp": ["isp", "ISP"],
            "technology": ["technology", "Technology", "TECHNOLOGY"],
            "tz": ["timezone_offset", "UTC_OFFSET", "tz", "utc_offset"],
            "dst": ["timezone_offset_dst", "UTC_OFFSET_DST", "dst", "utc_offset_dst"],
        }
        for dst, cands in candidates.items():
            col = _find_col(raw, cands)
            if col is not None:
                prof[dst] = raw[col]
            elif dst in mapping:
                prof[dst] = raw[mapping[dst]]
        prof["unit_id"] = _unit_ids(prof["unit_id"])
        prof = prof.drop_duplicates("unit_id")

    for col in ("isp", "technology"):
        if col not in prof.columns:
            prof[col] = "unknown"
    for col in ("tz", "dst"):
        if col not in prof.columns:
            prof[col] = np.nan
        prof[col] = prof[col].map(_parse_offset)

    prof["isp"] = prof["isp"].map(lambda x: _canon(x, C.ISP_CANON))
    prof["technology"] = prof["technology"].map(lambda x: _canon(x, C.TECH_CANON))
    prof = prof[["unit_id", "isp", "technology", "tz", "dst"]]
    return prof


def classify_targets(targets):
    s = targets.astype("string").fillna("").str.lower()
    out = np.zeros(len(s), dtype=np.int8)
    mlab = s.str.contains(r"measurement-lab\.org|(?:^|[^a-z])mlab", regex=True, na=False)
    level3 = s.str.contains(r"level3\.net", regex=True, na=False)
    isp = s.str.contains(
        r"comcast\.net|cox\.net|rr\.com|cv\.net|verizon\.net|att\.net|"
        r"qwest\.net|charter\.com|optonline\.net|earthlink\.net|"
        r"windstream\.net|frontiernet\.net|mediacomcc\.com|centurylink\.net|"
        r"cablevision\.com|brighthouse\.com|insightbb\.com|clearwire\.net|"
        r"wildblue\.net|viasat\.com|hughes\.net|sonic\.net|googlefiber\.net|"
        r"sbcglobal\.net|pacbell\.net|ameritech\.net|bellsouth\.net",
        regex=True, na=False,
    )
    samknows = s.str.contains(r"samknows", regex=True, na=False)
    out[isp.to_numpy()] = 4
    out[samknows.to_numpy()] = 3
    out[level3.to_numpy()] = 2
    out[mlab.to_numpy()] = 1
    return out


def is_dst(ts):
    month = ts.dt.month
    day = ts.dt.day
    return ((month >= 4) & (month <= 10)) | ((month == 3) & (day >= 14)) | (
        (month == 11) & (day <= 7)
    )


def local_hour(df, profile):
    ts = pd.to_datetime(df["dtime"], errors="coerce", utc=True).dt.tz_localize(None)
    if profile is None or profile.empty:
        return ts.dt.hour.fillna(0).astype("int8").to_numpy()
    p = profile.set_index("unit_id")
    std = df["unit_id"].map(p["tz"])
    dst = df["unit_id"].map(p["dst"])
    offset = pd.to_numeric(std, errors="coerce")
    use_dst = dst.notna() & offset.notna() & (dst != std)
    if use_dst.any():
        mask = use_dst & is_dst(ts)
        offset = offset.where(~mask, pd.to_numeric(dst, errors="coerce"))
    offset = offset.fillna(0.0)
    local = ts + pd.to_timedelta(offset, unit="h")
    hour = local.dt.hour
    return hour.fillna(0).astype("int8").to_numpy()


class PrependReader(io.RawIOBase):
    def __init__(self, first, handle):
        self.first = first
        self.handle = handle

    def readable(self):
        return True

    def seekable(self):
        return False

    def writable(self):
        return False

    def read(self, size=-1):
        if self.first:
            if size is None or size < 0:
                data = self.first + self.handle.read()
                self.first = b""
                return data
            data = self.first[:size]
            self.first = self.first[size:]
            if len(data) < size:
                data += self.handle.read(size - len(data))
            return data
        return self.handle.read(size)

    def readinto(self, b):
        data = self.read(len(b))
        n = len(data)
        b[:n] = data
        return n


def download_tarball(entry, attempts=6):
    from boto3.s3.transfer import TransferConfig

    dest = C.DATA / "raw" / entry["name"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = int(entry.get("size", 0))
    if dest.exists() and (size == 0 or dest.stat().st_size == size):
        return dest
    if dest.exists():
        dest.unlink()
    free = shutil.disk_usage(C.DATA).free
    if free < 6 * 1024 ** 3:
        raise RuntimeError(f"low disk space: {free/1e9:.1f} GB free")
    client = s3()
    cfg = TransferConfig(
        multipart_threshold=64 * 1024 ** 2,
        multipart_chunksize=64 * 1024 ** 2,
        max_concurrency=8,
        use_threads=True,
    )
    tmp = dest.with_suffix(dest.suffix + ".part")
    last = None
    for attempt in range(attempts):
        try:
            if tmp.exists():
                tmp.unlink()
            client.download_file(C.BUCKET, entry["key"], str(tmp), Config=cfg)
            if size and tmp.stat().st_size != size:
                raise IOError(f"size mismatch {tmp.stat().st_size} != {size}")
            tmp.replace(dest)
            return dest
        except Exception as exc:
            last = exc
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError(f"download failed for {entry['key']}: {last}")


def schema_for(kind, ncols):
    if kind in ("httpgetmt", "httppostmt"):
        if ncols == 12:
            return C.THROUGHPUT_12
        if ncols == 14:
            return C.THROUGHPUT_14
        if ncols == 15:
            return C.THROUGHPUT_15
    if kind == "ping":
        if ncols == 9:
            return C.PING_9
        if ncols == 10:
            return C.PING_10
    if kind in ("dlping", "ulping"):
        if ncols == 9:
            return C.PING_9
        if ncols == 10:
            return C.PING_10
    if kind == "udpjitter":
        if ncols == 15:
            return C.JITTER_15
        if ncols == 16:
            return C.JITTER_16
    return None


def member_chunks(handle, kind):
    first = handle.readline()
    if not first:
        return
    text = first.decode("utf-8", "replace").strip().lstrip("\ufeff")
    header = text.startswith("#") or text.lower().startswith("unit_id")
    if header:
        cols = [c.strip().lstrip("\ufeff") for c in text.lstrip("#").split(",")]
        reader = io.BufferedReader(PrependReader(b"", handle))
    else:
        cols = None
        reader = io.BufferedReader(PrependReader(first, handle))
    if cols is None:
        ncols = len(text.split(","))
        cols = schema_for(kind, ncols)
        if cols is None:
            print(f"WARN unknown headerless {kind} with {ncols} cols", file=sys.stderr)
            return
    else:
        expected = schema_for(kind, len(cols))
        if expected is None:
            print(f"WARN unknown {kind} header {cols}", file=sys.stderr)
            return
        normalized = [c.strip().lower() for c in cols]
        cols = [expected[i] if i < len(expected) else c
                for i, c in enumerate(normalized)]
    usecols = [c for c in cols if c in {
        "unit_id", "dtime", "target", "fetch_time", "bytes_total", "bytes_sec",
        "bytes_sec_interval", "warmup_time", "warmup_bytes", "sequence",
        "threads", "successes", "failures", "rtt_avg", "rtt_min", "rtt_max",
        "rtt_std", "jitter_up", "jitter_down", "latency",
    }]
    dtype = {}
    for c in usecols:
        if c == "unit_id":
            dtype[c] = "float64"
        elif c in ("dtime", "target", "address"):
            dtype[c] = "object"
    for chunk in pd.read_csv(
        reader, names=cols, header=None, usecols=usecols, dtype=dtype,
        chunksize=C.CHUNK_ROWS, on_bad_lines="skip", low_memory=False,
    ):
        yield chunk
