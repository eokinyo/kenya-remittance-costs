#!/usr/bin/env python3
"""
What it costs to send money to Kenya.

Reproduces the numbers and the two charts in the article "The 1% US tax is not the
biggest cost of sending money to Kenya" (Elly Okinyo, 3 October 2026).

Three steps, run in order by main():
  1. download  - fetch the two source files (cached outside the project folder, see DATA_DIR)
  2. analyse   - corridor averages, USA payment-instrument split, Tanzania detail,
                 global average, CBK Tanzania vs Saudi Arabia (CSVs in outputs/)
  3. charts    - two PNG charts (outputs/charts/)

Sources (downloaded at run time; nothing is committed to the repo):
  * World Bank, Remittance Prices Worldwide (RPW), complete dataset 2011 to Q3 2025
  * Central Bank of Kenya (CBK), "Remittances by Source ('000 USD Equivalent)", Aug 2026

Run:  python remittance_costs.py            (add --refresh to download again)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # no GUI needed; works on Windows/macOS/Linux/headless
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# The URLs are pinned to the releases used in the article, so the numbers do not change
# when a newer round comes out. To update, change the URL (and the CBK month below).
RPW_URL = ("https://datacatalogfiles.worldbank.org/ddh-published/0037898/DR0095523/"
           "rpw_dataset_2011_2025_q3.xlsx")
RPW_PAGE = "https://datacatalog.worldbank.org/search/dataset/0037898/remittance-prices-worldwide"
RPW_SHEET = "Dataset (from Q2 2016)"

CBK_URL = "https://www.centralbank.go.ke/wp-content/uploads/2026/09/August2026.xlsx"
CBK_PAGE = "https://www.centralbank.go.ke/diaspora-remittances/"
CBK_YEAR, CBK_MONTH = 2026, "Aug"

# Reference values that are not in the dataset.
SDG_TARGET = 3.0     # UN SDG 10.c / G20 target for the global average cost by 2030 (%)
TAX_PCT = 1.0        # US remittance transfer tax on cash-funded transfers since 1 Jan 2026
                     # (26 U.S.C. 4475)
# Published in the RPW Q3 2025 report (Issue 54, September 2025, p. 6 and Annex Table 1):
# https://datacatalogfiles.worldbank.org/ddh-published/0037898/DR0095413/RPW_main_report_and_annex_Q325.pdf
GLOBAL_AVG_REPORT = 6.36   # global average, Q3 2025 (the script also derives it from the data)
SSA_AVG_REPORT = 8.46      # Sub-Saharan Africa (as destination) average, Q3 2025

AMOUNT_USD = 200     # RPW prices the equivalent of US$200 ("cc1" columns)
DEST = "KEN"
CORRIDORS = {  # source_code: (label, colour)
    "USA": ("USA", "#1f77b4"), "GBR": ("UK", "#2ca02c"), "CAN": ("Canada", "#d62728"),
    "TZA": ("Tanzania", "#ff7f0e"), "RWA": ("Rwanda", "#9467bd"), "ZAF": ("South Africa", "#7f7f7f"),
}
INSTRUMENT_LABELS = {"Bank account transfer": "Bank account"}
SOURCE_NOTE = "Source: World Bank, Remittance Prices Worldwide; author's calculations."

BASE_DIR = Path(__file__).resolve().parent
PROJECT = "kenya-remittance-costs"


def _data_dir() -> Path:
    """Download cache, kept outside the project folder (so a synced project folder stays small).

    KRC_DATA_DIR overrides it. Default: %LOCALAPPDATA%\\project-data\\<project> on Windows,
    ~/.cache/project-data/<project> elsewhere. clean.ps1 deletes it after a run.
    """
    if os.environ.get("KRC_DATA_DIR"):
        return Path(os.environ["KRC_DATA_DIR"])
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "project-data" / PROJECT


DATA_DIR = _data_dir()
RAW_DIR = DATA_DIR / "raw"
OUT_DIR = BASE_DIR / "outputs"
CHART_DIR = OUT_DIR / "charts"

TIMEOUT = 120  # seconds
RETRIES = 3
USER_AGENT = "kenya-remittance-costs/1.0 (+python-requests)"


# --------------------------------------------------------------------------- #
# Step 1: download
# --------------------------------------------------------------------------- #
def download(url: str, page: str, refresh: bool) -> Path:
    """Download an Excel file into RAW_DIR (or reuse the cached copy)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / url.rsplit("/", 1)[-1]
    if path.exists() and not refresh:
        print(f"Using cached {path.name}")
        return path
    err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            if r.content[:4] != b"PK\x03\x04":
                raise ValueError("the response is not an Excel file")
            path.write_bytes(r.content)
            print(f"Downloaded {path.name} ({len(r.content) / 1e6:.1f} MB)")
            return path
        except (requests.RequestException, ValueError) as e:
            err = e
            time.sleep(2 * attempt)
    sys.exit(f"Could not download {url} ({err}).\n"
             f"Open {page} in a browser, save the file as {path} and run again.")


# --------------------------------------------------------------------------- #
# Step 2: analyse
# --------------------------------------------------------------------------- #
def load_rpw(xlsx: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (all services in the latest round, Kenya services in every round).

    Only transparent services are kept (the World Bank lists non-transparent
    services separately and leaves them out of its averages). The large Excel sheet
    is read once and cached as two small CSVs next to it.
    """
    ken_csv = RAW_DIR / f"{xlsx.stem}_kenya.csv"
    last_csv = RAW_DIR / f"{xlsx.stem}_latest_round.csv"
    if not (ken_csv.exists() and last_csv.exists()
            and ken_csv.stat().st_mtime >= xlsx.stat().st_mtime):
        print(f"Reading sheet '{RPW_SHEET}' (large file, about a minute)...")
        df = pd.read_excel(xlsx, sheet_name=RPW_SHEET)
        df[df["destination_code"] == DEST].to_csv(ken_csv, index=False)
        df[df["period"] == df["period"].max()].to_csv(last_csv, index=False)
    out = []
    for f in (last_csv, ken_csv):
        df = pd.read_csv(f)
        df["cost"] = pd.to_numeric(df["cc1 total cost %"], errors="coerce")
        keep = df["transparent"].astype(str).str.strip().str.lower().eq("yes") & df["cost"].notna()
        df = df[keep].copy()
        df["quarter"] = pd.PeriodIndex(  # "2025_3Q" -> 2025Q3
            df["period"].str.replace(r"(\d{4})_(\d)Q", r"\1Q\2", regex=True), freq="Q")
        out.append(df)
    return out[0], out[1]


def corridor_table(ken: pd.DataFrame) -> pd.DataFrame:
    """Simple mean / median / count of total cost by quarter and sending country."""
    g = ken.groupby(["quarter", "source_code"])["cost"]
    t = pd.DataFrame({"mean": g.mean(), "median": g.median(), "n": g.size()}).reset_index()
    return t.sort_values(["source_code", "quarter"])


def cbk_month(xlsx: Path, year: int, month: str) -> dict[str, float]:
    """Values (USD millions) for every row of the CBK 'Remittances by Source' file in one month."""
    raw = pd.read_excel(xlsx, header=None)
    hdr = next(i for i in range(10) if raw.iloc[i].astype(str).str.strip().eq("Region/Country").any())
    name_col = raw.columns[raw.iloc[hdr].astype(str).str.strip().eq("Region/Country")][0]
    years = pd.to_numeric(raw.iloc[hdr - 1], errors="coerce").ffill()
    months = raw.iloc[hdr].astype(str).str.strip().str[:3].str.lower()
    cols = [c for c in raw.columns if years[c] == year and months[c] == month[:3].lower()]
    if not cols:
        sys.exit(f"{month} {year} not found in {xlsx.name}.")
    vals = {}
    for _, row in raw.iloc[hdr + 1:].iterrows():
        name, v = str(row[name_col]).strip(), pd.to_numeric(row[cols[0]], errors="coerce")
        if name and pd.notna(v) and name not in vals:
            vals[name] = v / 1000.0  # USD '000 -> USD millions
    return vals


def analyse(rpw_xlsx: Path, cbk_xlsx: Path) -> dict:
    latest_all, ken = load_rpw(rpw_xlsx)
    table = corridor_table(ken)
    latest = ken["quarter"].max()
    lq = ken[ken["quarter"] == latest]
    us = lq[lq["source_code"] == "USA"]
    tz = lq[lq["source_code"] == "TZA"]
    cash = us["payment instrument"].str.strip().str.lower().eq("cash")

    r = {"table": table, "latest": latest, "lq": lq, "us": us,
         "qlabel": f"Q{latest.quarter} {latest.year}",
         "dates": pd.to_datetime(lq["date"], errors="coerce").agg(["min", "max"]),
         "by_instrument": us.groupby("payment instrument")["cost"].agg(["mean", "size"]),
         "by_pickup": us.groupby("pickup method")["cost"].agg(["mean", "size"]),
         "cash": us.loc[cash, "cost"].agg(["mean", "size"]),
         "noncash": us.loc[~cash, "cost"].agg(["mean", "size"]),
         "tz_banks": tz[tz["firm_type"] == "Bank"],
         "tz_other": tz[tz["firm_type"] != "Bank"].sort_values("cost", ascending=False),
         "global_avg": latest_all["cost"].mean(),  # RPW global average = mean of all services
         "ssa_avg": latest_all.loc[latest_all["destination_region"] == "Sub-Saharan Africa",
                                   "cost"].mean()}
    r["cash_usd"] = r["cash"]["mean"] / 100 * AMOUNT_USD
    r["noncash_usd"] = r["noncash"]["mean"] / 100 * AMOUNT_USD
    r["tax_usd"] = TAX_PCT / 100 * AMOUNT_USD
    r["gap_usd"] = r["cash_usd"] - r["noncash_usd"]

    cbk = cbk_month(cbk_xlsx, CBK_YEAR, CBK_MONTH)
    pick = lambda prefix: next((k, v) for k, v in cbk.items() if k.lower().startswith(prefix))
    r["cbk"] = {"Tanzania": pick("tanzania"), "Saudi Arabia": pick("saudi"),
                "Grand total": pick("grand total")}

    OUT_DIR.mkdir(exist_ok=True)
    table.assign(quarter=table["quarter"].astype(str)).to_csv(
        OUT_DIR / "kenya_corridor_costs.csv", index=False, float_format="%.2f")
    r["by_instrument"].to_csv(OUT_DIR / f"usa_kenya_by_instrument_{latest}.csv", float_format="%.2f")
    return r


def report(r: dict):
    t, latest, q = r["table"], r["latest"], r["qlabel"]
    print(f"\n=== World Bank RPW, latest round {q} "
          f"(prices collected {r['dates']['min']:%d %b %Y} to {r['dates']['max']:%d %b %Y}) ===")
    print(f"Global average, all corridors: {r['global_avg']:.2f}% from the data "
          f"(report: {GLOBAL_AVG_REPORT:.2f}%)")
    print(f"Sub-Saharan Africa average:    {r['ssa_avg']:.2f}% from the data "
          f"(report: {SSA_AVG_REPORT:.2f}%)")
    print(f"\nCorridor averages to Kenya, {q} (simple mean of transparent services, % of US$200):")
    for c, row in t[t["quarter"] == latest].set_index("source_code").iterrows():
        print(f"  {CORRIDORS.get(c, (c,))[0]:<13} {row['mean']:6.2f}%  median {row['median']:6.2f}%"
              f"  n={int(row['n'])}")
    print("\nChange since each corridor's first quarter in the sheet:")
    for c in CORRIDORS:
        s = t[t["source_code"] == c].set_index("quarter")["mean"]
        if len(s):
            print(f"  {CORRIDORS[c][0]:<13} {s.index[0]} {s.iloc[0]:6.2f}%  ->  "
                  f"{s.index[-1]} {s.iloc[-1]:6.2f}%")
    for title, tbl in (("payment instrument", r["by_instrument"]), ("receiving method", r["by_pickup"])):
        print(f"\nUSA -> Kenya by {title}:")
        for name, row in tbl.iterrows():
            print(f"  {name:<22} {row['mean']:6.2f}%  n={int(row['size'])}")
    print(f"\nCash-funded {r['cash']['mean']:.2f}% (n={int(r['cash']['size'])}); "
          f"bank- or card-funded {r['noncash']['mean']:.2f}% (n={int(r['noncash']['size'])})")
    print(f"On US${AMOUNT_USD}: cash US${r['cash_usd']:.2f}, bank/card US${r['noncash_usd']:.2f}, "
          f"gap US${r['gap_usd']:.2f} = {r['gap_usd'] / r['tax_usd']:.1f} times the "
          f"US${r['tax_usd']:.0f} tax")
    b, o = r["tz_banks"], r["tz_other"]
    print(f"\nTanzania -> Kenya ({b['cc1 lcu code'].iloc[0]} {b['cc1 lcu amount'].iloc[0]:,.0f}): "
          f"{len(b)} bank transfers cost {b['cost'].min():.2f}% to {b['cost'].max():.2f}% "
          f"(fees {b['cc1 lcu fee'].min():,.0f} to {b['cc1 lcu fee'].max():,.0f}; "
          f"FX margins {b['cc1 fx margin'].min():.2f}% to {b['cc1 fx margin'].max():.2f}%)")
    print("  Others: " + "; ".join(f"{f} {c:.2f}%" for f, c in o[["firm", "cost"]].values))
    print(f"\n=== CBK Remittances by Source, {CBK_MONTH} {CBK_YEAR} (USD millions) ===")
    for label, (row, v) in r["cbk"].items():
        print(f"  {label:<13} {v:8.2f}   (row '{row}')")


# --------------------------------------------------------------------------- #
# Step 3: charts (same style as kenya-remittances-2026)
# --------------------------------------------------------------------------- #
def style():
    plt.rcParams.update({
        "figure.dpi": 100, "savefig.dpi": 300, "font.size": 10.5,
        "font.family": "DejaVu Sans", "axes.titlesize": 13, "axes.titleweight": "bold",
        "axes.labelsize": 10.5, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.6,
        "legend.frameon": False, "legend.fontsize": 9.5})


def finish(fig, ax, path: Path, offset: int = -30):
    ax.annotate(SOURCE_NOTE, xy=(0, 0), xycoords="axes fraction", xytext=(-40, offset),
                textcoords="offset points", ha="left", va="top", fontsize=8, color="#555555")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_funding(r: dict, path: Path):
    t = r["by_instrument"].sort_values("mean")
    us_avg, global_avg = r["us"]["cost"].mean(), r["global_avg"]
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.grid(axis="y", visible=False)
    ys = range(len(t))
    ax.barh(ys, t["mean"], height=0.6, zorder=2,
            color=["#c0392b" if i == "Cash" else "#1f77b4" for i in t.index])
    for y, (inst, row) in zip(ys, t.iterrows()):
        if inst == "Cash":
            ax.barh(y, TAX_PCT, left=row["mean"], height=0.6, color="white", edgecolor="#c0392b",
                    hatch="////", lw=0.8, zorder=2)
            ax.annotate("+1% US tax since 1 Jan 2026\n(cash-funded transfers only)",
                        xy=(row["mean"] + TAX_PCT, y), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=8, color="#444444")
        ax.annotate(f"{row['mean']:.2f}%  (n={int(row['size'])})", xy=(0, y), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color="white",
                    fontweight="bold", zorder=3)
    ax.set_yticks(list(ys), [INSTRUMENT_LABELS.get(i, i) for i in t.index])
    for x, ls, txt in [
            (us_avg, "--", f"USA-Kenya average, all services ({us_avg:.2f}%)"),
            (global_avg, "-.", f"Global average, all corridors ({global_avg:.2f}%, {r['qlabel']})"),
            (SDG_TARGET, ":", f"UN/G20 target for the global average by 2030 ({SDG_TARGET:.0f}%)")]:
        ax.axvline(x, color="#333333", ls=ls, lw=1.0, zorder=1, label=txt)
    ax.legend(loc="lower right")
    ax.set_xlim(0, 12)
    ax.set_xlabel("Total cost of sending US$200, % of amount sent (fee + exchange-rate margin)")
    ax.set_title(f"Kenya: cost of sending US$200 from the USA, by how the sender pays "
                 f"({r['qlabel']})", loc="left")
    finish(fig, ax, path, offset=-42)


def chart_corridors(table: pd.DataFrame, path: Path):
    full = pd.period_range(table["quarter"].min(), table["quarter"].max(), freq="Q")
    wide = table.pivot(index="quarter", columns="source_code", values="mean").reindex(full)
    x = wide.index.to_timestamp(how="start") + pd.Timedelta(days=45)  # mid-quarter
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1], "hspace": 0.22})
    for ax, codes, top in [(ax1, ["USA", "GBR", "CAN"], 12), (ax2, ["TZA", "RWA", "ZAF"], 70)]:
        for c in codes:
            if c not in wide:
                continue
            lab, col = CORRIDORS[c]
            s = pd.Series(wide[c].values, index=x)
            ok = s.dropna()
            ax.plot(s.index, s.values, color=col, lw=2.0, label=lab)
            # Bridge quarters with no survey round (e.g. Q2 2025) with a dotted line.
            ax.plot(ok.index, ok.values, color=col, lw=1.2, ls=":", zorder=1)
            ax.plot(ok.index[-1:], ok.values[-1:], "o", color=col, ms=4.5)
            ax.annotate(f"{ok.values[-1]:.2f}%", xy=(ok.index[-1], ok.values[-1]), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=8.5, color=col,
                        fontweight="bold")
        ax.axhline(SDG_TARGET, color="#333333", ls="--", lw=0.9, zorder=1)
        ax.set_ylim(0, top)
        ax.set_ylabel("% of US$200")
        ax.legend(loc="upper left", ncol=3)
    ax1.annotate("3% target for the global average (UN/G20, 2030)", xy=(0, SDG_TARGET),
                 xycoords=("axes fraction", "data"), xytext=(4, 3), textcoords="offset points",
                 ha="left", va="bottom", fontsize=8, color="#444444")
    ax1.set_title("Kenya: cost of sending US$200, by sending country", loc="left")
    ax2.set_title("Regional corridors (different scale)", loc="left", fontsize=11.5)
    ax2.annotate("Dotted segments: no survey round that quarter (e.g. Q2 2025). Dots: latest round.",
                 xy=(1, 1), xycoords="axes fraction", xytext=(0, 4), textcoords="offset points",
                 ha="right", va="bottom", fontsize=8, color="#444444")
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    finish(fig, ax2, path)


def charts(r: dict):
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    style()
    chart_funding(r, CHART_DIR / "1_usa_kenya_cost_by_funding.png")
    chart_corridors(r["table"], CHART_DIR / "2_kenya_corridor_costs.png")
    print(f"\nCharts and CSVs written to {OUT_DIR}")


# --------------------------------------------------------------------------- #
def main():
    refresh = "--refresh" in sys.argv
    rpw_xlsx = download(RPW_URL, RPW_PAGE, refresh)
    cbk_xlsx = download(CBK_URL, CBK_PAGE, refresh)
    results = analyse(rpw_xlsx, cbk_xlsx)
    report(results)
    charts(results)


if __name__ == "__main__":
    main()
