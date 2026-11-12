import argparse
import contextlib
import json
import multiprocessing as mp
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from . import config as C
from .io import inventory
from .process_month import process

_DOWNLOAD_SEM = None


def _init_worker(sem):
    global _DOWNLOAD_SEM
    _DOWNLOAD_SEM = sem


def _run(entry, force=False, keep_raw=False):
    year, month = entry["year"], entry["month"]
    log_path = C.LOGS / f"{year}-{month:02d}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with open(log_path, "a") as log, contextlib.redirect_stdout(log), \
            contextlib.redirect_stderr(log):
        print(f"\n=== {year}-{month:02d} {entry['key']} ===", flush=True)
        try:
            summary = process(year, month, force=force, keep_raw=keep_raw,
                              download_sem=_DOWNLOAD_SEM)
            summary["wall_s"] = round(time.time() - started, 1)
            return summary
        except Exception as exc:
            return {
                "year": year, "month": month, "key": entry["key"],
                "error": f"{type(exc).__name__}: {exc}",
                "wall_s": round(time.time() - started, 1),
            }


def _clean_stale():
    for path in (C.DATA / "raw").glob("*"):
        if path.suffix in (".part",) or path.name.endswith(".tar.gz.part"):
            try:
                path.unlink()
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=C.MAX_WORKERS)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--months", nargs="*", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--keep-raw", action="store_true")
    args = ap.parse_args()

    rows = inventory()
    if args.years:
        rows = [r for r in rows if r["year"] in set(args.years)]
    if args.months:
        rows = [r for r in rows if r["month"] in set(args.months)]
    rows.sort(key=lambda r: (r["year"], r["month"]))
    if args.limit:
        rows = rows[:args.limit]

    done = []
    pending = []
    for r in rows:
        out = C.UNITS / f"{r['year']}-{r['month']:02d}.parquet"
        done.append(r) if out.exists() and not args.force else pending.append(r)

    print(f"inventory={len(rows)} done={len(done)} pending={len(pending)} "
          f"workers={args.workers}", flush=True)

    _clean_stale()
    free = shutil.disk_usage(C.DATA).free / 1e9
    print(f"free_disk_gb={free:.1f}", flush=True)

    run_log = C.LOGS / "run_all.log"
    failures = []
    started = time.time()
    sem = mp.Semaphore(1)
    with ProcessPoolExecutor(max_workers=max(1, args.workers),
                             initializer=_init_worker, initargs=(sem,)) as pool:
        futures = {
            pool.submit(_run, r, args.force, args.keep_raw): r for r in pending
        }
        for i, fut in enumerate(as_completed(futures), 1):
            r = futures[fut]
            try:
                summary = fut.result()
            except Exception as exc:
                summary = {"year": r["year"], "month": r["month"],
                           "key": r["key"], "error": str(exc)}
            line = json.dumps(summary)
            print(f"[{i}/{len(pending)}] {line}", flush=True)
            with open(run_log, "a") as fh:
                fh.write(line + "\n")
            if summary.get("error"):
                failures.append(summary)
            elapsed = time.time() - started
            rate = elapsed / i
            print(f"   elapsed={elapsed/60:.1f}m eta={rate*(len(pending)-i)/60:.1f}m",
                  flush=True)

    print(f"finished failures={len(failures)} elapsed={(time.time()-started)/60:.1f}m",
          flush=True)
    for f in failures:
        print(json.dumps(f), flush=True)


if __name__ == "__main__":
    main()
