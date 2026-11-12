import argparse
import json
import sys
import tarfile
import time
import traceback
from pathlib import Path

import pandas as pd

from . import config as C
from .io import (download_tarball, inventory, load_profile, member_chunks,
                 member_kind, s3)
from .metrics import (add_jitter, add_ping, add_throughput,
                      add_throughput_direction, finalize, new_acc)


def _entry(year, month, key=None):
    rows = inventory()
    if key:
        for r in rows:
            if r["key"] == key:
                return r
    for r in rows:
        if r["year"] == year and r["month"] == month:
            return r
    raise KeyError(f"no tarball for {year}-{month:02d}")


def process(year, month, key=None, force=False, local=None, keep_raw=False,
            download_sem=None):
    entry = _entry(year, month, key)
    key = entry["key"]
    out = C.UNITS / f"{year}-{month:02d}.parquet"
    summary_path = C.SUMMARIES / f"{year}-{month:02d}.json"
    if out.exists() and summary_path.exists() and not force:
        return json.loads(summary_path.read_text())

    started = time.time()
    profile = load_profile(year, month)
    acc = new_acc()
    stats = {"rows": 0, "chunks": 0, "members": {}}
    error = None
    if local:
        tar_path = Path(local)
    elif download_sem is None:
        tar_path = download_tarball(entry)
    else:
        with download_sem:
            tar_path = download_tarball(entry)
    delete_tar = (not local) and (not keep_raw)
    try:
        with tarfile.open(tar_path, mode="r|gz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                base = Path(member.name).name
                kind = member_kind(base)
                if kind is None:
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                stats["members"][kind] = stats["members"].get(kind, 0) + 1
                for chunk in member_chunks(handle, kind):
                    stats["rows"] += len(chunk)
                    stats["chunks"] += 1
                    if kind in ("httpgetmt", "httppostmt"):
                        tests = add_throughput(acc, chunk, year, profile)
                        if tests is not None and not tests.empty:
                            direction = "down" if kind == "httpgetmt" else "up"
                            add_throughput_direction(acc, tests, direction)
                    elif kind in ("ping", "dlping", "ulping"):
                        add_ping(acc, chunk, kind)
                    elif kind == "udpjitter":
                        add_jitter(acc, chunk)
                    if stats["chunks"] % 20 == 0:
                        print(f"{year}-{month:02d} rows={stats['rows']:,} "
                              f"chunks={stats['chunks']} members={stats['members']}",
                              flush=True)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()

    elapsed = time.time() - started
    if error is None:
        df = finalize(acc, year, month, profile)
        if df.empty:
            df = pd.DataFrame(columns=["unit_id", "collection_year",
                                       "collection_month", "year_month"])
        df.to_parquet(out, index=False, compression="zstd")
        summary = {
            "year": int(year), "month": int(month), "key": key,
            "elapsed_s": round(elapsed, 1), "n_units": int(len(df)),
            "rows": stats["rows"], "chunks": stats["chunks"],
            "members": stats["members"], "error": None,
            "profile_units": int(len(profile)),
            "local": str(tar_path),
        }
    else:
        summary = {
            "year": int(year), "month": int(month), "key": key,
            "elapsed_s": round(elapsed, 1), "n_units": 0,
            "rows": stats["rows"], "chunks": stats["chunks"],
            "members": stats["members"], "error": error,
            "profile_units": int(len(profile)),
            "local": str(tar_path),
        }
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    if delete_tar and tar_path.exists():
        tar_path.unlink()
    if error is not None:
        raise RuntimeError(error)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    ap.add_argument("--key")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--local")
    ap.add_argument("--keep-raw", action="store_true")
    args = ap.parse_args()
    if args.key:
        from .io import parse_key
        parsed = parse_key(args.key)
        if not parsed:
            raise SystemExit(f"cannot parse key {args.key}")
        year, month = parsed["year"], parsed["month"]
    else:
        if not args.year or not args.month:
            raise SystemExit("need --year and --month, or --key")
        year, month = args.year, args.month
    process(year, month, key=args.key, force=args.force, local=args.local,
            keep_raw=args.keep_raw)


if __name__ == "__main__":
    main()
