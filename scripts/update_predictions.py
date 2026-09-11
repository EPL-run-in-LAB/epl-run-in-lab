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
    "Nottingham Forest": "Nott'm Forest",
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

    return {
        "title": title, "body": body,
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
            if selected in priors or opponent in priors:
                involved = selected if selected in priors else opponent
                note = (
                    f"{involved}은(는) 승격 직후 EPL 표본이 적기 때문에 직전 Championship 시즌의 승점, 득점, 실점, "
                    f"슈팅, 유효슈팅을 과거 승격팀 사례를 통해 EPL 수준으로 변환한 초기 전력값을 함께 반영했습니다. "
                    f"이 보정은 EPL 경기가 쌓일수록 첫 10경기 동안 점차 줄어듭니다."
                )
            games[selected].append({
                "date":m["date_str"],"opponent":opponent,"venue":venue,
                "win":win,"draw":pd_,"loss":loss,"xpts":3*win+pd_,
                "details":details,"promotionNote":note
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
        "promotionPriors": {t:{
            "championshipPPG":round(p["championship"]["ppg"],3),
            "mappedEPLPPG":round(p["ppg"],3)
        } for t,p in priors.items()}
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--api-json", help="Use a saved football-data.org response instead of live API")
    args=ap.parse_args()
    payload=fetch_api(api_json=args.api_json)
    result=generate(payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Teams: {len(result['games'])}; promoted priors: {list(result['promotionPriors'])}")

if __name__=="__main__":
    main()
