#!/usr/bin/env python3
import os, json, math, argparse
from pathlib import Path
from datetime import datetime, timezone
import requests
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge

ROOT = Path(__file__).resolve().parents[1]
EPL_CSV = ROOT / "model_data/epl_master_2016_2026.csv"
CHAMP_CSV = ROOT / "model_data/championship_master_2016_2026.csv"
OUT = ROOT / "docs/data/predictions.json"

HALF_LIFE_DAYS = 365.0
TEMPERATURE = 1.162
MAX_HISTORY = 30

ALIASES = {
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Manchester Utd": "Man United",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nottingham",
    "Nott'm Forest": "Nottingham",
    "Tottenham Hotspur": "Tottenham",
    "Brighton & Hove Albion": "Brighton",
    "Brighton Hove Albion": "Brighton",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    "Leicester City": "Leicester",
    "Ipswich Town": "Ipswich",
    "Hull City": "Hull",
    "Hull City AFC": "Hull",
    "Coventry City": "Coventry",
    "Leeds United": "Leeds",
    "Sunderland AFC": "Sunderland",
    "Sunderland": "Sunderland",
    "AFC Bournemouth": "Bournemouth",
    "Bournemouth AFC": "Bournemouth",
    "Crystal Palace FC": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Liverpool FC": "Liverpool",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Brentford FC": "Brentford",
    "Aston Villa FC": "Aston Villa",
}

FEATURES = [
    "H_ppg","H_gf","H_ga","H_shots","H_sot",
    "A_ppg","A_gf","A_ga","A_shots","A_sot",
    "HH_ppg","HH_gf","HH_ga",
    "AA_ppg","AA_gf","AA_ga",
]

GROUPS = {
    "Home overall form": ["H_ppg","H_gf","H_ga"],
    "Home chance creation": ["H_shots","H_sot"],
    "Home venue form": ["HH_ppg","HH_gf","HH_ga"],
    "Away overall form": ["A_ppg","A_gf","A_ga"],
    "Away chance creation": ["A_shots","A_sot"],
    "Away venue form": ["AA_ppg","AA_gf","AA_ga"],
}

def canonical(name):
    name = str(name).strip()
    if name.endswith(" FC"):
        name = name[:-3].strip()
    return ALIASES.get(name, name)

def parse_date_col(s):
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def season_sort_key(s):
    return int(str(s).split("/")[0])

def load_historical():
    epl = pd.read_csv(EPL_CSV)
    champ = pd.read_csv(CHAMP_CSV)
    epl["Date"] = parse_date_col(epl["Date"])
    champ["Date"] = parse_date_col(champ["Date"])
    for c in ["HomeTeam","AwayTeam"]:
        epl[c] = epl[c].map(canonical)
        champ[c] = champ[c].map(canonical)
    return epl.sort_values("Date"), champ.sort_values("Date")

def pts(gf, ga):
    return 3 if gf > ga else 1 if gf == ga else 0

def append_record(store, team, date, venue, gf, ga, shots=np.nan, sot=np.nan):
    store.setdefault(team, []).append({
        "date": pd.Timestamp(date), "venue": venue, "pts": pts(gf, ga),
        "gf": float(gf), "ga": float(ga),
        "shots": float(shots) if pd.notna(shots) else np.nan,
        "sot": float(sot) if pd.notna(sot) else np.nan,
    })

def weighted_stats(records, date, venue=None, maxn=MAX_HISTORY):
    rr = [x for x in records if venue is None or x["venue"] == venue][-maxn:]
    if not rr:
        return {}
    ages = np.array([(pd.Timestamp(date) - x["date"]).days for x in rr], dtype=float)
    w = np.exp(-np.log(2) * ages / HALF_LIFE_DAYS)
    out = {}
    for outkey, key in [("ppg","pts"),("gf","gf"),("ga","ga"),("shots","shots"),("sot","sot")]:
        vals = np.array([x[key] for x in rr], dtype=float)
        ok = ~np.isnan(vals)
        out[outkey] = float(np.sum(w[ok] * vals[ok]) / w[ok].sum()) if ok.any() else np.nan
    return out

def historical_feature_table(epl):
    hist, rows = {}, []
    for _, r in epl.sort_values("Date").iterrows():
        h, a, d = r.HomeTeam, r.AwayTeam, r.Date
        hs = weighted_stats(hist.get(h, []), d)
        aws = weighted_stats(hist.get(a, []), d)
        hh = weighted_stats(hist.get(h, []), d, "H")
        aa = weighted_stats(hist.get(a, []), d, "A")
        row = {"Result": r.FTR}
        for k in ["ppg","gf","ga","shots","sot"]:
            row["H_"+k] = hs.get(k, np.nan)
            row["A_"+k] = aws.get(k, np.nan)
        for k in ["ppg","gf","ga"]:
            row["HH_"+k] = hh.get(k, np.nan)
            row["AA_"+k] = aa.get(k, np.nan)
        rows.append(row)
        append_record(hist, h, d, "H", r.FTHG, r.FTAG, r.get("HS",np.nan), r.get("HST",np.nan))
        append_record(hist, a, d, "A", r.FTAG, r.FTHG, r.get("AS",np.nan), r.get("AST",np.nan))
    return pd.DataFrame(rows)

def fit_match_model(epl):
    ft = historical_feature_table(epl)
    model = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("lr", LogisticRegression(max_iter=3000))
    ])
    model.fit(ft[FEATURES], ft["Result"])
    neutral = pd.Series(model.named_steps["imp"].statistics_, index=FEATURES)
    return model, neutral

def tempered_probs(model, X):
    X = pd.DataFrame([X], columns=FEATURES)
    transformed = model.named_steps["sc"].transform(model.named_steps["imp"].transform(X))
    logits = model.named_steps["lr"].decision_function(transformed)
    logits = np.atleast_2d(logits) / TEMPERATURE
    logits = logits - logits.max(axis=1, keepdims=True)
    ex = np.exp(logits)
    return ex / ex.sum(axis=1, keepdims=True)

def teams_by_season(df):
    return {s: set(g.HomeTeam).union(g.AwayTeam) for s, g in df.groupby("Season")}

def team_season_stats(df, season, team):
    g = df[(df.Season == season) & ((df.HomeTeam == team) | (df.AwayTeam == team))]
    vals = []
    for _, r in g.iterrows():
        home = r.HomeTeam == team
        gf, ga = (r.FTHG, r.FTAG) if home else (r.FTAG, r.FTHG)
        sh = r.get("HS",np.nan) if home else r.get("AS",np.nan)
        sot = r.get("HST",np.nan) if home else r.get("AST",np.nan)
        vals.append([pts(gf,ga), gf, ga, sh, sot])
    a = np.array(vals, dtype=float)
    return {
        "n": len(a), "ppg": float(np.nanmean(a[:,0])), "gf": float(np.nanmean(a[:,1])),
        "ga": float(np.nanmean(a[:,2])), "shots": float(np.nanmean(a[:,3])),
        "sot": float(np.nanmean(a[:,4])),
    }

def fit_promotion_models(epl, champ):
    E, C = teams_by_season(epl), teams_by_season(champ)
    seasons = sorted(E.keys(), key=season_sort_key)
    rows = []
    for i in range(1, len(seasons)):
        prev, cur = seasons[i-1], seasons[i]
        for team in sorted(E[cur] & C.get(prev, set())):
            cs, es = team_season_stats(champ, prev, team), team_season_stats(epl, cur, team)
            rows.append({
                "C_ppg":cs["ppg"],"C_gf":cs["gf"],"C_ga":cs["ga"],"C_shots":cs["shots"],"C_sot":cs["sot"],
                "E_ppg":es["ppg"],"E_gf":es["gf"],"E_ga":es["ga"],"E_shots":es["shots"],"E_sot":es["sot"],
            })
    df = pd.DataFrame(rows)
    X = df[["C_ppg","C_gf","C_ga","C_shots","C_sot"]].values
    models = {}
    for target in ["E_ppg","E_gf","E_ga","E_shots","E_sot"]:
        pipe = Pipeline([("sc",StandardScaler()),("ridge",Ridge(alpha=10.0))])
        pipe.fit(X, df[target].values)
        models[target] = pipe
    return models

def infer_previous_season_label(epl):
    # Historical file ends at 2025/26 in this project.
    return sorted(epl.Season.unique(), key=season_sort_key)[-1]

def promotion_priors(current_teams, epl, champ, models):
    prev_epl_season = infer_previous_season_label(epl)
    prev_teams = teams_by_season(epl)[prev_epl_season]
    champ_season = prev_epl_season
    champ_teams = teams_by_season(champ).get(champ_season, set())
    promoted = sorted((set(current_teams) - prev_teams) & champ_teams)
    priors = {}
    for team in promoted:
        cs = team_season_stats(champ, champ_season, team)
        x = np.array([[cs["ppg"],cs["gf"],cs["ga"],cs["shots"],cs["sot"]]])
        priors[team] = {
            "championship": cs,
            "ppg": float(models["E_ppg"].predict(x)[0]),
            "gf": float(models["E_gf"].predict(x)[0]),
            "ga": float(models["E_ga"].predict(x)[0]),
            "shots": float(models["E_shots"].predict(x)[0]),
            "sot": float(models["E_sot"].predict(x)[0]),
        }
    return priors

def fetch_api(token=None, api_json=None):
    if api_json:
        return json.loads(Path(api_json).read_text(encoding="utf-8"))
    token = token or os.getenv("FOOTBALL_DATA_TOKEN")
    if not token:
        raise RuntimeError("FOOTBALL_DATA_TOKEN secret is missing.")
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    r = requests.get(url, headers={"X-Auth-Token": token}, timeout=30)
    r.raise_for_status()
    return r.json()

def api_matches(payload):
    rows = []
    for m in payload.get("matches", []):
        home = canonical(m["homeTeam"]["name"])
        away = canonical(m["awayTeam"]["name"])
        utc = pd.to_datetime(m["utcDate"], utc=True)
        date = utc.tz_convert("Europe/London").tz_localize(None)
        score = m.get("score", {}).get("fullTime", {})
        hg, ag = score.get("home"), score.get("away")
        rows.append({
            "date": date, "date_str": date.strftime("%Y-%m-%d"),
            "home": home, "away": away, "status": m.get("status"),
            "hg": hg, "ag": ag,
        })
    return sorted(rows, key=lambda x: x["date"])

def build_current_history(epl, matches):
    hist = {}
    # All historical EPL can contribute, with max 30 and time decay.
    for _, r in epl.sort_values("Date").iterrows():
        append_record(hist, r.HomeTeam, r.Date, "H", r.FTHG, r.FTAG, r.get("HS",np.nan), r.get("HST",np.nan))
        append_record(hist, r.AwayTeam, r.Date, "A", r.FTAG, r.FTHG, r.get("AS",np.nan), r.get("AST",np.nan))
    for m in matches:
        if m["status"] == "FINISHED" and m["hg"] is not None and m["ag"] is not None:
            # football-data.org free match endpoint does not supply the historical HS/HST fields
            append_record(hist, m["home"], m["date"], "H", m["hg"], m["ag"], np.nan, np.nan)
            append_record(hist, m["away"], m["date"], "A", m["ag"], m["hg"], np.nan, np.nan)
    for t in hist:
        hist[t].sort(key=lambda x:x["date"])
    return hist

def fixture_vector(home, away, date, hist, neutral, priors, current_finished_count):
    v = neutral.copy()
    hs, aws = weighted_stats(hist.get(home,[]),date), weighted_stats(hist.get(away,[]),date)
    hh, aa = weighted_stats(hist.get(home,[]),date,"H"), weighted_stats(hist.get(away,[]),date,"A")
    for k in ["ppg","gf","ga","shots","sot"]:
        if pd.notna(hs.get(k,np.nan)): v["H_"+k] = hs[k]
        if pd.notna(aws.get(k,np.nan)): v["A_"+k] = aws[k]
    for k in ["ppg","gf","ga"]:
        if pd.notna(hh.get(k,np.nan)): v["HH_"+k] = hh[k]
        if pd.notna(aa.get(k,np.nan)): v["AA_"+k] = aa[k]

    # Fade Championship prior out over first 10 EPL matches.
    for team, prefix, vprefix in [(home,"H_","HH_"),(away,"A_","AA_")]:
        if team in priors:
            n = current_finished_count.get(team,0)
            blend = max(0.0, min(1.0, (10.0-n)/10.0))
            pr = priors[team]
            for k in ["ppg","gf","ga","shots","sot"]:
                v[prefix+k] = (1-blend)*float(v[prefix+k]) + blend*pr[k]
            for k in ["ppg","gf","ga"]:
                v[vprefix+k] = (1-blend)*float(v[vprefix+k]) + blend*pr[k]
    return v

def detail_copy(selected, opponent, venue, factor_name, selected_delta):
    favorable = selected_delta > 0
    factor_team = None
    if factor_name.startswith("Home "):
        factor_team = selected if venue=="H" else opponent
    else:
        factor_team = opponent if venue=="H" else selected

    if "overall form" in factor_name:
        if factor_team == selected:
            title = f"{selected}은(는) 최근까지 {'꾸준히 좋은 경기력을 보여왔습니다' if favorable else '경기 흐름이 다소 좋지 않습니다'}"
            body = (
                f"최근 몇 경기만 보는 것이 아니라 이전 경기까지 함께 살펴보되, 최근 경기에 더 큰 비중을 둡니다. "
                f"이 기간의 승점, 득점, 실점을 종합했을 때 {selected}의 경기 흐름이 리그 평균과 비교해 "
                f"{'좋게 평가되어 승리 가능성을 높였습니다' if favorable else '낮게 평가되어 승리 가능성을 낮췄습니다'}."
            )
        else:
            title = f"{opponent}의 최근 경기 흐름이 {selected}에게 {'도움이 됩니다' if favorable else '부담입니다'}"
            body = (
                f"{opponent} 역시 최근 경기에 더 큰 비중을 두고 이전 경기까지 함께 평가합니다. "
                f"최근 승점, 득점, 실점을 종합했을 때 상대의 경기 흐름이 리그 평균보다 "
                f"{'낮게 평가되어' if favorable else '좋게 평가되어'} {selected}의 승리 가능성에 "
                f"{'긍정적' if favorable else '부정적'} 영향을 줍니다."
            )
    elif "chance creation" in factor_name:
        if factor_team == selected:
            title = f"{selected}의 공격 기회 창출력이 {'좋습니다' if favorable else '아쉽습니다'}"
            body = (
                f"단순 득점 결과뿐 아니라 최근 경기의 슈팅과 유효슈팅을 함께 봅니다. {selected}가 상대 골문을 위협하는 기회를 "
                f"만들어내는 빈도가 리그 중립 수준과 비교해 {'좋게' if favorable else '낮게'} 평가되어 승리 확률에 반영됐습니다."
            )
        else:
            title = f"{opponent}의 공격 기회 창출력이 {selected}에게 {'유리하게' if favorable else '불리하게'} 작용합니다"
            body = (
                f"{opponent}의 최근 슈팅과 유효슈팅 생산력을 평가했습니다. 상대가 득점 기회를 만들어내는 능력이 리그 중립 수준보다 "
                f"{'약하게' if favorable else '강하게'} 평가되어 {selected}의 승리 가능성이 "
                f"{'높아지는' if favorable else '낮아지는'} 방향으로 작용했습니다."
            )
    elif "venue form" in factor_name:
        loc = "홈" if factor_name.startswith("Home") else "원정"
        if factor_team == selected:
            title = f"{selected}의 {loc} 경기력이 {'강점입니다' if favorable else '부담 요소입니다'}"
            body = (
                f"전체 경기력과 별도로 {selected}의 최근 {loc} 경기 승점과 득실점을 반영합니다. "
                f"{selected}의 {loc} 경기력이 중립 수준보다 {'좋아' if favorable else '낮아'} "
                f"이번 경기 승리 가능성을 {'끌어올립니다' if favorable else '낮춥니다'}."
            )
        else:
            title = f"{opponent}의 {loc} 경기력이 {selected}에게 {'크게 위협적이지 않습니다' if favorable else '부담입니다'}"
            body = (
                f"{opponent}의 최근 {loc} 경기 승점과 득실점을 따로 반영했습니다. 상대의 {loc} 경기력이 "
                f"{'중립 수준보다 약하게 평가되어' if favorable else '중립 수준보다 좋게 평가되어'} "
                f"{selected} 입장에서는 {'부담이 줄어듭니다' if favorable else '경기 난이도가 높아집니다'}."
            )
    else:
        title = f"{factor_name} — {selected}에게 {'유리' if favorable else '불리'}"
        body = "이 요인을 리그 중립 수준으로 바꿔 다시 계산했을 때 선택한 팀의 승리 확률이 변했습니다."

    # English copy for the bilingual site. Keep the same model attribution; only presentation changes.
    if "overall form" in factor_name:
        if factor_team == selected:
            title_en = f"{selected}'s recent form is {'a strength' if favorable else 'a concern'}"
            body_en = (
                f"The model looks beyond only the last few matches, while giving more weight to recent games. "
                f"Combining points, goals scored and goals conceded, {selected}'s recent form is rated "
                f"{'above' if favorable else 'below'} the league-neutral level, which {'raises' if favorable else 'reduces'} the win probability."
            )
        else:
            title_en = f"{opponent}'s recent form is {'helpful for' if favorable else 'a concern for'} {selected}"
            body_en = (
                f"{opponent}'s recent results are also weighted more heavily than older matches. "
                f"Based on points, goals scored and goals conceded, the opponent is rated "
                f"{'below' if favorable else 'above'} the league-neutral level, which {'helps' if favorable else 'hurts'} {selected}'s win probability."
            )
    elif "chance creation" in factor_name:
        if factor_team == selected:
            title_en = f"{selected}'s chance creation is {'strong' if favorable else 'below average'}"
            body_en = (
                f"The model uses recent shots and shots on target as well as goals. {selected}'s ability to create threatening chances is rated "
                f"{'above' if favorable else 'below'} the league-neutral level and is reflected in the win probability."
            )
        else:
            title_en = f"{opponent}'s chance creation works {'in favour of' if favorable else 'against'} {selected}"
            body_en = (
                f"The model evaluates {opponent}'s recent shots and shots on target. Their chance creation is rated "
                f"{'weaker' if favorable else 'stronger'} than the league-neutral level, which {'raises' if favorable else 'reduces'} {selected}'s win probability."
            )
    elif "venue form" in factor_name:
        loc_en = "home" if factor_name.startswith("Home") else "away"
        if factor_team == selected:
            title_en = f"{selected}'s {loc_en} form is {'a strength' if favorable else 'a concern'}"
            body_en = (
                f"The model separately considers {selected}'s recent {loc_en} points and goal difference. "
                f"That {loc_en} performance is rated {'above' if favorable else 'below'} the neutral level, which {'raises' if favorable else 'reduces'} the chance of winning this match."
            )
        else:
            title_en = f"{opponent}'s {loc_en} form is {'less threatening' if favorable else 'a concern'} for {selected}"
            body_en = (
                f"The model separately considers {opponent}'s recent {loc_en} points and goal difference. "
                f"The opponent's {loc_en} performance is rated {'below' if favorable else 'above'} the neutral level, which {'reduces the difficulty for' if favorable else 'makes the match tougher for'} {selected}."
            )
    else:
        title_en = f"{factor_name} — {'favourable' if favorable else 'unfavourable'} for {selected}"
        body_en = "The model recalculates the selected team's win probability after resetting this factor to a league-neutral level."

    return {
        "title": title, "body": body,
        "titleEn": title_en, "bodyEn": body_en,
        "impact": round(float(selected_delta)*100,1),
        "favorable": bool(favorable)
    }

def explain(model, neutral, vector, selected, opponent, venue):
    actual = tempered_probs(model, vector)[0]
    classes = list(model.classes_)
    sel_class = "H" if venue=="H" else "A"
    idx = classes.index(sel_class)
    base = tempered_probs(model, neutral)[0][idx]
    details = []
    for name, cols in GROUPS.items():
        temp = neutral.copy()
        for c in cols:
            temp[c] = vector[c]
        p = tempered_probs(model, temp)[0][idx]
        details.append(detail_copy(selected, opponent, venue, name, p-base))
    return actual, sorted(details, key=lambda d:abs(d["impact"]), reverse=True)


def build_standings(teams, matches):
    table = {t:{"team":t,"played":0,"won":0,"drawn":0,"lost":0,"gf":0,"ga":0,"gd":0,"points":0} for t in teams}
    for m in matches:
        if m["status"]!="FINISHED" or m["hg"] is None or m["ag"] is None:
            continue
        h,a,hg,ag = m["home"],m["away"],int(m["hg"]),int(m["ag"])
        for t in [h,a]:
            if t not in table:
                table[t]={"team":t,"played":0,"won":0,"drawn":0,"lost":0,"gf":0,"ga":0,"gd":0,"points":0}
        table[h]["played"] += 1
        table[a]["played"] += 1
        table[h]["gf"] += hg; table[h]["ga"] += ag
        table[a]["gf"] += ag; table[a]["ga"] += hg
        if hg > ag:
            table[h]["won"] += 1; table[a]["lost"] += 1; table[h]["points"] += 3
        elif hg < ag:
            table[a]["won"] += 1; table[h]["lost"] += 1; table[a]["points"] += 3
        else:
            table[h]["drawn"] += 1; table[a]["drawn"] += 1
            table[h]["points"] += 1; table[a]["points"] += 1
    rows=list(table.values())
    for r in rows:
        r["gd"] = r["gf"] - r["ga"]
    rows.sort(key=lambda r:(r["points"],r["gd"],r["gf"]), reverse=True)
    for i,r in enumerate(rows,1):
        r["rank"]=i
    return rows

def current_team_stats(team, date, hist, priors, current_finished_count):
    """Current model inputs for one team, including fading Championship prior."""
    overall = weighted_stats(hist.get(team, []), date)
    home = weighted_stats(hist.get(team, []), date, "H")
    away = weighted_stats(hist.get(team, []), date, "A")

    def blended(base, keys):
        out = {k: base.get(k, np.nan) for k in keys}
        if team in priors:
            n = current_finished_count.get(team, 0)
            blend = max(0.0, min(1.0, (10.0-n)/10.0))
            pr = priors[team]
            for k in keys:
                cur = out.get(k, np.nan)
                if pd.isna(cur): cur = pr[k]
                out[k] = (1-blend)*float(cur) + blend*float(pr[k])
        return out

    return {
        "overall": blended(overall, ["ppg","gf","ga","shots","sot"]),
        "home": blended(home, ["ppg","gf","ga"]),
        "away": blended(away, ["ppg","gf","ga"]),
    }


def build_power_rankings(model, neutral, teams, hist, priors, current_finished_count, date, standings):
    """
    Relative team-strength index from the same match model.
    Each team is evaluated vs a neutral league-level opponent once at home and once away.
    The strongest team's neutral-opponent xPts is set to 100; other teams scale proportionally.
    """
    classes = list(model.classes_)
    ci = {c:i for i,c in enumerate(classes)}
    raw = []
    stand_map = {r["team"]: r for r in standings}

    for team in teams:
        st = current_team_stats(team, date, hist, priors, current_finished_count)

        vh = neutral.copy()
        for k in ["ppg","gf","ga","shots","sot"]:
            val = st["overall"].get(k, np.nan)
            if pd.notna(val): vh["H_"+k] = val
        for k in ["ppg","gf","ga"]:
            val = st["home"].get(k, np.nan)
            if pd.notna(val): vh["HH_"+k] = val
        ph = tempered_probs(model, vh)[0]
        home_xpts = 3*float(ph[ci["H"]]) + float(ph[ci["D"]])

        va = neutral.copy()
        for k in ["ppg","gf","ga","shots","sot"]:
            val = st["overall"].get(k, np.nan)
            if pd.notna(val): va["A_"+k] = val
        for k in ["ppg","gf","ga"]:
            val = st["away"].get(k, np.nan)
            if pd.notna(val): va["AA_"+k] = val
        pa = tempered_probs(model, va)[0]
        away_xpts = 3*float(pa[ci["A"]]) + float(pa[ci["D"]])

        avg = (home_xpts + away_xpts) / 2.0
        raw.append({
            "team": team,
            "neutralXPPG": avg,
            "homeNeutralXPPG": home_xpts,
            "awayNeutralXPPG": away_xpts,
            "currentEPLRank": stand_map.get(team, {}).get("rank"),
        })

    raw.sort(key=lambda x:x["neutralXPPG"], reverse=True)
    max_raw = max((x["neutralXPPG"] for x in raw), default=1.0) or 1.0
    for i,x in enumerate(raw,1):
        x["rank"] = i
        x["score"] = round(100.0 * x["neutralXPPG"] / max_raw, 1)
        x["neutralXPPG"] = round(x["neutralXPPG"], 3)
        x["homeNeutralXPPG"] = round(x["homeNeutralXPPG"], 3)
        x["awayNeutralXPPG"] = round(x["awayNeutralXPPG"], 3)
    return raw


def build_team_profiles(teams, matches, hist, priors, current_finished_count, date, power_rankings):
    power_map = {r["team"]: r for r in power_rankings}
    profiles = {}
    for team in teams:
        st = current_team_stats(team, date, hist, priors, current_finished_count)
        finished = []
        for m in matches:
            if m["status"] != "FINISHED" or m["hg"] is None or m["ag"] is None:
                continue
            if team not in {m["home"],m["away"]}:
                continue
            home = m["home"] == team
            gf = int(m["hg"] if home else m["ag"])
            ga = int(m["ag"] if home else m["hg"])
            result = "W" if gf > ga else "D" if gf == ga else "L"
            finished.append({"date":m["date_str"],"opponent":m["away"] if home else m["home"],"venue":"H" if home else "A","gf":gf,"ga":ga,"result":result})
        finished.sort(key=lambda x:x["date"], reverse=True)
        recent = finished[:5]
        profiles[team] = {
            "recentResults": recent,
            "modelStats": {
                "ppg": round(float(st["overall"].get("ppg", np.nan)), 2) if pd.notna(st["overall"].get("ppg", np.nan)) else None,
                "gf": round(float(st["overall"].get("gf", np.nan)), 2) if pd.notna(st["overall"].get("gf", np.nan)) else None,
                "ga": round(float(st["overall"].get("ga", np.nan)), 2) if pd.notna(st["overall"].get("ga", np.nan)) else None,
                "shots": round(float(st["overall"].get("shots", np.nan)), 2) if pd.notna(st["overall"].get("shots", np.nan)) else None,
                "sot": round(float(st["overall"].get("sot", np.nan)), 2) if pd.notna(st["overall"].get("sot", np.nan)) else None,
                "homePPG": round(float(st["home"].get("ppg", np.nan)), 2) if pd.notna(st["home"].get("ppg", np.nan)) else None,
                "awayPPG": round(float(st["away"].get("ppg", np.nan)), 2) if pd.notna(st["away"].get("ppg", np.nan)) else None,
            },
            "powerRank": power_map.get(team, {}).get("rank"),
            "powerScore": power_map.get(team, {}).get("score"),
        }
    return profiles


def generate(payload):
    epl, champ = load_historical()
    model, neutral = fit_match_model(epl)
    promo_models = fit_promotion_models(epl, champ)
    matches = api_matches(payload)
    teams = sorted(set([m["home"] for m in matches] + [m["away"] for m in matches]))
    priors = promotion_priors(teams, epl, champ, promo_models)
    hist = build_current_history(epl, matches)

    finished_count = {t:0 for t in teams}
    for m in matches:
        if m["status"]=="FINISHED":
            finished_count[m["home"]] += 1
            finished_count[m["away"]] += 1

    future = [m for m in matches if m["status"] in {"SCHEDULED","TIMED","POSTPONED"}]
    # If API marks today's not-started match differently later, keep only matches without final score.
    future = [m for m in future if m["hg"] is None or m["ag"] is None]

    standings = build_standings(teams, matches)
    snapshot_date = max([m["date"] for m in matches if m["status"]=="FINISHED"], default=pd.Timestamp.utcnow().tz_localize(None))
    power_rankings = build_power_rankings(model, neutral, teams, hist, priors, finished_count, snapshot_date, standings)
    team_profiles = build_team_profiles(teams, matches, hist, priors, finished_count, snapshot_date, power_rankings)
    games = {t:[] for t in teams}
    classes = list(model.classes_)
    ci = {c:i for i,c in enumerate(classes)}

    for m in future:
        h,a,d = m["home"],m["away"],m["date"]
        v = fixture_vector(h,a,d,hist,neutral,priors,finished_count)
        probs = tempered_probs(model,v)[0]
        ph,pd_,pa = float(probs[ci["H"]]),float(probs[ci["D"]]),float(probs[ci["A"]])

        for selected,opponent,venue,win,loss in [
            (h,a,"H",ph,pa),(a,h,"A",pa,ph)
        ]:
            _, details = explain(model,neutral,v,selected,opponent,venue)
            note = ""
            note_en = ""
            if selected in priors or opponent in priors:
                involved = selected if selected in priors else opponent
                note = (
                    f"{involved}은(는) 승격 직후 EPL 표본이 적기 때문에 직전 Championship 시즌의 승점, 득점, 실점, "
                    f"슈팅, 유효슈팅을 과거 승격팀 사례를 통해 EPL 수준으로 변환한 초기 전력값을 함께 반영했습니다. "
                    f"이 보정은 EPL 경기가 쌓일수록 첫 10경기 동안 점차 줄어듭니다."
                )
                note_en = (
                    f"Because {involved} has only a small EPL sample immediately after promotion, the model also uses a conservative initial strength estimate derived from the club's previous Championship season. "
                    f"Points, goals, shots and shots on target are translated using historical promoted-team cases, and this adjustment gradually fades during the first 10 EPL matches."
                )
            games[selected].append({
                "date":m["date_str"],"opponent":opponent,"venue":venue,
                "win":win,"draw":pd_,"loss":loss,"xpts":3*win+pd_,
                "details":details,"promotionNote":note,"promotionNoteEn":note_en
            })

    for t in games:
        games[t] = sorted(games[t], key=lambda x:x["date"])[:10]

    rankings = {}
    for horizon in [3,5,10]:
        rr=[]
        for t in teams:
            gs=games[t][:horizon]
            if not gs: continue
            xp=sum(g["xpts"] for g in gs)
            rr.append({"team":t,"xpts":xp,"xppg":xp/len(gs)})
        rr.sort(key=lambda x:x["xpts"], reverse=True)
        for i,x in enumerate(rr,1): x["rank"]=i
        rankings[str(horizon)] = rr

    return {
        "asOf": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "methodVersion":"v4-auto",
        "games":games,
        "rankings":rankings,
        "standings":standings,
        "powerRankings":power_rankings,
        "teamProfiles":team_profiles,
        "promotionPriors": {t:{
            "championshipPPG":round(p["championship"]["ppg"],3),
            "mappedEPLPPG":round(p["ppg"],3)
        } for t,p in priors.items()}
    }


SITE_URL = "https://epl-run-in-lab.github.io/epl-run-in-lab"

def slugify_team(team):
    mapping = {
        "Man City":"man-city","Man United":"man-united","Aston Villa":"aston-villa",
        "Crystal Palace":"crystal-palace","Newcastle":"newcastle","Tottenham":"tottenham",
        "Nottingham":"nottingham","Bournemouth":"bournemouth","Brighton":"brighton",
        "Coventry":"coventry","Ipswich":"ipswich","Sunderland":"sunderland",
        "Brentford":"brentford","Chelsea":"chelsea","Arsenal":"arsenal","Liverpool":"liverpool",
        "Everton":"everton","Fulham":"fulham","Leeds":"leeds","Hull":"hull"
    }
    return mapping.get(team, team.lower().replace(" ","-").replace("'",""))

def esc(s):
    import html
    return html.escape(str(s), quote=True)

def fmtp(x):
    return f"{float(x)*100:.1f}%"

def fmt2(x):
    return f"{float(x):.2f}"

def page_shell(title, description, canonical_path, body, active="", schema_name=None):
    canonical = SITE_URL + canonical_path
    page_name = schema_name or title.split(" | ")[0]
    breadcrumb_items = [
        {"@type":"ListItem","position":1,"name":"EPL Run-in Lab","item":SITE_URL + "/"}
    ]
    if canonical_path != "/":
        breadcrumb_items.append({"@type":"ListItem","position":2,"name":page_name,"item":canonical})
    structured = {
        "@context":"https://schema.org",
        "@graph":[
            {"@type":"WebSite","@id":SITE_URL+"/#website","url":SITE_URL+"/","name":"EPL Run-in Lab",
             "description":"EPL 경기 예측, 일정 난이도, 기대 승점과 파워 랭킹을 데이터로 분석합니다.",
             "inLanguage":["ko","en"]},
            {"@type":"WebPage","@id":canonical+"#webpage","url":canonical,"name":page_name,
             "description":description,"isPartOf":{"@id":SITE_URL+"/#website"},"inLanguage":"ko-KR"},
            {"@type":"BreadcrumbList","itemListElement":breadcrumb_items}
        ]
    }
    structured_json = json.dumps(structured, ensure_ascii=False).replace("</", "<\\/")
    nav = [
        ("홈","/"),("경기 예측","/predictions/"),("일정 난이도","/fixture-difficulty/"),
        ("파워 랭킹","/power-ranking/"),("EPL 순위","/standings/"),("팀 분석","/teams/"),
        ("모델 소개","/model/")
    ]
    links = "".join(
        f'<a class="nav {"active" if path==active else ""}" href="{SITE_URL}{path}">{label}</a>'
        for label,path in nav
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{structured_json}</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2MHM6WELBT"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','G-2MHM6WELBT');</script>
<style>
:root{{--bg:#f5f7fb;--panel:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--soft:#eef2f7;--good:#0f766e;--bad:#b91c1c}}
body.dark{{--bg:#0b1220;--panel:#111827;--text:#f3f4f6;--muted:#9ca3af;--line:#263244;--soft:#182235;--good:#5eead4;--bad:#fca5a5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,"Noto Sans KR",sans-serif;line-height:1.55}}
header{{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--line)}}.top{{max-width:1180px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:16px}}.brand{{font-weight:900;text-decoration:none;color:var(--text);white-space:nowrap}}
nav{{display:flex;gap:6px;overflow:auto;flex:1}}.nav{{text-decoration:none;color:var(--muted);padding:7px 9px;border-radius:9px;white-space:nowrap;font-size:14px}}.nav.active,.nav:hover{{background:var(--soft);color:var(--text)}}
.switch{{width:42px;height:24px;border:0;border-radius:99px;background:#111827;padding:3px;cursor:pointer;display:flex;align-items:center}}.knob{{width:18px;height:18px;background:#fff;border-radius:50%;display:block;transition:.2s}}body.dark .switch{{background:#e5e7eb}}body.dark .knob{{transform:translateX(18px);background:#111827}}
main{{max-width:1100px;margin:auto;padding:34px 20px 70px}}h1{{font-size:clamp(28px,5vw,44px);line-height:1.15;margin:0 0 10px}}h2{{margin-top:34px}}.lead{{color:var(--muted);max-width:760px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:22px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}}.label{{font-size:13px;color:var(--muted)}}.big{{font-size:27px;font-weight:900;margin-top:4px}}table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}}th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{font-size:12px;color:var(--muted)}}.good{{color:var(--good)}}.bad{{color:var(--bad)}}.muted{{color:var(--muted)}}.share{{border:1px solid var(--line);background:var(--panel);color:var(--text);padding:9px 12px;border-radius:10px;cursor:pointer;font-weight:700}}.teams{{display:flex;flex-wrap:wrap;gap:8px}}.teams a{{text-decoration:none;color:var(--text);background:var(--panel);border:1px solid var(--line);padding:9px 12px;border-radius:10px}}footer{{max-width:1100px;margin:auto;padding:0 20px 40px;color:var(--muted);font-size:12px}}
@media(max-width:760px){{nav{{display:none}}.grid{{grid-template-columns:1fr}}th,td{{padding:10px 7px;font-size:13px}}}}
</style>
</head>
<body>
<header><div class="top"><a class="brand" href="{SITE_URL}/">EPL Run-in Lab</a><nav>{links}</nav><button class="switch" id="theme" aria-label="다크모드 전환"><span class="knob"></span></button></div></header>
<main>{body}</main>
<footer>데이터 기반 확률은 경기 결과를 보장하지 않습니다. EPL Run-in Lab은 Premier League 또는 개별 구단의 공식 서비스가 아닙니다.</footer>
<script>
const b=document.body,t=document.getElementById('theme');if(localStorage.getItem('runin-theme')==='dark')b.classList.add('dark');t.onclick=()=>{{b.classList.toggle('dark');localStorage.setItem('runin-theme',b.classList.contains('dark')?'dark':'light')}};
async function sharePage(text){{const data={{title:document.title,text:text,url:location.href}};if(navigator.share){{try{{await navigator.share(data);return}}catch(e){{}}}}await navigator.clipboard.writeText(location.href);const btn=document.querySelector('.share');if(btn){{const old=btn.textContent;btn.textContent='링크 복사됨';setTimeout(()=>btn.textContent=old,1500)}}}}
</script>
</body></html>"""

def write_page(rel, html):
    p = ROOT / "docs" / rel
    if p.suffix.lower() != ".html":
        p = p / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")

def generate_static_pages(result):
    standings = result.get("standings", [])
    powers = result.get("powerRankings", [])
    games = result.get("games", {})
    rankings = result.get("rankings", {})
    profiles = result.get("teamProfiles", {})
    teams = sorted(games)

    # Predictions
    rows=[]
    for t in teams:
        if games.get(t):
            g=games[t][0]
            rows.append(f"<tr><td><a href='{SITE_URL}/teams/{slugify_team(t)}/'>{esc(t)}</a></td><td>{esc(g['date'])}</td><td>{esc(g['opponent'])} ({g['venue']})</td><td><b>{fmtp(g['win'])}</b></td><td>{fmtp(g['draw'])}</td><td>{fmtp(g['loss'])}</td><td>{fmt2(g['xpts'])}</td></tr>")
    body=f"""<h1>EPL 경기 승률 예측</h1><p class="lead">현재 데이터를 기준으로 각 팀의 다음 경기 승·무·패 확률과 기대 승점(xPts)을 비교합니다. 팀별 페이지에서는 확률이 왜 그렇게 계산됐는지도 확인할 수 있습니다.</p>
<button class="share" onclick="sharePage('EPL 다음 경기 승률 예측')">예측 공유하기</button>
<h2>팀별 다음 경기</h2><table><thead><tr><th>팀</th><th>날짜</th><th>상대</th><th>승</th><th>무</th><th>패</th><th>xPts</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"""
    write_page("predictions", page_shell("EPL 경기 예측·승률·기대 승점 | EPL Run-in Lab","프리미어리그(EPL) 다음 경기의 승·무·패 확률, 승률과 기대 승점(xPts)을 데이터 모델로 비교합니다.","/predictions/",body,"/predictions/"))

    # Fixture difficulty
    rr=rankings.get("5",[])
    rows="".join(f"<tr><td>{r['rank']}</td><td><a href='{SITE_URL}/teams/{slugify_team(r['team'])}/'>{esc(r['team'])}</a></td><td><b>{fmt2(r['xpts'])}</b></td><td>{fmt2(r['xppg'])}</td></tr>" for r in rr)
    body=f"""<h1>EPL 일정 난이도</h1><p class="lead">향후 5경기에서 모델이 예상하는 기대 승점이 높을수록 상대적으로 유리한 일정으로 평가합니다. 단순 상대 순위가 아니라 경기별 승·무·패 확률을 합산합니다.</p>
<button class="share" onclick="sharePage('EPL 향후 5경기 일정 난이도')">순위 공유하기</button><h2>향후 5경기</h2><table><thead><tr><th>#</th><th>팀</th><th>xPts</th><th>xPPG</th></tr></thead><tbody>{rows}</tbody></table>"""
    write_page("fixture-difficulty",page_shell("EPL 일정 난이도·남은 일정 | 향후 5경기 | EPL Run-in Lab","프리미어리그(EPL) 20개 팀의 향후 5경기 일정 난이도와 남은 일정을 기대 승점(xPts)으로 비교합니다.","/fixture-difficulty/",body,"/fixture-difficulty/"))

    # Power ranking
    rows="".join(f"<tr><td>{r['rank']}</td><td><a href='{SITE_URL}/teams/{slugify_team(r['team'])}/'>{esc(r['team'])}</a></td><td><b>{r['score']:.1f}</b></td><td>{r.get('currentEPLRank') or '-'}</td><td>{r['neutralXPPG']:.2f}</td></tr>" for r in powers)
    body=f"""<h1>EPL 파워 랭킹</h1><p class="lead">현재 리그 순위와 별개로, 같은 리그 평균 수준의 상대를 만난다고 가정했을 때 모델이 평가하는 팀 전력을 비교합니다. 홈·원정 중립 상대 기대 승점을 평균한 뒤 최고 팀을 100으로 정규화합니다.</p>
<h2>모델 전력 순위</h2><table><thead><tr><th>#</th><th>팀</th><th>Power Score</th><th>현재 EPL 순위</th><th>중립 상대 xPts</th></tr></thead><tbody>{rows}</tbody></table>"""
    write_page("power-ranking",page_shell("EPL 파워랭킹·팀 전력 순위 | EPL Run-in Lab","현재 프리미어리그 순위와 별개로 데이터 모델이 평가한 EPL 20개 팀의 파워랭킹과 상대 전력을 비교합니다.","/power-ranking/",body,"/power-ranking/"))

    # Standings
    rows="".join(f"<tr><td>{r['rank']}</td><td><a href='{SITE_URL}/teams/{slugify_team(r['team'])}/'>{esc(r['team'])}</a></td><td>{r['played']}</td><td>{r['won']}</td><td>{r['drawn']}</td><td>{r['lost']}</td><td>{r['gd']:+d}</td><td><b>{r['points']}</b></td></tr>" for r in standings)
    body=f"""<h1>현재 EPL 순위</h1><p class="lead">현재까지 완료된 리그 경기 결과를 기준으로 계산한 순위표입니다.</p><table><thead><tr><th>#</th><th>팀</th><th>경기</th><th>승</th><th>무</th><th>패</th><th>득실</th><th>승점</th></tr></thead><tbody>{rows}</tbody></table>"""
    write_page("standings",page_shell("현재 EPL 순위·승점 | EPL Run-in Lab","현재 EPL 순위, 승점, 승무패와 득실차를 확인합니다.","/standings/",body,"/standings/"))

    # Team index
    links="".join(f"<a href='{SITE_URL}/teams/{slugify_team(t)}/'>{esc(t)}</a>" for t in teams)
    body=f"""<h1>EPL 팀 분석</h1><p class="lead">팀을 선택하면 현재 순위, 최근 경기 흐름, 파워 스코어, 향후 일정과 경기별 승률을 한 페이지에서 확인할 수 있습니다.</p><div class="teams">{links}</div>"""
    write_page("teams",page_shell("EPL 팀별 경기 예측·승률·일정 분석 | EPL Run-in Lab","아스날, 리버풀 등 EPL 20개 팀의 경기 예측, 승률, 향후 일정 난이도, 기대 승점과 파워랭킹을 팀별로 확인합니다.","/teams/",body,"/teams/"))

    standmap={r["team"]:r for r in standings}
    powmap={r["team"]:r for r in powers}
    r5map={r["team"]:r for r in rankings.get("5",[])}
    for t in teams:
        st=standmap.get(t,{})
        pw=powmap.get(t,{})
        r5=r5map.get(t,{})
        gs=games.get(t,[])[:5]
        prof=profiles.get(t,{})
        stats=prof.get("modelStats",{})
        fx="".join(f"<tr><td>{esc(g['date'])}</td><td>{'홈' if g['venue']=='H' else '원정'}</td><td><a href='{SITE_URL}/teams/{slugify_team(g['opponent'])}/'>{esc(g['opponent'])}</a></td><td><b>{fmtp(g['win'])}</b></td><td>{fmtp(g['draw'])}</td><td>{fmtp(g['loss'])}</td><td>{fmt2(g['xpts'])}</td></tr>" for g in gs)
        recent=" · ".join(f"{x['date'][5:]} {'홈' if x['venue']=='H' else '원정'} {x['opponent']} {x['gf']}-{x['ga']} {x['result']}" for x in prof.get("recentResults",[])) or "현재 시즌 완료 경기 없음"
        nextg=gs[0] if gs else None
        next_summary=(f"다음 경기는 {esc(nextg['date'])} {'홈에서' if nextg['venue']=='H' else '원정에서'} {esc(nextg['opponent'])}을(를) 상대합니다. "
                      f"모델은 {esc(t)} 기준 승리 {fmtp(nextg['win'])}, 무승부 {fmtp(nextg['draw'])}, 패배 {fmtp(nextg['loss'])}, 기대 승점 {fmt2(nextg['xpts'])}점을 제시합니다.") if nextg else "현재 예정된 다음 경기 데이터가 없습니다."
        form_bits=[]
        if stats.get('ppg') is not None: form_bits.append(f"최근 경기 흐름에 반영되는 경기당 승점은 {stats['ppg']:.2f}점")
        if stats.get('gf') is not None and stats.get('ga') is not None: form_bits.append(f"경기당 득점/실점은 {stats['gf']:.2f}/{stats['ga']:.2f}")
        if stats.get('shots') is not None and stats.get('sot') is not None: form_bits.append(f"경기당 슈팅/유효슈팅은 {stats['shots']:.1f}/{stats['sot']:.1f}회")
        if stats.get('homePPG') is not None and stats.get('awayPPG') is not None: form_bits.append(f"홈/원정 경기당 승점은 {stats['homePPG']:.2f}/{stats['awayPPG']:.2f}점")
        form_summary=". ".join(form_bits)+("." if form_bits else "현재 표시할 모델 입력 통계가 충분하지 않습니다.")
        summary=(f"{esc(t)}은(는) 현재 EPL {st.get('rank','-')}위, 승점 {st.get('points','-')}점입니다. "
                 f"Power Score는 {pw.get('score','-')}로 모델 파워랭킹 {pw.get('rank','-')}위이며, "
                 f"향후 5경기 기대 승점은 {fmt2(r5['xpts']) if r5 else '-'}점, 일정 쉬움 순위는 {r5.get('rank','-')}위입니다.")
        desc=(f"{t} EPL 경기 예측. 다음 상대 {nextg['opponent']}전 승률 {fmtp(nextg['win'])}, 향후 5경기 기대 승점 {fmt2(r5['xpts']) if r5 else '-'}, 현재 순위와 Power Score를 확인하세요." if nextg else f"{t}의 EPL 경기 예측, 향후 일정, 기대 승점, 현재 순위와 Power Score를 확인하세요.")
        body=f"""<h1>{esc(t)} 경기 예측·승률·향후 일정</h1><p class="lead">{summary}</p>
<button class="share" onclick="sharePage('{esc(t)} EPL 경기 예측과 향후 일정')">이 팀 분석 공유하기</button>
<div class="grid"><div class="card"><div class="label">현재 EPL 순위</div><div class="big">{st.get('rank','-')}위</div><div class="muted">승점 {st.get('points','-')}</div></div>
<div class="card"><div class="label">Power Score</div><div class="big">{pw.get('score','-')}</div><div class="muted">파워 랭킹 {pw.get('rank','-')}위</div></div>
<div class="card"><div class="label">향후 5경기 xPts</div><div class="big">{fmt2(r5['xpts']) if r5 else '-'}</div><div class="muted">일정 쉬움 순위 {r5.get('rank','-')}위</div></div></div>
<h2>{esc(t)} 다음 경기 예측</h2><p>{next_summary}</p>
<h2>{esc(t)} 최근 경기 흐름</h2><p>{esc(recent)}</p><p class="muted">{form_summary}</p>
<h2>{esc(t)} 향후 5경기 예측</h2><table><thead><tr><th>날짜</th><th>장소</th><th>상대</th><th>승</th><th>무</th><th>패</th><th>xPts</th></tr></thead><tbody>{fx}</tbody></table>
<h2>이 수치를 어떻게 봐야 하나요?</h2><p class="muted">승·무·패 확률과 xPts는 최근 경기 흐름, 득점·실점, 슈팅·유효슈팅, 홈·원정 경기력 등을 모델에 반영한 결과입니다. Power Score는 리그 평균 수준의 가상 상대를 기준으로 팀 전력을 비교한 별도 지표이며 실제 EPL 순위와는 다릅니다.</p>
<h2>관련 EPL 분석</h2><div class="teams"><a href="{SITE_URL}/predictions/">EPL 경기 예측</a><a href="{SITE_URL}/fixture-difficulty/">EPL 일정 난이도</a><a href="{SITE_URL}/power-ranking/">EPL 파워랭킹</a><a href="{SITE_URL}/standings/">현재 EPL 순위</a></div>"""
        write_page(f"teams/{slugify_team(t)}",page_shell(f"{t} 경기 예측·승률·남은 일정 | EPL Run-in Lab",desc,f"/teams/{slugify_team(t)}/",body,"/teams/",f"{t} 경기 예측·승률·남은 일정"))

    # Model page
    body="""<h1>예측 모델 소개</h1><p class="lead">EPL Run-in Lab은 AI가 임의로 경기 결과를 만들어내는 사이트가 아니라, 과거 EPL 경기 데이터로 학습한 통계 모델의 확률을 보여주는 사이트입니다.</p>
<h2>무엇을 반영하나?</h2><p>최근 경기 승점, 득점·실점, 슈팅·유효슈팅, 홈·원정 경기력을 사용합니다. 오래된 경기일수록 영향이 점차 줄어들며, 승격팀은 EPL 표본이 충분해질 때까지 직전 Championship 시즌을 과거 승격팀 사례로 보수적으로 변환한 초기 전력값을 함께 사용합니다.</p>
<h2>확률의 이유</h2><p>설명 화면의 %p 효과는 특정 요인만 리그 중립 수준으로 되돌린 뒤 모델을 다시 계산하여 선택 팀의 승리 확률이 얼마나 달라지는지 측정한 값입니다. 요인끼리 상호작용하므로 단순 합계와 최종 확률은 정확히 일치하지 않습니다.</p>
<h2>주의사항</h2><p>부상, 라인업, 전술 변화처럼 실시간 반영되지 않는 변수가 있으며, 무료 데이터 소스에서 제공되지 않는 현재 시즌 일부 세부 지표는 기존 기록의 영향을 받을 수 있습니다. 확률은 결과를 보장하지 않습니다.</p>"""
    write_page("model",page_shell("EPL Run-in Lab 예측 모델·방법론","EPL 경기 승률, 기대 승점, 일정 난이도와 파워 랭킹을 계산하는 모델의 방법과 한계를 설명합니다.","/model/",body,"/model/"))

    # robots and sitemap
    paths=["/","/predictions/","/fixture-difficulty/","/power-ranking/","/standings/","/teams/","/model/"]+[f"/teams/{slugify_team(t)}/" for t in teams]
    now=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls="\n".join(f"  <url><loc>{SITE_URL}{p}</loc><lastmod>{now}</lastmod></url>" for p in paths)
    (ROOT/"docs/sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n',encoding="utf-8")
    (ROOT/"docs/robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",encoding="utf-8")

    # Search Console verification placeholder instructions, not a fake verification token.
    (ROOT/"docs/SEARCH_CONSOLE_SETUP.txt").write_text(
        "Google Search Console에서 URL 접두어 속성으로 "+SITE_URL+"/ 를 추가하세요.\n"
        "HTML 파일 인증을 선택한 뒤 Google이 제공한 googleXXXXXXXX.html 파일을 docs/에 그대로 넣고 배포하세요.\n"
        "인증 후 Sitemap 메뉴에서 sitemap.xml을 제출하세요.\n", encoding="utf-8"
    )

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--api-json", help="Use a saved football-data.org response instead of live API")
    args=ap.parse_args()
    payload=fetch_api(api_json=args.api_json)
    result=generate(payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    generate_static_pages(result)
    print(f"Wrote {OUT} and SEO static pages")
    print(f"Teams: {len(result['games'])}; promoted priors: {list(result['promotionPriors'])}")

if __name__=="__main__":
    main()
