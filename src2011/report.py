import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyze import (
    COLORS,
    fig6_scatter,
    fig7_cdf,
    fig9_powerboost,
    fig11_web,
    fig12_latency,
    fig13_under_load,
)
from common import ISP8, add_local_time, is_mlab, load_meta, load_tz, out_dir, parquet, savefig


def loss_by_hour(month, meta, tz):
    cols = ["unit_id", "dtime", "target", "successes", "failures"]
    p = pd.read_parquet(parquet(month, "ping"), columns=cols)
    p = p[is_mlab(p["target"])].copy()
    p["successes"] = pd.to_numeric(p["successes"], errors="coerce")
    p["failures"] = pd.to_numeric(p["failures"], errors="coerce")
    p = p[(p["successes"] + p["failures"]) > 0].copy()
    p["loss"] = p["failures"] / (p["successes"] + p["failures"])
    p = p.merge(meta[["unit_id", "isp"]], on="unit_id", how="inner")
    p = add_local_time(p, tz, month)
    return p.groupby(["isp", "local_hour"])["loss"].mean().reset_index()


def fig8_local(tod, loss):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for isp in ISP8:
        s = tod[tod["isp"] == isp].sort_values("local_hour")
        axes[0].plot(s["local_hour"], s["mean"], color=COLORS[isp], label=isp, lw=1.2)
        axes[1].plot(s["local_hour"], s["std"], color=COLORS[isp], label=isp, lw=1.2)
        l = loss[loss["isp"] == isp].sort_values("local_hour")
        axes[2].plot(l["local_hour"], 100 * l["loss"], color=COLORS[isp], label=isp, lw=1.2)
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


def combined_latency(e2e, edge):
    u = e2e[
        ["unit_id", "isp", "technology", "e2e_baseline", "e2e_median", "e2e_loss", "e2e_n"]
    ].merge(
        edge[["unit_id", "edge_baseline", "edge_median", "edge_loss", "edge_n"]],
        on="unit_id",
        how="outer",
    )
    u["baseline_proxy"] = u[["e2e_baseline", "edge_baseline"]].min(axis=1)
    u["loss_proxy"] = u["e2e_loss"].fillna(u["edge_loss"])
    return u


def table4_proxy(u):
    g = u.groupby("isp")
    t = pd.DataFrame(
        {
            "units": g["unit_id"].nunique(),
            "latency_mean": g["baseline_proxy"].mean(),
            "latency_std": g["baseline_proxy"].std(),
            "loss_mean_pct": 100 * g["loss_proxy"].mean(),
            "loss_std_pct": 100 * g["loss_proxy"].std(),
        }
    )
    return t.loc[[i for i in ISP8 if i in t.index]]


def web_facebook(month, unit, e2e, edge, meta):
    import pyarrow.parquet as pq

    cols = ["unit_id", "target", "fetch_time", "bytes_total", "objects", "successes"]
    pf = pq.ParquetFile(parquet(month, "webget"))
    parts = []
    for batch in pf.iter_batches(batch_size=1_000_000, columns=cols):
        b = batch.to_pandas()
        b = b[(b["successes"] > 0) & (b["fetch_time"] > 0)]
        if b.empty:
            continue
        t = b["target"].astype("string").str.lower()
        t = t.str.replace(r"^https?://", "", regex=True)
        t = t.str.split("/").str[0].str.replace(r"^www\.", "", regex=True)
        b = b[t == "facebook.com"]
        if len(b):
            b = b.assign(fetch_ms=b["fetch_time"] / 1000.0)
            parts.append(b[["unit_id", "fetch_ms", "bytes_total", "objects"]])
    w = pd.concat(parts, ignore_index=True)
    g = w.groupby("unit_id")
    fb = pd.DataFrame(
        {
            "fetch_ms": g["fetch_ms"].median(),
            "bytes": g["bytes_total"].median(),
            "objects": g["objects"].median(),
            "n": g.size(),
        }
    ).reset_index()
    fb = fb.merge(unit[["unit_id", "isp", "down_p95"]], on="unit_id", how="inner")
    fb = fb.merge(edge[["unit_id", "edge_baseline"]], on="unit_id", how="left")
    fb["baseline"] = fb["edge_baseline"].fillna(
        fb["unit_id"].map(e2e.set_index("unit_id")["e2e_baseline"])
    )
    fb["edge_baseline"] = fb["baseline"]
    return fb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="feb")
    args = ap.parse_args()
    month = args.month
    od = out_dir(month)
    meta = load_meta()
    tz = load_tz()

    unit = pd.read_csv(od / "unit_throughput.csv")
    dl = unit[unit["down_n"].notna()].copy()
    ul = unit[unit["up_n"].notna()].copy()
    tod = pd.read_csv(od / "tod_throughput.csv")
    curve = pd.read_csv(od / "powerboost_curve.csv")
    e2e = pd.read_csv(od / "latency_e2e_unit.csv")
    edge = pd.read_csv(od / "latency_edge_unit.csv")
    ud = {k: pd.read_csv(od / f"under_load_{k}.csv") for k in ("down", "up")}

    comb = combined_latency(e2e, edge)
    comb.to_csv(od / "latency_proxy_unit.csv", index=False)
    t4p = table4_proxy(comb)
    t4p.to_csv(od / "table4_proxy.csv")

    loss = loss_by_hour(month, meta, tz)
    loss.to_csv(od / "tod_loss.csv", index=False)

    dl6 = dl.drop(columns=[c for c in dl.columns if c.startswith("up_")])
    savefig(fig6_scatter(dl6, ul), od / "fig6_scatter.png")
    savefig(fig7_cdf(dl, ul), od / "fig7_avg_p95_cdf.png")
    savefig(fig8_local(tod, loss), od / "fig8_tod.png")
    savefig(fig9_powerboost(curve), od / "fig9_powerboost.png")
    comb12 = comb[["unit_id", "isp", "technology", "baseline_proxy"]].rename(columns={"baseline_proxy": "edge_baseline"})
    savefig(fig12_latency(comb12), od / "fig12_baseline_latency.png")
    savefig(fig13_under_load(ud), od / "fig13_under_load.png")

    fb = web_facebook(month, unit, e2e, edge, meta)
    fb.to_csv(od / "web_facebook.csv", index=False)
    savefig(fig11_web(fb), od / "fig11_web.png")

    r = fb[["down_p95", "baseline", "fetch_ms"]].dropna()
    summary = {
        "table4_proxy": t4p.reset_index().to_dict(orient="records"),
        "facebook_units": int(len(fb)),
        "facebook_bytes_median": float(fb["bytes"].median()),
        "facebook_objects_median": float(fb["objects"].median()),
        "facebook_fetch_ms_median": float(fb["fetch_ms"].median()),
        "spearman_p95_fetch": float(r["down_p95"].corr(r["fetch_ms"], method="spearman")),
        "spearman_baseline_fetch": float(r["baseline"].corr(r["fetch_ms"], method="spearman")),
        "spearman_p95_fetch_gt6": float(
            r[r["down_p95"] > 6]["down_p95"].corr(
                r[r["down_p95"] > 6]["fetch_ms"], method="spearman"
            )
        ),
        "spearman_baseline_fetch_gt6": float(
            r[(r["down_p95"] > 6) & r["baseline"].notna()]["baseline"].corr(
                r[(r["down_p95"] > 6) & r["baseline"].notna()]["fetch_ms"],
                method="spearman",
            )
        ),
    }
    with open(od / "report_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(t4p.round(3).to_string())


if __name__ == "__main__":
    main()
