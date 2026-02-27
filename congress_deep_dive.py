#!/usr/bin/env python3
"""
Congressional Trading Deep-Dive Analysis
=========================================
Takes the L1 backtest results (46,154 trades, 297 politicians) and
drills into the 20 statistically significant members (50+ trades, p<0.05).

Answers:
  1. Multiple testing correction — who survives Bonferroni & FDR?
  2. Time stability — consistent alpha or one lucky/unlucky stretch?
  3. Sector/ticker concentration — diversified edge or one bet?
  4. Trade frequency — enough signals per year to act on?
  5. Fade portfolio — aggregate short signal from negative-alpha members
  6. Size conditioning — do larger trades from good/bad traders amplify signal?
  7. Recency — is each member's alpha still active or historical?

Usage:
    python3 congress_deep_dive.py

Author: Kevin's Trading Platform
Created: 2026-02-16
"""

import os
import sys
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = os.path.expanduser(
    "~/Desktop/Claude_Programs/Trading_Programs/congress_tracker"
)
RESULTS_CSV = os.path.join(BASE_DIR, "congress_backtest_results.csv")
MEMBER_CSV = os.path.join(BASE_DIR, "congress_member_analysis_purchases_only.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "congress_deep_dive.txt")

MIN_TRADES = 50
WINDOWS = [5, 10, 20, 40, 60]
WINSORIZE_LOWER = 1
WINSORIZE_UPPER = 99


# =============================================================================
# HELPERS
# =============================================================================

def winsorize(arr, lo=1, hi=99):
    if len(arr) < 10:
        return arr
    return np.clip(arr, np.percentile(arr, lo), np.percentile(arr, hi))


def ttest(arr):
    """One-sample t-test against 0. Returns (n, mean, median, t, p)."""
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n < 10:
        return n, np.nan, np.nan, np.nan, np.nan
    w = winsorize(arr)
    mean = np.mean(w)
    median = np.median(arr)
    t, p = scipy_stats.ttest_1samp(w, 0)
    return n, mean, median, t, p


def benjamini_hochberg(p_values):
    """Return FDR-adjusted p-values using Benjamini-Hochberg method."""
    try:
        from statsmodels.stats.multitest import multipletests
        reject, fdr_p, _, _ = multipletests(p_values, alpha=0.05, method='fdr_bh')
        return fdr_p
    except ImportError:
        # Manual fallback
        n = len(p_values)
        ranked = np.argsort(p_values)
        adjusted = np.zeros(n)
        for i in range(n):
            rank = np.where(ranked == ranked[i])[0][0] + 1
            adjusted[ranked[i]] = p_values[ranked[i]] * n / rank
        sorted_idx = np.argsort(p_values)
        sorted_adj = adjusted[sorted_idx]
        for i in range(n - 2, -1, -1):
            sorted_adj[i] = min(sorted_adj[i], sorted_adj[i + 1])
        adjusted[sorted_idx] = sorted_adj
        return np.minimum(adjusted, 1.0)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("CONGRESSIONAL TRADING DEEP-DIVE")
    print("=" * 70)

    # Load data
    trades = pd.read_csv(RESULTS_CSV)
    members = pd.read_csv(MEMBER_CSV)

    trades["trade_date"] = pd.to_datetime(trades["trade_date"])
    trades["year"] = trades["trade_date"].dt.year

    print(f"  Loaded {len(trades):,} trades, {len(members)} members")

    # Significant members with 50+ trades
    sig = members[
        (members["n_trades"] >= MIN_TRADES) & (members["significant_p05"] == True)
    ].copy()

    sig_pos = sig[sig["mean_alpha_20d"] > 0].sort_values("mean_alpha_20d", ascending=False)
    sig_neg = sig[sig["mean_alpha_20d"] < 0].sort_values("mean_alpha_20d")

    print(f"  Significant (50+ trades, p<0.05): {len(sig)}")
    print(f"    Positive alpha: {len(sig_pos)}")
    print(f"    Negative alpha: {len(sig_neg)}")

    out = []
    out.append("=" * 100)
    out.append("CONGRESSIONAL TRADING DEEP-DIVE ANALYSIS")
    out.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"Total trades: {len(trades):,}  |  Total members: {len(members)}")
    out.append(f"Significant at p<0.05 (50+ trades): {len(sig)} "
               f"({len(sig_pos)} positive, {len(sig_neg)} negative)")
    out.append("=" * 100)

    # ==================================================================
    # 1. MULTIPLE TESTING CORRECTION
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  1. MULTIPLE TESTING CORRECTION")
    out.append(f"#     Testing {len(members[members['n_trades'] >= MIN_TRADES])} members "
               f"with {MIN_TRADES}+ trades")
    out.append(f"{'#'*100}")

    testable = members[members["n_trades"] >= MIN_TRADES].copy()
    testable = testable.dropna(subset=["p_val_20d"])
    n_tests = len(testable)

    raw_p = testable["p_val_20d"].values
    bonf_p = np.minimum(raw_p * n_tests, 1.0)
    fdr_p = benjamini_hochberg(raw_p)

    testable["bonferroni_p"] = bonf_p
    testable["fdr_p"] = fdr_p
    testable["survives_bonf"] = bonf_p < 0.05
    testable["survives_fdr"] = fdr_p < 0.05

    out.append(f"\n  Number of tests: {n_tests}")
    out.append(f"  Bonferroni threshold: p < {0.05/n_tests:.6f}")
    out.append(f"  Expected false positives at p<0.05: {n_tests * 0.05:.1f}")

    out.append(f"\n  Survives Bonferroni (p<0.05/{n_tests}): "
               f"{testable['survives_bonf'].sum()}")
    out.append(f"  Survives FDR (BH q<0.05): "
               f"{testable['survives_fdr'].sum()}")

    out.append(f"\n  {'Politician':<30} {'N':>5} {'Alpha20d':>9} {'Raw p':>9} "
               f"{'Bonf p':>9} {'FDR p':>9} {'Bonf?':>6} {'FDR?':>5}")
    out.append(f"  {'-'*90}")

    # Show all originally significant members
    for _, r in testable.sort_values("mean_alpha_20d", ascending=False).iterrows():
        if r["significant_p05"]:
            out.append(
                f"  {r['politician']:<30} {r['n_trades']:>5.0f} "
                f"{r['mean_alpha_20d']:>+8.2f}% "
                f"{r['p_val_20d']:>9.6f} {r['bonferroni_p']:>9.6f} "
                f"{r['fdr_p']:>9.6f} "
                f"{'YES' if r['survives_bonf'] else 'no':>6} "
                f"{'YES' if r['survives_fdr'] else 'no':>5}"
            )

    # ==================================================================
    # 2. TIME STABILITY — ROLLING ANALYSIS
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  2. TIME STABILITY — YEAR-BY-YEAR ALPHA FOR SIGNIFICANT MEMBERS")
    out.append(f"{'#'*100}")

    all_sig_names = list(sig["politician"].values)

    # Add Tuberville as borderline
    all_sig_names_plus = all_sig_names + ["Tuberville, Tommy"]

    for politician in all_sig_names_plus:
        ptrades = trades[trades["politician"] == politician].copy()
        if len(ptrades) < 10:
            continue

        overall_alpha = ptrades["alpha_20d"].dropna()
        n, mean, med, t, p = ttest(overall_alpha.values)

        is_borderline = politician == "Tuberville, Tommy"
        label = " [BORDERLINE p=0.066]" if is_borderline else ""

        out.append(f"\n  {politician}{label}")
        out.append(f"  Overall: n={n}, alpha20d={mean:+.2f}%, t={t:.2f}, p={p:.4f}")
        out.append(f"  {'Year':<6} {'N':>5} {'Mean α20d':>10} {'Med α20d':>10} "
                    f"{'t-stat':>8} {'p-val':>8} {'Win%':>6}")
        out.append(f"  {'-'*55}")

        for year in sorted(ptrades["year"].unique()):
            ydf = ptrades[ptrades["year"] == year]
            vals = ydf["alpha_20d"].dropna().values
            yn, ym, ymed, yt, yp = ttest(vals)
            if yn < 5:
                out.append(f"  {year:<6} {yn:>5}  (too few)")
                continue
            win = np.mean(vals > 0) if len(vals) > 0 else 0
            sig_mark = ""
            if yp < 0.01:
                sig_mark = " ***"
            elif yp < 0.05:
                sig_mark = " **"
            elif yp < 0.10:
                sig_mark = " *"
            out.append(
                f"  {year:<6} {yn:>5} {ym:>+9.2f}% {ymed:>+9.2f}% "
                f"{yt:>8.2f} {yp:>8.4f} {win:>5.1%}{sig_mark}"
            )

    # ==================================================================
    # 3. SECTOR/TICKER CONCENTRATION
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  3. TICKER CONCENTRATION — ARE THEY DIVERSIFIED OR ONE-TRICK?")
    out.append(f"{'#'*100}")

    for politician in all_sig_names_plus:
        ptrades = trades[trades["politician"] == politician].copy()
        if len(ptrades) < 10:
            continue

        n_tickers = ptrades["ticker"].nunique()
        n_trades = len(ptrades)
        top5 = ptrades["ticker"].value_counts().head(5)
        top5_pct = top5.sum() / n_trades

        # HHI concentration
        ticker_counts = ptrades["ticker"].value_counts()
        shares = ticker_counts / n_trades
        hhi = (shares ** 2).sum()

        out.append(f"\n  {politician}: {n_trades} trades across {n_tickers} tickers "
                    f"(HHI={hhi:.3f}, top5={top5_pct:.1%})")

        # Top 5 tickers with alpha
        out.append(f"  {'Ticker':<8} {'Trades':>7} {'%Total':>7} {'Avg α20d':>10} {'Med α20d':>10}")
        out.append(f"  {'-'*45}")
        for tick, count in top5.items():
            tick_alpha = ptrades[ptrades["ticker"] == tick]["alpha_20d"].dropna()
            if len(tick_alpha) > 0:
                out.append(
                    f"  {tick:<8} {count:>7} {count/n_trades:>6.1%} "
                    f"{np.mean(winsorize(tick_alpha.values)):>+9.2f}% "
                    f"{np.median(tick_alpha.values):>+9.2f}%"
                )
            else:
                out.append(f"  {tick:<8} {count:>7} {count/n_trades:>6.1%}  (no data)")

        # Alpha excluding top ticker
        top_tick = top5.index[0]
        excl = ptrades[ptrades["ticker"] != top_tick]["alpha_20d"].dropna().values
        if len(excl) >= 10:
            en, em, emed, et, ep = ttest(excl)
            out.append(f"  Excluding {top_tick}: n={en}, α20d={em:+.2f}%, t={et:.2f}, p={ep:.4f}")

    # ==================================================================
    # 4. TRADE FREQUENCY — SIGNALS PER YEAR
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  4. TRADE FREQUENCY — SIGNALS PER YEAR")
    out.append(f"{'#'*100}")

    out.append(f"\n  {'Politician':<30} {'Total':>6} {'Years':>6} "
               f"{'Per Yr':>7} {'Last Trade':>12} {'Still Active':>13}")
    out.append(f"  {'-'*80}")

    for politician in all_sig_names_plus:
        ptrades = trades[trades["politician"] == politician].copy()
        if len(ptrades) < 10:
            continue
        n_trades = len(ptrades)
        first = ptrades["trade_date"].min()
        last = ptrades["trade_date"].max()
        years_active = max((last - first).days / 365.25, 0.5)
        per_year = n_trades / years_active
        still_active = last >= pd.Timestamp("2025-01-01")

        out.append(
            f"  {politician:<30} {n_trades:>6} {years_active:>5.1f} "
            f"{per_year:>7.1f} {str(last.date()):>12} "
            f"{'YES' if still_active else 'no':>13}"
        )

    # ==================================================================
    # 5. SIZE CONDITIONING — DO LARGER TRADES AMPLIFY SIGNAL?
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  5. SIZE CONDITIONING — LARGER TRADES VS ALL TRADES")
    out.append(f"{'#'*100}")

    # Parse size buckets
    size_order = [
        "$1,001 - $15,000",
        "$15,001 - $50,000",
        "$50,001 - $100,000",
        "$100,001 - $250,000",
        "$250,001 - $500,000",
        "$500,001 - $1,000,000",
        "$1,000,001 - $5,000,000",
    ]
    size_threshold = "$15,001 - $50,000"  # "large" = $15K+

    for politician in all_sig_names_plus:
        ptrades = trades[trades["politician"] == politician].copy()
        if len(ptrades) < 20:
            continue

        small = ptrades[ptrades["trade_size_raw"] == "$1,001 - $15,000"]
        large = ptrades[ptrades["trade_size_raw"] != "$1,001 - $15,000"]

        out.append(f"\n  {politician}:")
        for label, subset in [("All trades", ptrades),
                              ("Small (<$15K)", small),
                              ("Large ($15K+)", large)]:
            vals = subset["alpha_20d"].dropna().values
            n, m, med, t, p = ttest(vals)
            if n < 5:
                out.append(f"    {label:<20} n={n} (too few)")
                continue
            sig_mark = ""
            if p < 0.01: sig_mark = " ***"
            elif p < 0.05: sig_mark = " **"
            elif p < 0.10: sig_mark = " *"
            out.append(
                f"    {label:<20} n={n:>5}  α20d={m:>+7.2f}%  "
                f"med={med:>+7.2f}%  t={t:>6.2f}  p={p:.4f}{sig_mark}"
            )

    # ==================================================================
    # 6. FADE PORTFOLIO — AGGREGATE SHORT SIGNAL
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  6. FADE PORTFOLIO — SHORTING NEGATIVE-ALPHA MEMBERS' PICKS")
    out.append(f"{'#'*100}")

    fade_names = list(sig_neg["politician"].values)
    # Add Tuberville
    fade_names_plus = fade_names + ["Tuberville, Tommy"]

    out.append(f"\n  Fade candidates ({len(fade_names_plus)} members):")
    for name in fade_names_plus:
        row = members[members["politician"] == name].iloc[0]
        out.append(f"    {name:<30} α20d={row['mean_alpha_20d']:>+6.2f}%")

    # Aggregate all fade trades
    fade_trades = trades[trades["politician"].isin(fade_names_plus)].copy()

    out.append(f"\n  Aggregate Fade Portfolio (short their purchases):")
    out.append(f"  Total trades: {len(fade_trades):,}")
    out.append(f"  Unique tickers: {fade_trades['ticker'].nunique()}")

    out.append(f"\n  {'Window':>8} {'N':>6} {'Avg α':>9} {'Med α':>9} "
               f"{'t-stat':>8} {'p-val':>8} {'Win%':>6}")
    out.append(f"  {'-'*55}")

    for w in WINDOWS:
        col = f"alpha_{w}d"
        vals = fade_trades[col].dropna().values
        n, m, med, t, p = ttest(vals)
        # For fading: negative alpha = profitable short
        win = np.mean(vals < 0)  # % where shorting would win
        sig_mark = ""
        if p < 0.01: sig_mark = " ***"
        elif p < 0.05: sig_mark = " **"
        elif p < 0.10: sig_mark = " *"
        out.append(
            f"  {w:>5}d {n:>6} {m:>+8.2f}% {med:>+8.2f}% "
            f"{t:>8.2f} {p:>8.4f} {win:>5.1%}{sig_mark}"
        )

    # Year-by-year fade portfolio
    out.append(f"\n  Fade Portfolio Year-by-Year (20d alpha):")
    out.append(f"  {'Year':<6} {'N':>6} {'Avg α20d':>10} {'Med α20d':>10} "
               f"{'t-stat':>8} {'ShortWin%':>10}")
    out.append(f"  {'-'*55}")

    for year in sorted(fade_trades["year"].unique()):
        ydf = fade_trades[fade_trades["year"] == year]
        vals = ydf["alpha_20d"].dropna().values
        n, m, med, t, p = ttest(vals)
        if n < 10:
            out.append(f"  {year:<6} {n:>6}  (too few)")
            continue
        short_win = np.mean(vals < 0)
        out.append(
            f"  {year:<6} {n:>6} {m:>+9.2f}% {med:>+9.2f}% {t:>8.2f} {short_win:>9.1%}"
        )

    # ==================================================================
    # 7. FOLLOW PORTFOLIO — AGGREGATE LONG SIGNAL
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  7. FOLLOW PORTFOLIO — BUYING POSITIVE-ALPHA MEMBERS' PICKS")
    out.append(f"{'#'*100}")

    follow_names = list(sig_pos["politician"].values)

    out.append(f"\n  Follow candidates ({len(follow_names)} members):")
    for name in follow_names:
        row = members[members["politician"] == name].iloc[0]
        out.append(f"    {name:<30} α20d={row['mean_alpha_20d']:>+6.2f}%")

    follow_trades = trades[trades["politician"].isin(follow_names)].copy()

    out.append(f"\n  Aggregate Follow Portfolio:")
    out.append(f"  Total trades: {len(follow_trades):,}")
    out.append(f"  Unique tickers: {follow_trades['ticker'].nunique()}")

    out.append(f"\n  {'Window':>8} {'N':>6} {'Avg α':>9} {'Med α':>9} "
               f"{'t-stat':>8} {'p-val':>8} {'Win%':>6}")
    out.append(f"  {'-'*55}")

    for w in WINDOWS:
        col = f"alpha_{w}d"
        vals = follow_trades[col].dropna().values
        n, m, med, t, p = ttest(vals)
        win = np.mean(vals > 0)
        sig_mark = ""
        if p < 0.01: sig_mark = " ***"
        elif p < 0.05: sig_mark = " **"
        elif p < 0.10: sig_mark = " *"
        out.append(
            f"  {w:>5}d {n:>6} {m:>+8.2f}% {med:>+8.2f}% "
            f"{t:>8.2f} {p:>8.4f} {win:>5.1%}{sig_mark}"
        )

    # Year-by-year follow portfolio
    out.append(f"\n  Follow Portfolio Year-by-Year (20d alpha):")
    out.append(f"  {'Year':<6} {'N':>6} {'Avg α20d':>10} {'Med α20d':>10} "
               f"{'t-stat':>8} {'Win%':>7}")
    out.append(f"  {'-'*50}")

    for year in sorted(follow_trades["year"].unique()):
        ydf = follow_trades[follow_trades["year"] == year]
        vals = ydf["alpha_20d"].dropna().values
        n, m, med, t, p = ttest(vals)
        if n < 10:
            out.append(f"  {year:<6} {n:>6}  (too few)")
            continue
        win = np.mean(vals > 0)
        out.append(
            f"  {year:<6} {n:>6} {m:>+9.2f}% {med:>+9.2f}% {t:>8.2f} {win:>6.1%}"
        )

    # ==================================================================
    # 8. CLUSTER × MEMBER QUALITY INTERACTION
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  8. CLUSTER INTERACTION — DO GOOD/BAD TRADERS IN CLUSTERS AMPLIFY?")
    out.append(f"{'#'*100}")

    # Mark trades by member quality
    all_sig_set = set(sig["politician"].values)
    pos_set = set(sig_pos["politician"].values)
    neg_set = set(sig_neg["politician"].values)

    trades["member_type"] = "neutral"
    trades.loc[trades["politician"].isin(pos_set), "member_type"] = "positive_sig"
    trades.loc[trades["politician"].isin(neg_set), "member_type"] = "negative_sig"

    # Check if each trade is part of a cluster (same ticker within 14 days)
    trades_sorted = trades.sort_values(["ticker", "trade_date"])
    trades["in_cluster"] = False

    for ticker, grp in trades_sorted.groupby("ticker"):
        dates = grp["trade_date"].values
        politicians = grp["politician"].values
        indices = grp.index.values

        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                diff = (dates[j] - dates[i]) / np.timedelta64(1, "D")
                if diff > 14:
                    break
                if politicians[i] != politicians[j]:
                    trades.loc[indices[i], "in_cluster"] = True
                    trades.loc[indices[j], "in_cluster"] = True

    out.append(f"\n  {'Type':<20} {'Cluster':>8} {'N':>6} "
               f"{'Avg α20d':>10} {'Med α20d':>10} {'t-stat':>8} {'p-val':>8}")
    out.append(f"  {'-'*70}")

    for mtype in ["positive_sig", "negative_sig", "neutral"]:
        for cluster in [True, False]:
            mask = (trades["member_type"] == mtype) & (trades["in_cluster"] == cluster)
            subset = trades[mask]
            vals = subset["alpha_20d"].dropna().values
            n, m, med, t, p = ttest(vals)
            cluster_label = "YES" if cluster else "no"
            if n < 20:
                out.append(f"  {mtype:<20} {cluster_label:>8} {n:>6} (too few)")
                continue
            sig_mark = ""
            if p < 0.01: sig_mark = " ***"
            elif p < 0.05: sig_mark = " **"
            elif p < 0.10: sig_mark = " *"
            out.append(
                f"  {mtype:<20} {cluster_label:>8} {n:>6} "
                f"{m:>+9.2f}% {med:>+9.2f}% {t:>8.2f} {p:>8.4f}{sig_mark}"
            )

    # ==================================================================
    # 9. ACTIVE TRADEABLE MEMBERS SUMMARY
    # ==================================================================
    out.append(f"\n\n{'#'*100}")
    out.append(f"#  9. ACTIONABLE SUMMARY — WHO TO FOLLOW, WHO TO FADE")
    out.append(f"{'#'*100}")

    out.append(f"\n  Criteria for actionable signal:")
    out.append(f"    - Survives FDR correction OR has 200+ trades with p<0.02")
    out.append(f"    - Still active (traded in 2025+)")
    out.append(f"    - 20+ trades per year")
    out.append(f"    - Alpha consistent across 2+ time periods")

    # Build actionable table
    out.append(f"\n  {'Politician':<30} {'Action':>6} {'N':>5} {'α20d':>7} "
               f"{'t':>6} {'RawP':>8} {'FDR_P':>8} {'Active':>7} "
               f"{'Trd/Yr':>7} {'Verdict':>12}")
    out.append(f"  {'-'*105}")

    for politician in all_sig_names_plus:
        ptrades = trades[trades["politician"] == politician]
        n_trades = len(ptrades)
        if n_trades < 10:
            continue

        last_trade = ptrades["trade_date"].max()
        first_trade = ptrades["trade_date"].min()
        years_active = max((last_trade - first_trade).days / 365.25, 0.5)
        per_year = n_trades / years_active
        still_active = last_trade >= pd.Timestamp("2025-01-01")

        # Get stats
        m_row = members[members["politician"] == politician]
        if len(m_row) == 0:
            continue
        m_row = m_row.iloc[0]

        t_row = testable[testable["politician"] == politician]
        fdr = t_row.iloc[0]["fdr_p"] if len(t_row) > 0 else 1.0
        raw_p = m_row["p_val_20d"] if pd.notna(m_row["p_val_20d"]) else 1.0

        alpha = m_row["mean_alpha_20d"]
        action = "FOLLOW" if alpha > 0 else "FADE"

        # Verdict logic
        if pd.isna(fdr):
            fdr = 1.0
        survives_fdr = fdr < 0.05
        strong_p = raw_p < 0.02 and n_trades >= 200

        if (survives_fdr or strong_p) and still_active and per_year >= 15:
            verdict = "TRADEABLE"
        elif (survives_fdr or strong_p) and still_active:
            verdict = "MONITOR"
        elif survives_fdr or strong_p:
            verdict = "INACTIVE"
        else:
            verdict = "WEAK"

        out.append(
            f"  {politician:<30} {action:>6} {n_trades:>5} "
            f"{alpha:>+6.2f}% {m_row['t_stat_20d']:>6.2f} "
            f"{raw_p:>8.4f} {fdr:>8.4f} "
            f"{'YES' if still_active else 'no':>7} "
            f"{per_year:>6.1f} {verdict:>12}"
        )

    # ==================================================================
    # OUTPUT
    # ==================================================================
    output_text = "\n".join(out)
    with open(OUTPUT_PATH, "w") as f:
        f.write(output_text)

    print(f"\nFull report: {OUTPUT_PATH}")
    print("\nDone.")


if __name__ == "__main__":
    main()
