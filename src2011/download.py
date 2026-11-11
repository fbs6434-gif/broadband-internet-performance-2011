import argparse
import os
import tarfile
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "2011"
BUCKET = "mba-data"
YEAR = "2011"


def load_env() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def client():
    endpoint = os.getenv("AWS_ENDPOINT_URL") or os.getenv("S3_ENDPOINT_URL")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    args = ap.parse_args()
    load_env()
    dest = RAW / args.month
    dest.mkdir(parents=True, exist_ok=True)
    key = f"fcc-mba/{YEAR}/raw/raw-bulk-data-{args.month}-{YEAR}.tar.gz"
    tar_path = dest / Path(key).name
    if not tar_path.exists():
        print(f"downloading s3://{BUCKET}/{key} -> {tar_path}")
        client().download_file(BUCKET, key, str(tar_path))
    else:
        print(f"exists {tar_path}")
    names = {p.name for p in dest.glob("*.csv")}
    if len(names) >= 12:
        print("csvs already extracted")
        return
    print("extracting")
    with tarfile.open(tar_path) as t:
        t.extractall(dest)
    print("done")


if __name__ == "__main__":
    main()
