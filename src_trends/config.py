import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("TRENDS_DATA", ROOT / "data" / "trends"))
OUT = Path(os.environ.get("TRENDS_OUT", ROOT / "output" / "trends"))
REPORTS = Path(os.environ.get("TRENDS_REPORTS", ROOT / "reports" / "trends"))
PROFILES = DATA / "profiles"
UNITS = DATA / "units"
SUMMARIES = DATA / "summaries"
LOGS = DATA / "logs"

for d in (DATA, OUT, REPORTS, PROFILES, UNITS, SUMMARIES, LOGS):
    d.mkdir(parents=True, exist_ok=True)

BUCKET = os.environ.get("MBA_BUCKET", "mba-data")
ENDPOINT = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT_URL")

CHUNK_ROWS = int(os.environ.get("TRENDS_CHUNK_ROWS", "1000000"))
MAX_WORKERS = int(os.environ.get("TRENDS_WORKERS", "3"))

MONTH_NUM = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

MONTH_NAME = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
    7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
}

THROUGHPUT_12 = [
    "unit_id", "dtime", "target", "fetch_time", "bytes_total", "bytes_sec",
    "warmup_time", "warmup_bytes", "sequence", "threads", "successes", "failures",
]

THROUGHPUT_15 = [
    "unit_id", "dtime", "target", "address", "fetch_time", "bytes_total",
    "bytes_sec", "bytes_sec_interval", "warmup_time", "warmup_bytes",
    "sequence", "threads", "successes", "failures", "location_id",
]

THROUGHPUT_14 = [
    "unit_id", "dtime", "target", "address", "fetch_time", "bytes_total",
    "bytes_sec", "bytes_sec_interval", "warmup_time", "warmup_bytes",
    "sequence", "threads", "successes", "failures",
]

PING_9 = [
    "unit_id", "dtime", "target", "rtt_avg", "rtt_min", "rtt_max",
    "rtt_std", "successes", "failures",
]

PING_10 = PING_9 + ["location_id"]

JITTER_15 = [
    "unit_id", "dtime", "target", "packet_size", "stream_rate", "duration",
    "packets_up_sent", "packets_down_sent", "packets_up_recv",
    "packets_down_recv", "jitter_up", "jitter_down", "latency",
    "successes", "failures",
]

JITTER_16 = JITTER_15 + ["location_id"]

PROFILE_MAP = {
    2011: [(None, "unit_metadata.csv", "fcc-mba/2011/profile/unit_metadata.csv", None, {
        "unit_id": "UnitID", "isp": "ISP", "technology": "TECHNOLOGY"}),
           (None, "unit_tz.csv", "fcc-mba/2011/profile/unit_tz.csv", None, {
        "unit_id": "unit_id", "tz": "tz", "dst": "dst"})],
    2012: [(None, "unit-profile-april-2012.xlsx",
            "fcc-mba/2012/profile/unit-profile-april-2012.xlsx", "openpyxl", {
        "unit_id": "UNIT_ID", "isp": "ISP", "technology": "TECHNOLOGY",
        "tz": "UTC_OFFSET", "dst": "UTC_OFFSET_DST"}),
           (9, "FCC_UnitProfile_Sept12.xls",
            "fcc-mba/2012/profile/FCC_UnitProfile_Sept12.xls", "xlrd", {
        "unit_id": "unit_id", "isp": "isp", "technology": "Technology",
        "tz": "UTC_OFFSET", "dst": "UTC_OFFSET_DST"})],
    2013: [(None, "FCC_Unit_Profile_20140207.xlsx",
            "fcc-mba/2013/profile/FCC_Unit_Profile_20140207.xlsx", "openpyxl", {
        "unit_id": "unit_id", "isp": "isp", "technology": "TECHNOLOGY",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2014: [(None, "FCC_UnitProfile_Sept14.xls",
            "fcc-mba/2014/profile/FCC_UnitProfile_Sept14.xls", "openpyxl", {
        "unit_id": "unit_id", "isp": "isp", "technology": "TECHNOLOGY",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2015: [(None, "Unit-Profile-sept2015.xlsx",
            "fcc-mba/2015/profile/Unit-Profile-sept2015.xlsx", "openpyxl", {
        "unit_id": "unit_id", "isp": "isp", "technology": "TECHNOLOGY",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2016: [(None, "Unit-Profile-sept2016.xlsx",
            "fcc-mba/2016/profile/Unit-Profile-sept2016.xlsx", "openpyxl", {
        "unit_id": "unit_id", "isp": "isp", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2017: [(None, "Unit-Profile-sept2017.xlsx",
            "fcc-mba/2017/profile/Unit-Profile-sept2017.xlsx", "openpyxl", {
        "unit_id": "unit_id", "isp": "ISP", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2018: [(None, "Unit-Profile-sept2018.xlsx",
            "fcc-mba/2018/profile/Unit-Profile-sept2018.xlsx", "openpyxl", {
        "unit_id": "Unit ID", "isp": "ISP", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2019: [(None, "Unit-Profile-sept2019.xlsx",
            "fcc-mba/2019/profile/Unit-Profile-sept2019.xlsx", "openpyxl", {
        "unit_id": "Unit ID", "isp": "ISP", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2020: [(None, "unit-profile-sept2020.xlsx",
            "fcc-mba/2020/profile/unit-profile-sept2020.xlsx", "openpyxl", {
        "unit_id": "Unit ID", "isp": "ISP", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2021: [(None, "unit-profile-sept2021.xlsx",
            "fcc-mba/2021/profile/unit-profile-sept2021.xlsx", "openpyxl", {
        "unit_id": "Unit ID", "isp": "ISP", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2022: [(None, "unit-profile-sept2022.xlsx",
            "fcc-mba/2022/profile/unit-profile-sept2022.xlsx", "openpyxl", {
        "unit_id": "Unit ID", "isp": "ISP", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
    2023: [(None, "unit-profile-sept2022.xlsx",
            "fcc-mba/2022/profile/unit-profile-sept2022.xlsx", "openpyxl", {
        "unit_id": "Unit ID", "isp": "ISP", "technology": "Technology",
        "tz": "timezone_offset", "dst": "timezone_offset_dst"})],
}

ISP_CANON = {
    "comcast": "Comcast", "comcast cable": "Comcast",
    "at&t": "AT&T", "att": "AT&T", "at&t internet": "AT&T",
    "at&t u-verse": "AT&T", "at&t uverse": "AT&T",
    "time warner cable": "TimeWarner", "timewarner": "TimeWarner",
    "time warner": "TimeWarner", "twc": "TimeWarner",
    "verizon": "Verizon", "verizon fios": "Verizon", "fios": "Verizon",
    "cox": "Cox", "cox communications": "Cox",
    "qwest": "Qwest", "centurylink": "CenturyLink", "century link": "CenturyLink",
    "charter": "Charter", "charter spectrum": "Charter", "spectrum": "Charter",
    "cablevision": "Cablevision", "altice": "Cablevision",
    "altice usa": "Cablevision", "optimum": "Cablevision",
    "frontier": "Frontier", "frontier communications": "Frontier",
    "windstream": "Windstream", "mediacom": "Mediacom",
    "insight": "Insight", "brighthouse": "Brighthouse",
    "clearwire": "Clearwire", "hughes": "Hughes",
    "wildblue": "Wildblue/ViaSat", "viasat": "Wildblue/ViaSat",
    "earthlink": "EarthLink", "cincinnati bell": "Cincinnati Bell",
    "tds": "TDS", "consolidated": "Consolidated",
    "sonic": "Sonic", "google fiber": "Google Fiber",
    "at&t ipbb": "AT&T", "at&t dsl": "AT&T", "at&t fiber": "AT&T",
    "at&t u-verse": "AT&T", "at&t uverse": "AT&T",
    "verizon dsl": "Verizon", "verizon fiber": "Verizon",
    "verizon fios": "Verizon", "verizon wireless": "Verizon",
    "frontier dsl": "Frontier", "frontier fiber": "Frontier",
    "cincinnati bell dsl": "Cincinnati Bell",
    "cincinnati bell fiber": "Cincinnati Bell",
    "centurylink dsl": "CenturyLink", "centurylink fiber": "CenturyLink",
    "windstream dsl": "Windstream", "windstream fiber": "Windstream",
    "charter spectrum": "Charter", "spectrum": "Charter",
    "cox cable": "Cox", "comcast xfinity": "Comcast", "xfinity": "Comcast",
    "miscellaneous": "Other",
}

TECH_CANON = {
    "cable": "Cable", "docsis": "Cable",
    "dsl": "DSL", "adsl": "DSL", "vdsl": "DSL",
    "fiber": "Fiber", "ftth": "Fiber", "fios": "Fiber",
    "satellite": "Satellite",
    "fixed wireless": "Fixed Wireless", "wireless": "Fixed Wireless",
    "mobile": "Mobile",
    "ethernet": "Ethernet",
    "cable - business": "Cable", "cable business": "Cable",
    "sat": "Satellite", "satellite - business": "Satellite",
    "fiber - business": "Fiber", "fiber business": "Fiber",
    "dsl - business": "DSL", "dsl business": "DSL",
    "fixed wireless - business": "Fixed Wireless",
}

TARGET_CLASS = {
    0: "other", 1: "mlab", 2: "level3", 3: "samknows", 4: "isp",
}
