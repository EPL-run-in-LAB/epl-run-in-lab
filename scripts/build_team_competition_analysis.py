#!/usr/bin/env python3
"""Descriptive 90-minute domestic vs UEFA comparisons from independent CC0 history."""
import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from build_history_warehouse import ROOT

DB = ROOT / "data/history/history.sqlite"
OUT = ROOT / "data/history/domestic_uefa_comparison.json"
MD = ROOT / "data/history/DOMESTIC_VS_UEFA_ANALYSIS_KO.md"
LEAGUES = {"EN1":"Premier League","DE1":"Bundesliga","ES1":"La Liga",
           "IT1":"Serie A","FR1":"Ligue 1"}
EUROPE = {"UCL","UEL","UECL"}

def empty():
    return dict(played=0, won=0, drawn=0, lost=0, gf=0, ga=0, points=0)

def add(stats, gf, ga):
    if type(gf) is not int or type(ga) is not int or min(gf,ga) < 0:
        raise ValueError("Cannot compare missing or invalid 90-minute scores")
    stats["played"] += 1
    stats["gf"] += gf
    stats["ga"] += ga
    if gf > ga:
        stats["won"] += 1
        stats["points"] += 3
    elif gf < ga:
        stats["lost"] += 1
    else:
        stats["drawn"] += 1
        stats["points"] += 1

def combine(all_stats):
    out = empty()
    for data in all_stats:
        for key in out:
            out[key] += data[key]
    return out

def metrics(stats):
    n = stats["played"]
    return {**stats, "gd":stats["gf"]-stats["ga"],
            "ppg":round(stats["points"]/n,3) if n else None,
            "winPct":round(100*stats["won"]/n,2) if n else None}

def build(db_path=DB,out_path=OUT,md_path=MD):
    db_path,out_path,md_path = Path(db_path),Path(out_path),Path(md_path)
    league = defaultdict(empty)
    domestic_comp = {}
    europe = defaultdict(empty)
    europe_comp = defaultdict(empty)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        club_names = {r["club_id"]:r["canonical_name"] for r in con.execute(
            "SELECT club_id,canonical_name FROM clubs")}
        club_countries = {r["club_id"]:r["country"] for r in con.execute(
            "SELECT club_id,country FROM clubs")}
        domestic_total = con.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        uefa_total = con.execute("SELECT COUNT(*) FROM uefa_matches").fetchone()[0]
        if (domestic_total,uefa_total)!=(8908,1941):
            raise ValueError("Comparison requires audited 5-league and UEFA warehouse")

        for m in con.execute("""SELECT s.season,s.competition_id AS competition,
                    m.home_club_id AS home,m.away_club_id AS away,
                    m.home_goals AS hg,m.away_goals AS ag
                    FROM matches m JOIN seasons s USING(season_id)
                    WHERE m.status='FINISHED' AND m.model_training_eligible=1"""):
            if m["competition"] not in LEAGUES:
                raise ValueError("Unexpected domestic league")
            for club,gf,ga in ((m["home"],m["hg"],m["ag"]),
                               (m["away"],m["ag"],m["hg"])):
                key = (club,m["season"])
                add(league[key],gf,ga)
                if key in domestic_comp and domestic_comp[key]!=m["competition"]:
                    raise ValueError("Conflicting domestic team competition")
                domestic_comp[key]=m["competition"]

        completed=0
        cancelled=0
        for m in con.execute("""SELECT s.season,s.competition_id AS competition,
                    m.home_club_id AS home,m.away_club_id AS away,
                    m.home_goals_90 AS hg,m.away_goals_90 AS ag,m.status
                    FROM uefa_matches m JOIN seasons s USING(season_id)"""):
            if m["competition"] not in EUROPE:
                raise ValueError("Unexpected European competition")
            if m["status"]=="CANCELLED":
                cancelled+=1
                continue
            if m["status"]!="FINISHED":
                raise ValueError("Unexpected UEFA match status")
            completed+=1
            for club,gf,ga in ((m["home"],m["hg"],m["ag"]),
                               (m["away"],m["ag"],m["hg"])):
                key=(club,m["season"])
                add(europe[key],gf,ga)
                add(europe_comp[(club,m["season"],m["competition"])],gf,ga)

    rows=[]
    unmatched=[]
    for club,season in sorted(europe):
        key=(club,season)
        if key not in league:
            unmatched.append({"clubId":club,"clubName":club_names[club],
                              "season":season,"country":club_countries[club]})
            continue
        l,u=league[key],europe[key]
        by_comp = {cid:metrics(europe_comp[(club,season,cid)]) for cid in sorted(EUROPE)
                   if (club,season,cid) in europe_comp}
        rows.append({
            "clubId":club, "clubName":club_names[club], "country":club_countries[club],
            "season":season, "domesticCompetition":domestic_comp[key],
            "domestic":metrics(l), "uefa":metrics(u), "uefaByCompetition":by_comp,
            "ppgGapDescriptive":round(u["points"]/u["played"]-l["points"]/l["played"],3),
            "coverageCaution2025":season=="2025-26",
        })
    rows.sort(key=lambda x:(x["season"],x["country"],x["clubName"]))
    clubs=defaultdict(list)
    for row in rows:
        clubs[row["clubId"]].append(row)
    if completed!=1939 or cancelled!=2 or len(clubs)<35:
        raise ValueError("Incomplete UEFA comparison coverage")
    if not any(r["clubName"]=="Arsenal FC" for r in rows):
        raise ValueError("Missing Premier League comparators")
    if not any(r["clubName"]=="Paris Saint-Germain" for r in rows):
        raise ValueError("Missing PSG comparators")

    summaries=[]
    for club, items in sorted(clubs.items()):
        dom=combine([r["domestic"] for r in items])
        euro=combine([r["uefa"] for r in items])
        last3=[r for r in items if r["season"] in ("2023-24","2024-25","2025-26")]
        summaries.append({
            "clubId":club,"clubName":club_names[club],"country":club_countries[club],
            "matchedSeasons":[r["season"] for r in items],
            "domestic":metrics(dom),"uefa":metrics(euro),
            "lastThreeDomestic":metrics(combine([r["domestic"] for r in last3])),
            "lastThreeUefa":metrics(combine([r["uefa"] for r in last3])),
            "includesPartial2025Uefa":any(r["season"]=="2025-26" for r in items)
        })
    summaries.sort(key=lambda r:(r["country"],r["clubName"]))
    report={
        "schemaVersion":1,
        "source":"independent CC0 history.sqlite; not the production prediction model",
        "period":"2021/22-2025/26",
        "definition":"3/1/0 points, only goals at 90 minutes; awarded/cancelled excluded",
        "limitations":[
            "UEFA strength and opponent selection differ by competition, so PPG gap is descriptive, not a team rating.",
            "No 2025/26 UEFA Europa League or Conference League main-stage data in current CC0 source.",
            "Club-season comparisons only include clubs with both domestic and UEFA matches.",
            "AET and penalty outcomes do not change 90-minute win/draw/loss.",
            "2026/27 live season, lineups, fatigue and match probability validation are out of scope."
        ],
        "coverage":{"domesticFixtures":domestic_total,"uefaFixtures":uefa_total,
                    "uefaCompleted":completed,"uefaCancelled":cancelled,
                    "pairedClubSeasons":len(rows),"pairedClubs":len(summaries),
                    "unpairedUefaClubSeasons":len(unmatched),
                    "missingUefaSeasons":[{"season":"2025-26","competition":"UEL"},
                                          {"season":"2025-26","competition":"UECL"}]},
        "clubSeasons":rows, "clubSummaries":summaries, "unpairedUefaClubSeasons":unmatched
    }
    out_path.parent.mkdir(parents=True,exist_ok=True)
    out_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[
        "# EPL Run-in Lab: 국내 리그 vs 유럽대항전 비교",
        "",
        "대상: 2021/22~2025/26, 국내 EPL·분데스리가·라리가·세리에 A·리그 1 및 UCL·UEL·UECL",
        "",
        f"- 국내 리그 **{domestic_total:,}경기**, UEFA **{uefa_total:,}경기** (그중 완료 {completed:,}건)",
        f"- 동일 구단·시즌 비교 **{len(rows)}건**, 고유 구단 **{len(summaries)}개**",
        "- 데이터: CC0 독립 역사 데이터베이스. 기존 EPL 예측 모델의 확률과 다른 지표.",
        "",
        "## 대표 구단의 2024/25 시즌 비교",
        "",
        "| 구단 | 국내 경기 | 국내 PPG | UEFA 경기 | UEFA PPG | UEFA 대회 |",
        "|---|---:|---:|---:|---:|---|"
    ]
    examples=["Arsenal FC","Manchester City FC","FC Bayern München",
              "Paris Saint-Germain","Real Madrid CF","FC Internazionale Milano"]
    for name in examples:
        for r in rows:
            if r["clubName"]==name and r["season"]=="2024-25":
                lines.append(f'| {name} | {r["domestic"]["played"]} | {r["domestic"]["ppg"]:.3f} | '
                             f'{r["uefa"]["played"]} | {r["uefa"]["ppg"]:.3f} | '
                             f'{", ".join(r["uefaByCompetition"])} |')
    lines += [
        "",
        "## 해석 원칙",
        "",
        "- PPG는 경기당 승점(90분 기준)이며 대회의 상대 수준·선발 명단을 보정하지 않았음.",
        "- 2025/26 UEL·UECL 원본이 없어 해당 기간 UEFA 통합 성적은 일부 누락.",
        "- 연장전·승부차기 승리는 90분 기준 승리가 아니므로 별도 기록.",
        "- 결과 차이만으로 리그 수준이나 로테이션의 효과를 인과적으로 주장할 수 없음.",
        "- 전체 구단별·시즌별 기록: domestic_uefa_comparison.json 참조.",
        ""
    ]
    md_path.parent.mkdir(parents=True,exist_ok=True)
    md_path.write_text("\n".join(lines),encoding="utf-8")
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,default=DB)
    parser.add_argument("--out",type=Path,default=OUT)
    parser.add_argument("--md",type=Path,default=MD)
    args=parser.parse_args()
    result=build(args.db,args.out,args.md)
    print("Comparison built",result["coverage"])
