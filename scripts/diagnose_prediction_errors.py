#!/usr/bin/env python3
"""Exploratory EPL error diagnostics from frozen pre-kickoff forecasts."""
import json
import argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/performance/epl_prediction_accuracy.json"
OUT=ROOT/"data/performance/prediction_error_diagnostics.json"
MD=ROOT/"data/performance/PREDICTION_ERROR_DIAGNOSTICS_KO.md"
CLASSES=("home","draw","away")

def group(rows):
    n=len(rows)
    return {"matches":n,"correct":sum(x["correctTop1"] for x in rows),
            "accuracy":round(sum(x["correctTop1"] for x in rows)/n,4) if n else None,
            "brier":round(sum(x["brier"] for x in rows)/n,4) if n else None,
            "logLoss":round(sum(x["logLoss"] for x in rows)/n,4) if n else None}

def analyse(report):
    rows=report["fixtures"]
    n=len(rows)
    if not n or n!=report["sample"]["eligibleFinalizedFixtures"] or any(not x.get("capturedAt") for x in rows):
        raise ValueError("Invalid pre-kickoff archive coverage")
    confusion={k:{j:0 for j in CLASSES} for k in CLASSES}
    for x in rows:
        confusion[x["mostLikelyOutcome"]][x["actualOutcome"]]+=1
    calibration={}
    for cls in CLASSES:
        calibration[cls]={
            "meanProbability":round(sum(x["probabilities"][cls] for x in rows)/n,4),
            "actualFrequency":round(sum(x["actualOutcome"]==cls for x in rows)/n,4),
            "binaryBrier":round(sum((x["probabilities"][cls]-int(x["actualOutcome"]==cls))**2 for x in rows)/n,4)
        }
    bins=[]
    for lo,hi in ((0,.4),(.4,.5),(.5,.6),(.6,1.01)):
        sub=[x for x in rows if lo<=max(x["probabilities"].values())<hi]
        bins.append({"min":lo,"maxExclusive":hi,**group(sub),
                     "averageConfidence":round(sum(max(x["probabilities"].values()) for x in sub)/len(sub),4) if sub else None})
    worst=sorted(rows,key=lambda x:-x["logLoss"])[:10]
    examples=[{"date":x["date"],"home":x["home"],"away":x["away"],
               "score":[x["homeGoals"],x["awayGoals"]],"expected":x["mostLikelyOutcome"],
               "actual":x["actualOutcome"],"probabilities":x["probabilities"],
               "logLoss":round(x["logLoss"],4)} for x in worst]
    return {"version":1,"source":"validated frozen pre-kickoff prediction report","sample":n,
            "overall":group(rows),"predictedByActual":confusion,
            "byActual":{c:group([x for x in rows if x["actualOutcome"]==c]) for c in CLASSES},
            "byTopPick":{c:group([x for x in rows if x["mostLikelyOutcome"]==c]) for c in CLASSES},
            "calibration":calibration,"confidenceBins":bins,
            "byMonth":{m:group([x for x in rows if x["date"].startswith(m)])
                       for m in sorted(set(x["date"][:7] for x in rows))},
            "highestLogLossGames":examples,
            "baseline":{"uniformBrier":report["results"]["uniformOneThirdBrier"],
                        "uniformLogLoss":report["results"]["uniformOneThirdLogLoss"],
                        "alwaysHomeTop1":report["results"]["alwaysPredictHomeAccuracyOnSample"]},
            "warnings":["40 games are not enough to establish systematic bias or retrain weights.",
                        "Draws can be calibrated even when not the single highest outcome.",
                        "Neither causes of upsets nor coach/lineup fatigue are established.",
                        "Only frozen pre-kickoff probabilities are included."]}

def markdown(d):
    names={"home":"홈승","draw":"무승부","away":"원정승"}
    x=["# EPL Run-in Lab — 예측 오류 진단 (Phase 4)","",
       "경기 시작 전에 저장한 확률과 종료 결과가 연결된 "+str(d["sample"])+"경기를 평가했다.","",
       "## 실제 결과별 적중 현황","","| 실제 결과 | 경기 | 적중 | 적중률 | Brier |",
       "|---|---:|---:|---:|---:|"]
    for k in CLASSES:
        q=d["byActual"][k]
        x.append("| "+names[k]+" | "+str(q["matches"])+" | "+str(q["correct"])+" | "+
                 (str(round(q["accuracy"]*100,1))+"%" if q["accuracy"] is not None else "—")+" | "+str(q["brier"])+" |")
    x+=["","## 실제 발생률과 모델 평균 확률","","| 결과 | 발생률 | 평균 예측 확률 | 차이(%p) |",
        "|---|---:|---:|---:|"]
    for k in CLASSES:
        q=d["calibration"][k]
        x.append("| "+names[k]+" | "+str(round(100*q["actualFrequency"],1))+"% | "+
                 str(round(100*q["meanProbability"],1))+"% | "+
                 str(round(100*(q["meanProbability"]-q["actualFrequency"]),1))+" |")
    x+=["","## 오차가 컸던 경기","","| 날짜 | 경기 | 결과 | 최다 확률 | Log Loss |",
        "|---|---|---|---|---:|"]
    for q in d["highestLogLossGames"][:8]:
        x.append("| "+q["date"]+" | "+q["home"]+" - "+q["away"]+" | "+
                 ":".join(map(str,q["score"]))+" | "+names[q["expected"]]+" | "+str(q["logLoss"])+" |")
    x+=["","## 해석 주의","","- 무승부를 최다 확률로 선택하지 않은 사실 자체는 무승부 확률이 잘못됐다는 증거가 아니다.",
        "- 충분한 표본이 쌓일 때까지 기존 모델의 가중치를 변경하지 않는다.",
        "- 경기 직전 부상, 로테이션, 일정 부담의 인과효과는 현재 기록만으로 검증하지 않는다.",
        "- 수치는 경기 전 보관된 확률에만 기반한다.",""]
    return "\n".join(x)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=SOURCE)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--md",type=Path,default=MD)
    a=p.parse_args()
    res=analyse(json.loads(a.input.read_text(encoding="utf-8")))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    a.md.write_text(markdown(res),encoding="utf-8")
    print("Diagnosed",res["sample"],"eligible matches")
if __name__=="__main__":main()
