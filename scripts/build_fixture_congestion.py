#!/usr/bin/env python3
"""Build an explanatory fixture congestion dataset; never modify predictions.

Date-only fixture spacing is the default. UTC kickoff spacing is enabled only
when *both* adjacent matches have explicit independently verified timestamps.
"""
import json
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from team_identity import ACTIVE_EPL_IDS, EPL_CLUBS, resolve

ROOT = Path(__file__).resolve().parents[1]
CUP = ROOT / "docs/data/competition_schedule.json"
EPL = ROOT / "docs/data/predictions.json"
OUT = ROOT / "docs/data/fixture_congestion.json"

def utc_verified(m):
    value = m.get("timeVerifiedUTC")
    proof = m.get("timeVerification")
    if not value or not isinstance(proof, dict) or proof.get("status") != "verified" or not proof.get("source"):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if t.tzinfo is None or t.utcoffset() != timedelta(0) or t.date().isoformat() != m["date"]:
            # Calendar date may legitimately differ from UTC for a late local kick-off;
            # until venue timezone is verified, quarantine rather than assume.
            return None
        return t
    except (ValueError, TypeError):
        return None

def normalize_cup(m):
    # Always resolve using original strings: older saved snapshots can have stale IDs.
    home = resolve(m["homeRaw"])
    away = resolve(m["awayRaw"])
    if not (home["matched"] or away["matched"]):
        return None
    return dict(m, homeClubId=home["clubId"], awayClubId=away["clubId"],
                homeEpl=home["matched"], awayEpl=away["matched"],
                home=home["displayName"], away=away["displayName"],
                quality="unverified_upstream", verifiedKickoffUTC=(
                    utc_verified(m).isoformat() if utc_verified(m) else None))

def normalize_epl_predictions(data):
    events = {}
    # The predictions file is a snapshot, not a live official fixture feed.
    for name, games in data["games"].items():
        club = resolve(name)
        if not club["matched"]:
            raise ValueError("Unknown EPL predictions team: " + name)
        for game in games:
            other = resolve(game["opponent"])
            if not other["matched"]:
                raise ValueError("Unknown EPL predictions opponent: " + game["opponent"])
            venue = game["venue"]
            if venue not in ("H", "A"):
                raise ValueError("Unsupported venue")
            home, away = (club["clubId"], other["clubId"]) if venue == "H" else (other["clubId"], club["clubId"])
            date.fromisoformat(game["date"])
            key = "EPL|" + game["date"] + "|" + home + "|" + away
            events[key] = dict(id=key, date=game["date"], competition="EPL",
                               home=EPL_CLUBS[home], away=EPL_CLUBS[away],
                               homeClubId=home, awayClubId=away,
                               verifiedKickoffUTC=None, quality="prediction_snapshot",
                               status="SCHEDULED")
    return list(events.values())

def build(cups, predictions):
    if cups.get("season") != "2026/27":
        raise ValueError("Unexpected cup season")
    events = normalize_epl_predictions(predictions)
    ids = {e["id"] for e in events}
    for raw in cups["matches"]:
        m = normalize_cup(raw)
        if m is None:
            continue
        date.fromisoformat(m["date"])
        if m["id"] in ids:
            raise ValueError("Duplicate fixture ID")
        ids.add(m["id"])
        events.append(m)
    teams = {}
    reference_date = datetime.now(timezone.utc).date()
    for club_id in sorted(ACTIVE_EPL_IDS):
        matches = sorted([m for m in events if m["homeClubId"] == club_id or m["awayClubId"] == club_id],
                         key=lambda m: (m["date"], m["id"]))
        annotated = []
        away_streak = 0
        for idx, m in enumerate(matches):
            d = date.fromisoformat(m["date"])
            # Include fixture itself; future events do not affect counts.
            past7 = sum(0 <= (d-date.fromisoformat(p["date"])).days < 7 for p in matches)
            past14 = sum(0 <= (d-date.fromisoformat(p["date"])).days < 14 for p in matches)
            prev = matches[idx-1] if idx else None
            gap = (d-date.fromisoformat(prev["date"])).days if prev else None
            prev_utc = utc_verified(prev) if prev else None
            curr_utc = utc_verified(m)
            hours = round((curr_utc-prev_utc).total_seconds()/3600, 1) if prev_utc and curr_utc and curr_utc > prev_utc else None
            venue = "H" if m["homeClubId"] == club_id else "A"
            away_streak = away_streak + 1 if venue == "A" else 0
            same_day = any(p["date"] == m["date"] and p["id"] != m["id"] for p in matches)
            annotated.append(dict(id=m["id"], date=m["date"], competition=m["competition"],
                                  opponent=m["away"] if m["homeClubId"] == club_id else m["home"],
                                  venue=venue,
                                  status=m["status"], quality=m["quality"],
                                  daysSincePrevious=gap, calendarRestDays=max(gap-1,0) if gap is not None else None,
                                  kickoffGapHours=hours, restBasis="verified_kickoff" if hours is not None else "calendar_date",
                                  gamesIn7Days=past7, gamesIn14Days=past14,
                                  awayStreak=away_streak, shortTurnaround=(gap is not None and 0 < gap <= 3),
                                  potentialDateConflict=same_day,
                                  isUpcoming=d >= reference_date))
        upcoming = [m for m in annotated if m["isUpcoming"]]
        teams[club_id] = dict(name=EPL_CLUBS[club_id], matches=annotated,
                              summary={"upcomingCount": len(upcoming),
                                       "nextFixture": upcoming[0]["date"] if upcoming else None,
                                       "upcoming7DayPeak": max((m["gamesIn7Days"] for m in upcoming),default=None),
                                       "potentialDateConflicts": sum(m["potentialDateConflict"] for m in annotated)})
    snapshot_age_days = None
    try:
        snapshot_date = date.fromisoformat(str(predictions.get("asOf",""))[:10])
        snapshot_age_days = (reference_date - snapshot_date).days
    except ValueError:
        pass
    return dict(version=1, season="2026/27",
                generatedAt=datetime.now(timezone.utc).isoformat(),
                asOfDate=reference_date.isoformat(),
                snapshotAgeDays=snapshot_age_days,
                eplSnapshotStale=(snapshot_age_days is None or snapshot_age_days > 7),
                sources={"cupUpdatedAt":cups.get("updatedAt"), "eplSnapshotAsOf":predictions.get("asOf")},
                disclaimer="Cup fixture truth not independently verified; EPL schedule derived from prediction snapshot. No fatigue effect is applied to predictions.",
                timestampPolicy="Verified UTC kickoff interval only when both adjacent fixtures have trusted provenance; otherwise calendar-date rest days.",
                teams=teams)

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".fixture_congestion.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main():
    cups = json.loads(CUP.read_text(encoding="utf-8"))
    predictions = json.loads(EPL.read_text(encoding="utf-8"))
    result = build(cups, predictions)
    save(OUT, result)
    print("Congestion metrics built for", len(result["teams"]), "clubs")

if __name__ == "__main__":
    main()
