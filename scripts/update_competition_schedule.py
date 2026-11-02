#!/usr/bin/env python3
"""Collect 2026/27 cup fixtures/results without modifying EPL predictions.

Source: https://github.com/oladeeayo/open-matchday
Run: python scripts/update_competition_schedule.py
"""
import csv
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import requests
from team_identity import resolve, EPL_CLUBS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/data/competition_schedule.json"
HISTORY = ROOT / "docs/data/competition_results_archive.json"
REPORT = ROOT / "docs/data/competition_validation_report.json"
BASE = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data"
SEASON = "2627"
COMPETITIONS = {
    "UCL": "UEFA_1_champions-league",
    "UEL": "UEFA_1_europa-league",
    "UECL": "UEFA_1_conference-league",
    "FAC": "ENG_CUP_fa-cup",
    "EFL": "ENG_CUP_efl-cup",
}
def read_csv(session, competition, kind):
    url = f"{BASE}/{competition}/{kind}_{SEASON}.csv"
    response = session.get(url, timeout=35)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    required = {"date", "home", "away"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Empty or invalid CSV: {url}")
    return rows, url

def valid_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()

def build_match(competition, kind, row):
    date = valid_date(row["date"])
    home_raw, away_raw = row["home"].strip(), row["away"].strip()
    if not home_raw or not away_raw:
        raise ValueError(f"Missing team in {competition} {date}")
    home_info, away_info = resolve(home_raw), resolve(away_raw)
    home, away = home_info['displayName'], away_info['displayName']
    # Source observation key; persistent IDs are assigned by reconcile().
    key = f"{competition}|{date}|{home_raw}|{away_raw}"
    result = {
        "id": key, "competition": competition, "date": date,
        "timeSource": row.get("time", "").strip(), "timeVerifiedUTC": None,
        "home": home, "away": away,
        "homeClubId": home_info["clubId"], "awayClubId": away_info["clubId"],
        "homeRaw": home_raw, "awayRaw": away_raw,
        "homeEpl": home_info["matched"], "awayEpl": away_info["matched"],
        "status": "FINISHED" if kind == "results" else "SCHEDULED",
        "source": "open-matchday",
    }
    if kind == "results":
        result["score"] = {
            "home": int(row["ft_home"]), "away": int(row["ft_away"])
        }
        result["upstreamSource"] = row.get("source", "")
    return result

def load_history():
    if not HISTORY.exists():
        return {"version": 1, "matches": {}, "changes": []}
    return json.loads(HISTORY.read_text(encoding="utf-8"))

def fixture_pair(m):
    # Compare only fully identified teams; unknown opponents remain ambiguous.
    if not m["homeClubId"] or not m["awayClubId"]:
        return None
    return (m["competition"], m["homeClubId"], m["awayClubId"])

def reconcile(observations, history, now):
    """Conservative reschedule detection; never silently overwrite a final result."""
    known = history.setdefault("matches", {})
    changes = history.setdefault("changes", [])
    issues = []
    by_pair = {}
    for ident, old in known.items():
        pair = fixture_pair(old)
        if pair:
            by_pair.setdefault(pair, []).append((ident, old))
    matched_old = set()
    current = []
    for m in observations:
        exact = known.get(m["id"])
        if exact is not None:
            stable_id = m["id"]
        else:
            pair = fixture_pair(m)
            candidates = [(i, old) for i, old in by_pair.get(pair, [])
                          if i not in matched_old] if pair else []
            # A unique pairing is safe only if it is not a second leg or another round.
            # Without an upstream fixture ID, date changes remain review-only.
            if candidates:
                issues.append({"type": "possible_reschedule", "incoming": m["id"],
                               "candidates": [i for i, _ in candidates]})
            stable_id = m["id"]
        m = dict(m, id=stable_id)
        current.append(m)
        if m["status"] != "FINISHED":
            continue
        old = known.get(stable_id)
        if old is None:
            known[stable_id] = dict(m, firstSeenAt=now)
        elif old.get("score") != m.get("score"):
            change = {"id": stable_id, "detectedAt": now,
                      "previous": old.get("score"), "incoming": m.get("score")}
            if not any(x.get("id") == stable_id and x.get("incoming") == m.get("score")
                       for x in changes):
                changes.append(change)
            issues.append({"type": "result_conflict", "id": stable_id})
        matched_old.add(stable_id)
    return current, issues

def compare_previous_schedule(current):
    """Detect disappeared or moved fixtures without assuming the same pairing is unique."""
    if not OUT.exists():
        return []
    previous = json.loads(OUT.read_text(encoding="utf-8")).get("matches", [])
    current_ids = {m["id"] for m in current}
    old_ids = {m["id"] for m in previous}
    incoming_by_pair = {}
    for m in current:
        pair = fixture_pair(m)
        if pair:
            incoming_by_pair.setdefault(pair, []).append(m)
    issues = []
    for old in previous:
        if old["id"] in current_ids or old.get("status") == "FINISHED":
            continue
        pair = fixture_pair(old)
        candidates = [m for m in incoming_by_pair.get(pair, [])
                      if m["id"] not in old_ids] if pair else []
        if candidates:
            issues.append({"type": "schedule_date_or_name_change",
                           "previous": old["id"],
                           "candidates": [m["id"] for m in candidates]})
        else:
            issues.append({"type": "fixture_disappeared", "previous": old["id"]})
    return issues

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="."+path.name+".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main():
    session = requests.Session()
    all_matches, coverage = [], {}
    for code, directory in COMPETITIONS.items():
        for kind in ("results", "fixtures"):
            raw, url = read_csv(session, directory, kind)
            matches = [build_match(code, kind, row) for row in raw]
            all_matches.extend(matches)
            coverage[f"{code}_{kind}"] = {"count": len(matches), "url": url}
    ids = [m["id"] for m in all_matches]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate competition/date/team identity; manual review required")
    history = load_history()
    now = datetime.now(timezone.utc).isoformat()
    all_matches, issues = reconcile(all_matches, history, now)
    relevant = sorted(
        [m for m in all_matches if m["homeEpl"] or m["awayEpl"]],
        key=lambda m: (m["date"], m["competition"], m["home"]),
    )
    issues.extend(compare_previous_schedule(relevant))
    # No fuzzy matching: retain raw names and report unknown opponents for review.
    unknown = sorted({m[side+"Raw"] for m in all_matches
                      for side in ("home", "away") if not m[side+"ClubId"]})
    report = {
        "version": 1, "updatedAt": now,
        "knownEplClubs": len(EPL_CLUBS),
        "competitionCounts": coverage,
        "eplRelevantMatches": len(relevant),
        "unknownNames": unknown,
        "issues": issues,
        "note": "Unknown non-EPL names are expected; never infer EPL club IDs from similarity.",
    }
    schedule = {
        "version": 1, "season": "2026/27", "updatedAt": now,
        "source": "https://github.com/oladeeayo/open-matchday",
        "notice": "Unverified source kickoff times are not used for hour-level rest calculations.",
        "coverage": coverage, "matches": relevant,
    }
    # Conflicts are quarantined: fail before publishing any new schedule/history.
    if issues:
        atomic_json(REPORT, report)
        raise ValueError(f"{len(issues)} identity/result conflicts; see validation report")
    atomic_json(OUT, schedule)
    atomic_json(HISTORY, history)
    atomic_json(REPORT, report)
    print(f"Competition schedule: {len(relevant)} EPL-team matches; archived results: {len(history['matches'])}")
if __name__ == "__main__":
    main()
