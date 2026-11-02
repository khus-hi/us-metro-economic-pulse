"""One-page monthly insight memo (analysis/output/memo.md).

Written for two readers: regional economic development offices and analyst
job seekers. Every number is computed below from the marts and analysis
outputs; the wording around each number is chosen by rules (e.g. "rose" vs
"fell" by sign), so the memo can be regenerated every month unattended.
"""
from __future__ import annotations

import pandas as pd


def _names(df, names, n):
    return ", ".join(f"{names.get(c, c)} ({v:+.2f})" for c, v in df.head(n).itertuples(index=False))


def _dir(x: float, up: str = "up", down: str = "down") -> str:
    return up if x > 0 else down if x < 0 else "flat"


def build(pulse: pd.DataFrame, now: pd.DataFrame, cv: pd.DataFrame, pay: pd.DataFrame,
          postings: pd.DataFrame, tools: pd.DataFrame, dim: pd.DataFrame,
          fcfg: dict, pcfg: dict) -> str:
    names = dim.set_index("cbsa_code")["short_name"].str.strip().to_dict()
    n_acc = pcfg.get("acceleration_months", 3)
    latest = pulse.dropna(subset=["pulse"])["month_date"].max()
    L = pulse[pulse["month_date"] == latest]
    P = pulse[pulse["month_date"] == latest - pd.DateOffset(months=n_acc)]
    ranked = L.sort_values("pulse", ascending=False)

    jg, jg_prev = L["nonfarm_jobs_yoy_pct"].median(), P["nonfarm_jobs_yoy_pct"].median()
    u_up = int((L["unemployment_change_yoy_pp"] > 0).sum())
    u_down = int((L["unemployment_change_yoy_pp"] < 0).sum())
    rw = L["real_wage_growth_pp"].median()
    rw_neg = int((L["real_wage_growth_pp"] < 0).sum())
    rw_n = int(L["real_wage_growth_pp"].notna().sum())

    acc = L[["cbsa_code", f"pulse_change_{n_acc}m"]].dropna().sort_values(f"pulse_change_{n_acc}m", ascending=False)
    dec = acc.sort_values(f"pulse_change_{n_acc}m")

    focus = fcfg["focus_metro"]
    fr = L[L["cbsa_code"] == focus].iloc[0]
    group = L[L["cbsa_code"].isin([focus, *fcfg["peers"]])].sort_values("pulse", ascending=False)
    f_place = int((group["cbsa_code"] == focus).values.nonzero()[0][0]) + 1

    soc = fcfg.get("pay_soc", "15-2051")
    sp = pay[pay["soc_code"] == soc].dropna(subset=["median_wage_cost_adjusted"]).copy()
    sp = sp.sort_values("median_wage_cost_adjusted", ascending=False)
    occ = sp["occupation_title"].iloc[0] if len(sp) else soc

    post = postings.drop_duplicates("job_key")
    open_now = post[post["is_open"].astype(str).str.lower() == "true"]
    n_open = len(open_now)
    in_metro = postings[(postings["is_open"].astype(str).str.lower() == "true") & postings["cbsa_code"].notna()]
    n_in_metro = in_metro["job_key"].nunique()
    top_post = in_metro.groupby("cbsa_code")["job_key"].nunique().sort_values(ascending=False).head(3)
    t_open = tools[tools["is_open"].astype(str).str.lower() == "true"].drop_duplicates(["job_key", "tool"])
    tool_share = (t_open.groupby("tool")["job_key"].nunique() / n_open * 100).sort_values(ascending=False).head(4)

    o = cv[cv["fold"] == "all folds"].iloc[0]
    rise = now.sort_values("nowcast_yoy_pp", ascending=False).head(3)
    tm = now["target_month"].max()

    lines = [
        f"# US Metro Economic Pulse: {latest:%B %Y}",
        "",
        f"*Top 50 US metros. Data through {latest:%B %Y} (BLS); analyst pay OEWS May "
        f"{int(pay['oews_year'].max())}; cost of living BEA RPP {int(pay['rpp_year'].max())}. "
        "For economic development offices and analyst job seekers.*",
        "",
        "## Headline",
        f"- **Hiring is {_dir(jg - jg_prev, 'picking up', 'cooling')}.** The median metro added "
        f"{jg:.2f}% more jobs than a year earlier, vs {jg_prev:.2f}% {n_acc} months ago.",
        f"- **Unemployment is higher than a year ago in {u_up} of 50 metros** and lower in {u_down}.",
        f"- **Real wages:** median growth {rw:+.2f} pp after local inflation; "
        f"real hourly earnings fell in {rw_neg} of {rw_n} metros.",
        "",
        "## Where momentum is",
        f"- **Strongest pulse:** {_names(ranked[['cbsa_code', 'pulse']], names, 3)}.",
        f"- **Weakest pulse:** {_names(ranked[['cbsa_code', 'pulse']].iloc[::-1], names, 3)}.",
        f"- **Gaining fastest ({n_acc} months):** {_names(acc, names, 3)}.",
        f"- **Losing ground fastest:** {_names(dec, names, 3)}.",
        "",
        f"## {names.get(focus, focus)} vs peers",
        f"- Pulse {fr['pulse']:+.2f}, #{fr['pulse_rank']:.0f} of 50 and #{f_place} of {len(group)} among peers "
        f"({', '.join(names.get(c, c) for c in fcfg['peers'])}).",
        f"- Job growth {fr['nonfarm_jobs_yoy_pct']:.2f}% YoY; unemployment {fr['unemployment_rate']:.1f}% "
        f"({fr['unemployment_change_yoy_pp']:+.1f} pp YoY); real wage growth {fr['real_wage_growth_pp']:+.2f} pp.",
        "",
        "## For analyst job seekers",
    ]
    if len(sp):
        top3 = "; ".join(f"{names.get(r.cbsa_code, r.cbsa_code)} ${r.median_wage_cost_adjusted:,.0f} "
                         f"(${r.annual_median_wage:,.0f} nominal)" for r in sp.head(3).itertuples())
        lines.append(f"- **{occ} pay after cost of living:** {top3}.")
        fp = sp[sp["cbsa_code"] == focus]
        if len(fp):
            fp = fp.iloc[0]
            rank = int((sp["median_wage_cost_adjusted"] > fp["median_wage_cost_adjusted"]).sum()) + 1
            lines.append(f"- {names.get(focus, focus)}: ${fp['annual_median_wage']:,.0f} median, "
                         f"${fp['median_wage_cost_adjusted']:,.0f} after cost of living (#{rank} of {len(sp)}).")
    lines += [
        f"- **Open analyst postings:** {n_open} across {post['company'].nunique()} companies' job boards, "
        f"{n_in_metro} of them in a top-50 metro. Most: "
        + ", ".join(f"{names.get(c, c)} ({v})" for c, v in top_post.items())
        + " (a posting listed in several metros counts in each).",
        "- **Most-requested tools:** " + ", ".join(f"{t} {v:.0f}%" for t, v in tool_share.items()) + " of postings.",
        "",
        f"## Watchlist: unemployment nowcast for {tm:%B %Y}",
        "- Largest expected year-over-year rises: "
        + ", ".join(f"{names.get(r.cbsa_code, r.cbsa_code)} {r.nowcast:.1f}% ({r.nowcast_yoy_pp:+.1f} pp)"
                    for r in rise.itertuples()) + ".",
        f"- Backtest accuracy (MAPE): model {o['mape_model']:.2f}%, seasonal naive {o['mape_seasonal_naive']:.2f}%, "
        f"last value {o['mape_naive_last']:.2f}%. Treat as a watchlist, not a forecast of record.",
        "",
        "## Data notes",
        "- Pulse = weighted z-scores of job growth, unemployment change, real wage growth and openings, "
        "relative to the other 49 metros (0 = average).",
    ]
    if pcfg.get("openings_source") == "jolts_state":
        om = L["openings_month"].max()
        lines.append(f"- Openings are state-level JOLTS, last published for {om:%B %Y}; metros in one state share it."
                     if pd.notna(om) else "- No state JOLTS within 12 months; openings excluded this month.")
    lines += [
        "- 29 metros use Census-division CPI (BLS publishes metro CPI for 21 of the 50).",
        "- BLS published no October 2025 metro data (federal shutdown).",
        "- Postings come from public Greenhouse/Lever boards of the companies in seeds/companies.csv, not the whole market.",
    ]
    return "\n".join(lines) + "\n"
