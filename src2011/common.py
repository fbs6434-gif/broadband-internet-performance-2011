from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "2011"
PROC = ROOT / "data" / "processed" / "2011"
OUT = ROOT / "output" / "2011"

ISP8 = [
    "Comcast",
    "AT&T",
    "TimeWarner",
    "Verizon",
    "Cox",
    "Qwest",
    "Charter",
    "Cablevision",
]

ISP_LABEL = {
    "Comcast": "Comcast",
    "AT&T": "AT&T",
    "TimeWarner": "TimeWarner",
    "Verizon": "Verizon",
    "Cox": "Cox",
    "Qwest": "Qwest",
    "Charter": "Charter",
    "Cablevision": "Cablevision",
    "CenturyLink": "CenturyLink",
    "Windstream": "Windstream",
    "Mediacom": "Mediacom",
    "Frontier": "Frontier",
    "Clearwire": "Clearwire",
    "Brighthouse": "Brighthouse",
    "Insight": "Insight",
    "Wildblue/ViaSat": "Wildblue/ViaSat",
    "Hughes": "Hughes",
}

THROUGHPUT_NAMES = [
    "unit_id",
    "dtime",
    "target",
    "fetch_time",
    "bytes_total",
    "bytes_sec",
    "warmup_time",
    "warmup_bytes",
    "sequence",
    "threads",
    "successes",
    "failures",
]

PING_NAMES = [
    "unit_id",
    "dtime",
    "target",
    "rtt_avg",
    "rtt_min",
    "rtt_max",
    "rtt_std",
    "successes",
    "failures",
]

UDPJITTER_NAMES = [
    "unit_id",
    "dtime",
    "target",
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
    "successes",
    "failures",
]

WEBGET_NAMES = [
    "unit_id",
    "dtime",
    "target",
    "fetch_time",
    "bytes_total",
    "bytes_sec",
    "objects",
    "successes",
    "failures",
]

NETUSAGE_NAMES = [
    "unit_id",
    "dtime",
    "wan_rx_bytes",
    "wan_tx_bytes",
    "sk_rx_bytes",
    "sk_tx_bytes",
]

THROUGHPUT_COLS = [
    "unit_id",
    "dtime",
    "target",
    "fetch_time",
    "bytes_total",
    "bytes_sec",
    "sequence",
    "successes",
    "failures",
]

PING_COLS = [
    "unit_id",
    "dtime",
    "target",
    "rtt_avg",
    "rtt_min",
    "rtt_max",
    "rtt_std",
    "successes",
    "failures",
]

UDPJITTER_COLS = [
    "unit_id",
    "dtime",
    "target",
    "jitter_up",
    "jitter_down",
    "latency",
    "successes",
    "failures",
]

WEBGET_COLS = [
    "unit_id",
    "dtime",
    "target",
    "fetch_time",
    "bytes_total",
    "bytes_sec",
    "objects",
    "successes",
    "failures",
]

NETUSAGE_COLS = NETUSAGE_NAMES


def load_meta() -> pd.DataFrame:
    m = pd.read_csv(RAW / "profile" / "unit_metadata.csv")
    m.columns = [c.strip().lower().replace(" ", "_") for c in m.columns]
    m = m.rename(columns={"unitid": "unit_id"})
    m["isp"] = m["isp"].str.strip()
    m["technology"] = m["technology"].str.strip()
    return m


def load_tz() -> pd.DataFrame:
    tz = pd.read_csv(RAW / "profile" / "unit_tz.csv")
    return tz.rename(columns={"unit_id": "unit_id"})


def add_local_time(df: pd.DataFrame, tz: pd.DataFrame, month: str) -> pd.DataFrame:
    t = tz.set_index("unit_id")
    tz_off = df["unit_id"].map(t["tz"]).astype("float")
    dst_off = df["unit_id"].map(t["dst"]).astype("float")
    off = tz_off.copy()
    if month == "mar":
        std_local = df["dtime"] + pd.to_timedelta(tz_off, unit="h")
        switch = std_local >= pd.Timestamp("2011-03-13 02:00:00")
        off = pd.Series(np.where(switch, dst_off, tz_off), index=df.index)
    df["local_dtime"] = df["dtime"] + pd.to_timedelta(off, unit="h")
    df["local_hour"] = df["local_dtime"].dt.hour
    df["local_dow"] = df["local_dtime"].dt.dayofweek
    return df


def is_mlab(target: pd.Series) -> pd.Series:
    return target.astype("string").str.contains("measurement-lab.org", na=False)


def is_isp_target(target: pd.Series) -> pd.Series:
    return ~is_mlab(target)


def target_site(target: str) -> str:
    s = str(target).strip().lower()
    for p in ("http://", "https://"):
        if s.startswith(p):
            s = s[len(p) :]
    s = s.split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    return s


def month_dir(month: str) -> Path:
    return RAW / month


def proc_dir(month: str) -> Path:
    return PROC / month


def out_dir(month: str) -> Path:
    return OUT / month


def parquet(month: str, kind: str) -> Path:
    return proc_dir(month) / f"{kind}.parquet"


def savefig(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
