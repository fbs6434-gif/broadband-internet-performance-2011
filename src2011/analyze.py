import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import (
    ISP8,
    add_local_time,
    is_mlab,
    load_meta,
    load_tz,
    out_dir,
    parquet,
    savefig,
    target_site,
)

COLORS = {
    "Comcast": "#1f77b4",
    "AT&T": "#ff7f0e",
    "TimeWarner": "#2ca02c",
    "Verizon": "#d62728",
    "Cox": "#9467bd",
    "Qwest": "#8c564b",
    "Charter": "#e377c2",
    "Cablevision": "#7f7f7f",
}
B = 125000.0
MBPS = 1e6


def read_throughput(month, kind):
    cols = [
        "unit_id",
        "dtime",
        "target",
        "fetch_time",
        "bytes_total",
        "bytes_sec",
        "sequence",
        "successes",
    ]
    d = pd.read_parquet(parquet(month, kind), columns=cols)
    d = d[pd.to_numeric(d["successes"], errors="coerce").fillna(0) > 0]
    d = d[is_mlab(d["target"])].copy()
    d["bytes_sec"] = pd.to_numeric(d["bytes_sec"], errors="coerce")
    d["target"] = d["target"].astype("category")
    return d


def final_tests(d):
    t = d[d["sequence"].eq(5).fillna(False)].copy()
    t["mbps"] = t["bytes_sec"] / B
    t = t[t["mbps"].notna()]
    return t[["unit_id", "dtime", "target", "mbps"]]


def unit_metrics(tests, meta, prefix):
    g = tests.groupby("unit_id")["mbps"]
    u = pd.DataFrame(
        {
            f"{prefix}_n": g.size(),
            f"{prefix}_mean": g.mean(),
            f"{prefix}_median": g.median(),
            f"{prefix}_p95": g.quantile(0.95),
        }
    )
    u[f"{prefix}_std"] = g.std()
    u[f"{prefix}_avg_p95"] = u[f"{prefix}_mean"] / u[f"{prefix}_p95"]
    u = u.reset_index().merge(
        meta[["unit_id", "isp", "technology"]], on="unit_id", how="inner"
    )
    return u


def table2(dl, ul, meta):
    total = meta.groupby("isp")["unit_id"].nunique()
    ad = dl[dl["down_n"] > 100].groupby("isp")["unit_id"].nunique()
    au = ul[ul["up_n"] > 100].groupby("isp")["unit_id"].nunique()
    t = pd.DataFrame({"total": total, "active_dl": ad, "active_ul": au}).fillna(0)
    t = t.loc[[i for i in ISP8 if i in t.index]].astype(int)
    paper = pd.DataFrame(
        {
            "paper_total": [864, 787, 690, 551, 381, 265, 187, 104],
            "paper_active": [560, 335, 381, 256, 161, 117, 51, 53],
        },
        index=ISP8,
    )
    return paper.join(t, how="outer")


def isp_throughput_summary(dl, ul):
    d = dl[dl["down_n"] > 100]
    u = ul[ul["up_n"] > 100]
    s = pd.DataFrame(
        {
            "dl_units": d.groupby("isp")["unit_id"].nunique(),
            "dl_avg_p95": d.groupby("isp")["down_avg_p95"].median(),
            "dl_p95_mbps": d.groupby("isp")["down_p95"].median(),
            "dl_std": d.groupby("isp")["down_std"].median(),
            "ul_units": u.groupby("isp")["unit_id"].nunique(),
            "ul_avg_p95": u.groupby("isp")["up_avg_p95"].median(),
            "ul_p95_mbps": u.groupby("isp")["up_p95"].median(),
            "ul_std": u.groupby("isp")["up_std"].median(),
        }
    )
    return s.loc[[i for i in ISP8 if i in s.index]]


def powerboost(d, meta):
    pb = d.sort_values(["unit_id", "dtime", "target", "sequence"]).copy()
    g = pb.groupby(["unit_id", "dtime", "target"], sort=False)
    pb["db"] = g["bytes_total"].diff()
    pb["dt"] = g["fetch_time"].diff()
    pb = pb[(pb["sequence"] > 0) & (pb["sequence"] <= 5)].copy()
    pb["int_mbps"] = pb["db"] * 8 / MBPS / (pb["dt"] / MBPS)
    first = pb[pb["sequence"] == 1].set_index(["unit_id", "dtime", "target"])[
        "int_mbps"
    ]
    pb = pb.join(first.rename("first"), on=["unit_id", "dtime", "target"])
    pb = pb[
        pb["first"].between(0.05, 500) & pb["int_mbps"].notna() & (pb["int_mbps"] > 0)
    ]
    pb["norm"] = pb["int_mbps"] / pb["first"]
    pb = pb.merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
    return pb


def powerboost_curve(pb):
    c = (
        pb[pb["isp"].isin(ISP8)]
        .groupby(["isp", "sequence"])["norm"]
        .agg(["mean", "median", "count"])
        .reset_index()
    )
    return c


def tod_throughput(down_tests, dl, meta, tz, month):
    t = down_tests.merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
    t = add_local_time(t, tz, month)
    p95 = dl.set_index("unit_id")["down_p95"]
    t["unit_p95"] = t["unit_id"].map(p95)
    t = t[t["unit_p95"] > 0]
    t["norm"] = t["mbps"] / t["unit_p95"]
    uh = t.groupby(["unit_id", "isp", "local_hour"])["norm"].mean().reset_index()
    g = uh.groupby(["isp", "local_hour"])["norm"].agg(["mean", "std", "count"])
    return g.reset_index()


def ping_metrics(month, meta, tz):
    cols = [
        "unit_id",
        "dtime",
        "target",
        "rtt_avg",
        "successes",
        "failures",
    ]
    p = pd.read_parquet(parquet(month, "ping"), columns=cols)
    p["rtt_avg"] = pd.to_numeric(p["rtt_avg"], errors="coerce")
    p["successes"] = pd.to_numeric(p["successes"], errors="coerce")
    p["failures"] = pd.to_numeric(p["failures"], errors="coerce")
    p = p[(p["successes"] + p["failures"]) > 0].copy()
    p["rtt_ms"] = p["rtt_avg"] / 1000.0
    p["loss"] = p["failures"] / (p["successes"] + p["failures"])
    p["mlab"] = is_mlab(p["target"])
    p = p.merge(meta[["unit_id", "isp", "technology"]], on="unit_id", how="inner")
    rows = []
    for cls, name in [("mlab", "e2e"), ("isp", "edge")]:
        q = p[p["mlab"] if cls == "mlab" else ~p["mlab"]]
        g = q.groupby("unit_id")
        u = pd.DataFrame(
            {
                f"{name}_baseline": g["rtt_ms"].quantile(0.10),
                f"{name}_median": g["rtt_ms"].median(),
                f"{name}_mean": g["rtt_ms"].mean(),
                f"{name}_std": g["rtt_ms"].std(),
                f"{name}_loss": g["loss"].mean(),
                f"{name}_n": g.size(),
            }
        ).reset_index()
        u = u.merge(meta[["unit_id", "isp", "technology"]], on="unit_id", how="inner")
        rows.append(u)
    return rows[0], rows[1], p


def table4(edge):
    g = edge.groupby("isp")
    t = pd.DataFrame(
        {
            "units": g["unit_id"].nunique(),
            "latency_mean": g["edge_baseline"].mean(),
            "latency_std": g["edge_baseline"].std(),
            "loss_mean_pct": 100 * g["edge_loss"].mean(),
            "loss_std_pct": 100 * g["edge_loss"].std(),
        }
    )
    return t.loc[[i for i in ISP8 if i in t.index]]


def under_load(month, baseline, meta):
    base = baseline.set_index("unit_id")["e2e_baseline"]
    out = {}
    for kind, name in [("dlping", "down"), ("ulping", "up")]:
        cols = ["unit_id", "target", "rtt_avg", "successes", "failures"]
        p = pd.read_parquet(parquet(month, kind), columns=cols)
        p = p[is_mlab(p["target"])].copy()
        p["rtt_ms"] = pd.to_numeric(p["rtt_avg"], errors="coerce") / 1000.0
        g = p.groupby("unit_id")["rtt_ms"].median().rename(f"{name}_load")
        u = g.reset_index()
        u = u.merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
        u["baseline"] = u["unit_id"].map(base)
        u = u[(u["baseline"] > 0) & u[f"{name}_load"].notna()]
        u[f"{name}_ratio"] = u[f"{name}_load"] / u["baseline"]
        u = u[u[f"{name}_ratio"].between(0, 1000)]
        out[name] = u
    return out


def jitter_check(month):
    cols = ["unit_id", "target", "jitter_up", "jitter_down", "latency"]
    j = pd.read_parquet(parquet(month, "udpjitter"), columns=cols)
    res = {}
    for c in ["jitter_up", "jitter_down", "latency"]:
        x = pd.to_numeric(j[c], errors="coerce")
        res[c] = int(x.notna().sum())
    return res


def web_metrics(month, dl, edge, meta):
    cols = ["unit_id", "target", "fetch_time", "bytes_total", "objects", "successes"]
    w = pd.read_parquet(parquet(month, "webget"), columns=cols)
    w = w[(w["successes"] > 0) & (w["fetch_time"] > 0)].copy()
    w["fetch_ms"] = pd.to_numeric(w["fetch_time"], errors="coerce") / 1000.0
    site = w["target"].astype("string").str.lower()
    site = site.str.replace(r"^https?://", "", regex=True)
    site = site.str.split("/").str[0].str.replace(r"^www\.", "", regex=True)
    w["site"] = site
    g = w.groupby(["unit_id", "site"])
    u = pd.DataFrame(
        {
            "fetch_ms": g["fetch_ms"].median(),
            "bytes": g["bytes_total"].median(),
            "objects": g["objects"].median(),
            "n": g.size(),
        }
    ).reset_index()
    fb = u[u["site"] == "facebook.com"].merge(
        dl[["unit_id", "down_p95"]], on="unit_id", how="inner"
    )
    fb = fb.merge(
        edge[["unit_id", "edge_baseline"]], on="unit_id", how="inner"
    )
    return u, fb


def fig6_scatter(dl, ul):
    d = dl.merge(ul[["unit_id", "up_mean"]], on="unit_id")
    d = d[(d["down_mean"] > 0) & (d["up_mean"] > 0) & d["isp"].isin(ISP8)]
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    for isp in ISP8:
        s = d[d["isp"] == isp]
        ax.scatter(
            s["down_mean"],
            s["up_mean"],
            s=6,
            alpha=0.35,
            color=COLORS[isp],
            label=isp,
            linewidths=0,
        )
    lims = [0.05, 300]
    ax.plot(lims, lims, color="k", lw=0.6, ls="--")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Average download rate (Mbit/s)")
    ax.set_ylabel("Average upload rate (Mbit/s)")
    ax.set_title("Fig 6 analog: average download vs upload per user")
    ax.legend(fontsize=7, markerscale=2, ncol=2, frameon=False)
    return fig


def cdf(ax, values, color, label):
    v = np.sort(np.asarray(values))
    y = np.arange(1, len(v) + 1) / len(v)
    ax.plot(v, y, color=color, label=label, lw=1.2)


def fig7_cdf(dl, ul):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for isp in ISP8:
        s = dl[(dl["isp"] == isp) & (dl["down_n"] > 100)]
        if len(s):
            cdf(axes[0], s["down_avg_p95"], COLORS[isp], isp)
        s = ul[(ul["isp"] == isp) & (ul["up_n"] > 100)]
        if len(s):
            cdf(axes[1], s["up_avg_p95"], COLORS[isp], isp)
    axes[0].set_title("(a) Download")
    axes[1].set_title("(b) Upload")
    for ax in axes:
        ax.set_xlim(0, 1.02)
        ax.set_xlabel("Avg/P95")
    axes[0].set_ylabel("CDF")
    axes[1].legend(fontsize=7, frameon=False)
    fig.suptitle("Fig 7 analog: consistency of throughput (Avg/P95)")
    return fig


def fig8_tod(tod, ping, month, tz, meta):
    p = ping.copy()
    p = add_local_time(p, tz, month)
    lg = p.groupby(["isp", "local_hour"])["loss"].mean().reset_index()
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for isp in ISP8:
        s = tod[tod["isp"] == isp].sort_values("local_hour")
        axes[0].plot(s["local_hour"], s["mean"], color=COLORS[isp], label=isp, lw=1.2)
        axes[1].plot(
            s["local_hour"], s["std"], color=COLORS[isp], label=isp, lw=1.2
        )
        l = lg[lg["isp"] == isp].sort_values("local_hour")
        axes[2].plot(
            l["local_hour"], 100 * l["loss"], color=COLORS[isp], label=isp, lw=1.2
        )
    axes[0].set_ylabel("Normalized throughput (mean / user P95)")
    axes[1].set_ylabel("Std. dev. of normalized throughput")
    axes[2].set_ylabel("Loss (%)")
    for ax in axes:
        ax.set_xlabel("Local hour of day")
        ax.set_xticks(range(0, 24, 4))
        ax.grid(alpha=0.25)
    axes[2].legend(fontsize=7, frameon=False, ncol=2)
    fig.suptitle("Fig 8 analog: time-of-day effects")
    return fig


def fig9_powerboost(curve):
    fig, ax = plt.subplots(figsize=(6.5, 4.3))
    for isp in ISP8:
        s = curve[curve["isp"] == isp].sort_values("sequence")
        ax.plot(
            s["sequence"],
            s["mean"],
            marker="o",
            ms=3,
            color=COLORS[isp],
            label=isp,
            lw=1.2,
        )
    ax.axhline(1.0, color="k", lw=0.6, ls="--")
    ax.set_xlabel("5-second interval during throughput test")
    ax.set_ylabel("Normalized throughput (interval / first)")
    ax.set_title("Fig 9 analog: PowerBoost progression")
    ax.legend(fontsize=7, frameon=False, ncol=2)
    ax.grid(alpha=0.25)
    return fig


def fig11_web(fb):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    ax = axes[0]
    ax.scatter(fb["down_p95"], fb["fetch_ms"], s=8, alpha=0.35, color="#1f77b4")
    ax.set_xscale("log")
    ax.set_xlabel("95th percentile download speed (Mbit/s)")
    ax.set_ylabel("Facebook fetch time (ms)")
    ax.set_title("(a) Fetch time vs download speed")
    ax.grid(alpha=0.25)
    hi = fb[fb["down_p95"] > 6]
    ax = axes[1]
    ax.scatter(hi["edge_baseline"], hi["fetch_ms"], s=8, alpha=0.35, color="#d62728")
    ax.set_xlabel("Baseline latency proxy (ms)")
    ax.set_ylabel("Facebook fetch time (ms)")
    ax.set_title("(b) Fetch time vs baseline latency (>6 Mbit/s)")
    ax.grid(alpha=0.25)
    ymax = float(fb["fetch_ms"].quantile(0.99)) * 1.05
    for a in axes:
        a.set_ylim(0, ymax)
    fig.suptitle("Fig 11 analog: web fetch time")
    return fig


def fig12_latency(edge):
    bins = [0, 10, 20, 30, 40, 50, 60, np.inf]
    labels = ["0-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60+"]
    rows = []
    for isp in ISP8:
        s = edge[edge["isp"] == isp]["edge_baseline"].dropna()
        if not len(s):
            continue
        h = pd.cut(s, bins=bins, labels=labels, right=False).value_counts(
            normalize=True
        )
        rows.append(pd.Series(h, name=isp))
    h = pd.DataFrame(rows).fillna(0) * 100
    fig, ax = plt.subplots(figsize=(10, 4))
    bottom = np.zeros(len(h))
    cmap = plt.get_cmap("viridis")
    for i, lab in enumerate(labels):
        vals = h[lab].values if lab in h.columns else np.zeros(len(h))
        ax.bar(h.index, vals, bottom=bottom, label=lab, color=cmap(i / 7))
        bottom += vals
    ax.set_ylabel("Percentage of users")
    ax.set_title("Fig 12 analog: baseline latency distribution (edge proxy)")
    ax.legend(title="Latency (ms)", fontsize=7, ncol=7, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.set_ylim(0, 100)
    fig.subplots_adjust(bottom=0.22)
    return fig


def fig13_under_load(ul):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, name, title in [
        (axes[0], "down", "(a) Download saturated"),
        (axes[1], "up", "(b) Upload saturated"),
    ]:
        data = []
        labels = []
        col = f"{name}_ratio"
        for isp in ISP8:
            d = ul[name]
            s = d[d["isp"] == isp][col].dropna()
            if len(s) > 10:
                data.append(s.values)
                labels.append(isp)
        bp = ax.boxplot(data, labels=labels, showfliers=False, patch_artist=True)
        for patch, isp in zip(bp["boxes"], labels):
            patch.set_facecolor(COLORS[isp])
            patch.set_alpha(0.6)
        ax.set_yscale("log")
        ax.set_ylabel("Latency under load / baseline")
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(alpha=0.25, axis="y")
    fig.suptitle("Fig 13 analog: latency under load")
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="feb")
    args = ap.parse_args()
    month = args.month
    od = out_dir(month)
    od.mkdir(parents=True, exist_ok=True)

    meta = load_meta()
    tz = load_tz()

    down = read_throughput(month, "httpgetmt")
    down_tests = final_tests(down)
    down_tests.to_parquet(parquet(month, "tests_down"), index=False)
    dl = unit_metrics(down_tests, meta, "down")
    pbcols = down[["unit_id", "dtime", "target", "sequence", "fetch_time", "bytes_total"]].copy()
    del down
    pb = powerboost(pbcols, meta)
    del pbcols
    curve = powerboost_curve(pb)
    del pb
    up = read_throughput(month, "httppostmt")
    up_tests = final_tests(up)
    up_tests.to_parquet(parquet(month, "tests_up"), index=False)
    ul = unit_metrics(up_tests, meta, "up")
    del up

    t2 = table2(dl, ul, meta)
    isp_sum = isp_throughput_summary(dl, ul)
    unit = dl.merge(
        ul[
            [
                "unit_id",
                "up_n",
                "up_mean",
                "up_median",
                "up_p95",
                "up_std",
                "up_avg_p95",
            ]
        ],
        on="unit_id",
        how="outer",
    )
    unit.to_csv(od / "unit_throughput.csv", index=False)
    t2.to_csv(od / "table2_analog.csv")
    isp_sum.to_csv(od / "isp_throughput.csv")

    curve.to_csv(od / "powerboost_curve.csv", index=False)

    tod = tod_throughput(down_tests, dl, meta, tz, month)
    tod.to_csv(od / "tod_throughput.csv", index=False)

    e2e, edge, _ = ping_metrics(month, meta, tz)
    t4 = table4(edge)
    t4.to_csv(od / "table4_analog.csv")
    e2e.to_csv(od / "latency_e2e_unit.csv", index=False)
    edge.to_csv(od / "latency_edge_unit.csv", index=False)

    uload = under_load(month, e2e, meta)
    for k, v in uload.items():
        v.to_csv(od / f"under_load_{k}.csv", index=False)

    jit = jitter_check(month)

    summary = {
        "month": month,
        "units_meta": int(meta["unit_id"].nunique()),
        "units_down": int(dl["unit_id"].nunique()),
        "units_up": int(ul["unit_id"].nunique()),
        "active_down_gt100": int((dl["down_n"] > 100).sum()),
        "active_up_gt100": int((ul["up_n"] > 100).sum()),
        "jitter_nonnull": jit,
        "table2": t2.reset_index().to_dict(orient="records"),
        "isp_throughput": isp_sum.reset_index().to_dict(orient="records"),
        "table4": t4.reset_index().to_dict(orient="records"),
    }
    with open(od / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("table2", "isp_throughput", "table4")}, indent=2))
    print(t2.to_string())
    print(isp_sum.round(3).to_string())
    print(t4.round(3).to_string())


if __name__ == "__main__":
    main()
