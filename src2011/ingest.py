import argparse

import pandas as pd

from common import (
    NETUSAGE_COLS,
    NETUSAGE_NAMES,
    PING_COLS,
    PING_NAMES,
    PROC,
    THROUGHPUT_COLS,
    THROUGHPUT_NAMES,
    UDPJITTER_COLS,
    UDPJITTER_NAMES,
    WEBGET_COLS,
    WEBGET_NAMES,
    month_dir,
    parquet,
    proc_dir,
)

SPECS = {
    "httpgetmt": (THROUGHPUT_NAMES, THROUGHPUT_COLS),
    "httppostmt": (THROUGHPUT_NAMES, THROUGHPUT_COLS),
    "ping": (PING_NAMES, PING_COLS),
    "dlping": (PING_NAMES, PING_COLS),
    "ulping": (PING_NAMES, PING_COLS),
    "udplatency": (PING_NAMES, PING_COLS),
    "udpjitter": (UDPJITTER_NAMES, UDPJITTER_COLS),
    "webget": (WEBGET_NAMES, WEBGET_COLS),
    "netusage": (NETUSAGE_NAMES, NETUSAGE_COLS),
}

NUMERIC = {
    "fetch_time",
    "bytes_total",
    "bytes_sec",
    "warmup_time",
    "warmup_bytes",
    "sequence",
    "threads",
    "successes",
    "failures",
    "rtt_avg",
    "rtt_min",
    "rtt_max",
    "rtt_std",
    "packet_size",
    "stream_rate",
    "duration",
    "packets_up_sent",
    "packets_down_sent",
    "packets_up_recv",
    "packets_down_recv",
    "jitter_up",
    "jitter_down",
    "latency",
    "objects",
    "wan_rx_bytes",
    "wan_tx_bytes",
    "sk_rx_bytes",
    "sk_tx_bytes",
}



def ingest_webget_chunked(month: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    src = month_dir(month) / "curr_webget.csv"
    if not src.exists():
        print(f"skip missing {src}")
        return
    out = parquet(month, "webget")
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["unit_id", "target", "fetch_time", "bytes_total", "bytes_sec", "objects", "successes", "failures"]
    dtypes = {
        "unit_id": "Int64",
        "target": "string",
        "fetch_time": "float64",
        "bytes_total": "float64",
        "bytes_sec": "float64",
        "objects": "float64",
        "successes": "float64",
        "failures": "float64",
    }
    writer = None
    n = 0
    for chunk in pd.read_csv(
        src, comment="#", names=WEBGET_NAMES, usecols=cols, dtype=dtypes, chunksize=1_000_000
    ):
        chunk["unit_id"] = pd.to_numeric(chunk["unit_id"], errors="coerce").astype("Int64")
        t = chunk["target"].astype("string")
        chunk = chunk.assign(target=t)
        table = pa.Table.from_pandas(chunk, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(out, table.schema)
        writer.write_table(table)
        n += len(chunk)
    if writer is not None:
        writer.close()
    print(f"{month} webget: {n:,} rows -> {out}")


def ingest_kind(month: str, kind: str) -> None:
    if kind == "webget":
        ingest_webget_chunked(month)
        return
    names, cols = SPECS[kind]
    src = month_dir(month) / f"curr_{kind}.csv"
    if not src.exists():
        print(f"skip missing {src}")
        return
    df = pd.read_csv(src, comment="#", names=names, usecols=cols)
    df["dtime"] = pd.to_datetime(df["dtime"], errors="coerce")
    df["unit_id"] = pd.to_numeric(df["unit_id"], errors="coerce")
    df = df[df["dtime"].notna() & df["unit_id"].notna()].copy()
    df["unit_id"] = df["unit_id"].astype("int32")
    if "target" in df.columns:
        df["target"] = df["target"].astype("string")
    for c in df.columns:
        if c in NUMERIC:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("sequence", "threads", "successes", "failures"):
        if c in df.columns:
            df[c] = df[c].astype("Int32")
    out = parquet(month, kind)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"{month} {kind}: {len(df):,} rows -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="feb")
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    PROC.mkdir(parents=True, exist_ok=True)
    proc_dir(args.month).mkdir(parents=True, exist_ok=True)
    kinds = args.only or list(SPECS)
    for kind in kinds:
        ingest_kind(args.month, kind)


if __name__ == "__main__":
    main()
