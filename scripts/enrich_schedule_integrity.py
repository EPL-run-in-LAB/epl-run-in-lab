#!/usr/bin/env python3
"""Add vetted optional NL/PT domestic fixtures and audit unresolved source dates.

Isolated staging only. No unsupported UTC kickoff or travel-time estimates.
A league must have 306 unique home/away fixtures before it is considered a
complete domestic schedule. Cross-competition club IDs require an EXACT
pre-reviewed alias from club_aliases_2627.json; no fuzzy guessing.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
import requests

from build_multi_competition_schedule import get_csv, OM, sha_id

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/live/current_schedule_2627.json"
ALIASES = ROOT / "data/live/club_aliases_2627.json"
OUTPUT = ROOT / "data/live/extended_domestic_2627.json"
AUDIT = ROOT / "data/live/date_conflict_audit_2627.json"
LEAGUES = {"NL1": "NED_1_eredivisie", "PT1": "POR_1_primeira-liga"}
EXPECTED = 306

def collect(session, aliases, reference_date):
    approved = aliases["other"]
    out, stats = [], {}
    for comp, folder in LEAGUES.items():
        rows = []
        for kind in ("results", "fixtures"):
            url = OM + "/" + folder + "/" + kind + "_2627.csv"
            rows.extend(get_csv(session, url, kind))
        pairs = [(r["home"], r["away"]) for r in rows]
        clubs = {club for h, a in pairs for club in (h, a)}
        complete = len(rows) == EXPECTED and len(set(pairs)) == EXPECTED and len(clubs) == 18
        if not complete:
            stats[comp] = {"status": "INCOMPLETE_QUARANTINED", "count": len(rows),
                           "distinctPairs": len(set(pairs)), "clubs": len(clubs)}
            continue
        mapped_clubs = {name: approved.get(name) for name in clubs}
        mapped_count = sum(bool(v) for v in mapped_clubs.values())
        stats[comp] = {"status": "COMPLETE_SOURCE_UNVERIFIED_DATES", "count": EXPECTED,
                       "matchedClubIds": mapped_count, "unmatchedClubNames":
                       sorted(name for name, key in mapped_clubs.items() if not key)}
        for r in rows:
            status = "FINISHED" if r["score"] is not None else (
                "PAST_UNVERIFIED" if r["date"] < reference_date else "SCHEDULED")
            out.append({"id": sha_id(comp, r["round"], r["home"], r["away"]),
                        "competition": comp, "season": "2026-27", "date": r["date"],
                        "round": r["round"], "home": r["home"], "away": r["away"],
                        "homeClubId": mapped_clubs[r["home"]],
                        "awayClubId": mapped_clubs[r["away"]],
                        "status": status, "score": r["score"],
                        "dateDisagreement": True, "dateAuditStatus": "SINGLE_SOURCE_UNVERIFIED",
                        "timeUnverified": r["timeUnverified"], "kickoffUTC": None,
                        "source": "open-matchday", "sourceLicense": "noncommercial"})
    return out, stats

def audit_dates(stage):
    matches = {(m["competition"], m["home"], m["away"]): m for m in stage["matches"]
               if m["competition"] in {"EN1", "EN2", "DE1", "ES1", "IT1", "FR1"}}
    issues = []
    for m in stage.get("matches", []):
        if not m.get("dateDisagreement"): continue
        if m["competition"] not in {"EN1", "EN2", "DE1", "ES1", "IT1", "FR1"}: continue
        issues.append({"id": m["id"], "competition": m["competition"],
                       "home": m["home"], "away": m["away"], "status": m["status"],
                       "cc0Date": m.get("cc0Date"), "providerDate": m["date"],
                       "dateVerified": False, "kickoffVerifiedUTC": None,
                       "classification": "SOURCE_DATE_DISAGREEMENT_REQUIRES_EXTERNAL_CHECK",
                       "reason": "Reschedule, fixture baseline, and timezone are not distinguishable from these feeds."})
    counts = Counter(x["status"] for x in issues)
    return {"season": "2026-27", "verifiedCount": 0, "unresolvedCount": len(issues),
            "byStatus": dict(counts), "license": "staging-only, noncommercial inputs",
            "policy": "No source conflict is resolved by majority vote, weekday heuristics or guessed kickoff.",
            "issues": issues}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--aliases", type=Path, default=ALIASES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--audit", type=Path, default=AUDIT)
    args = parser.parse_args()
    stage = json.loads(args.input.read_text(encoding="utf-8"))
    if stage.get("status") != "STAGING_NOT_MODEL_INPUT": raise ValueError("Untrusted staging status")
    aliases = json.loads(args.aliases.read_text(encoding="utf-8"))
    with requests.Session() as session:
        matches, coverage = collect(session, aliases, stage["asOfDate"])
    enriched = {"schemaVersion": 1, "season": "2026-27",
                "status": "STAGING_NOT_MODEL_INPUT", "license": "noncommercial",
                "coverage": coverage, "matches": matches}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = audit_dates(stage)
    args.audit.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Extra domestic league coverage:", coverage)
    print("Unresolved date disagreements:", report["unresolvedCount"], report["byStatus"])

if __name__ == "__main__":
    main()
