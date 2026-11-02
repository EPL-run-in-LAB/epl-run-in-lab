"""Offline checks for club identity, data normalization and archive safety.

Run from repository root: python -m unittest discover -s tests -p 'test_competition_schedule.py'
"""
import sys
import json
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from team_identity import EPL_CLUBS, ACTIVE_EPL_IDS, resolve
from update_competition_schedule import build_match, reconcile, compare_previous_schedule, refresh_archive_identity, audit_epl_source

class ClubIdentityTests(unittest.TestCase):
    def test_all_canonical_names_resolve(self):
        self.assertEqual(len(ACTIVE_EPL_IDS), 20)
        for club_id, name in EPL_CLUBS.items():
            self.assertEqual(resolve(name)["clubId"], club_id)

    def test_verified_aliases(self):
        pairs = {
            "Manchester City": "man-city",
            "Man Utd": "man-united",
            "Manchester United": "man-united",
            "AFC Bournemouth": "bournemouth",
            "Newcastle United": "newcastle",
            "Nottingham Forest": "nottingham",
            "Ipswich Town": "ipswich",
        }
        for alias, club_id in pairs.items():
            self.assertEqual(resolve(alias)["clubId"], club_id)

    def test_official_2026_27_membership_and_relegated_club(self):
        expected = {"arsenal", "aston-villa", "bournemouth", "brentford",
                    "brighton", "chelsea", "coventry", "crystal-palace",
                    "everton", "fulham", "hull", "ipswich", "leeds",
                    "liverpool", "man-city", "man-united", "newcastle",
                    "nottingham", "sunderland", "tottenham"}
        self.assertEqual(ACTIVE_EPL_IDS, expected)
        self.assertEqual(resolve("West Ham United")["clubId"], "west-ham")
        self.assertFalse(resolve("West Ham United")["matched"])
        self.assertTrue(resolve("Ipswich Town")["matched"])

    def test_archive_membership_correction_preserves_result(self):
        old = build_match("EFL", "results", {
            "date": "2026-08-08", "home": "West Ham United",
            "away": "Ipswich Town", "ft_home": "2", "ft_away": "1"
        })
        old["homeEpl"] = True  # Previous production bug
        old["awayClubId"] = None
        old["awayEpl"] = False
        history = {"matches": {old["id"]: old}, "changes": []}
        fixes = refresh_archive_identity(history)
        updated = history["matches"][old["id"]]
        self.assertEqual(updated["score"], {"home": 2, "away": 1})
        self.assertFalse(updated["homeEpl"])
        self.assertTrue(updated["awayEpl"])
        self.assertEqual(updated["awayClubId"], "ipswich")
        self.assertEqual(len(fixes), 3)

    def test_epl_membership_gate_rejects_relegated_club(self):
        import csv
        import io
        from unittest.mock import Mock
        valid = sorted(ACTIVE_EPL_IDS)
        fixture_rows = [{"date":"2026-10-01","home":name,"away":"Arsenal"} for name in EPL_CLUBS.values() if name != "West Ham"]
        fixture_rows.append({"date":"2026-10-02","home":"West Ham United","away":"Arsenal"})
        with patch("update_competition_schedule.read_csv", return_value=(fixture_rows, "mock")):
            with self.assertRaisesRegex(ValueError, "unapproved club"):
                audit_epl_source(Mock())

    def test_unknown_and_youth_teams_not_auto_merged(self):
        for name in ["Manchester United U21", "Manchester City Women", "Unknown FC"]:
            self.assertIsNone(resolve(name)["clubId"])

    def test_original_spelling_and_club_id_retained(self):
        m = build_match("EFL", "fixtures", {
            "date": "2026-12-15", "time": "21:00",
            "home": "Manchester City", "away": "Bradford City",
        })
        self.assertEqual(m["home"], "Man City")
        self.assertEqual(m["homeRaw"], "Manchester City")
        self.assertEqual(m["homeClubId"], "man-city")
        self.assertIsNone(m["awayClubId"])
        self.assertIsNone(m["timeVerifiedUTC"])

    def test_results_preserve_score(self):
        m = build_match("UCL", "results", {
            "date": "2026-10-21", "time": "20:00",
            "home": "Real Madrid", "away": "Manchester United",
            "ft_home": "2", "ft_away": "1", "source": "example",
        })
        self.assertEqual(m["score"], {"home": 2, "away": 1})
        self.assertEqual(m["awayClubId"], "man-united")
        self.assertEqual(m["status"], "FINISHED")

    def test_reschedule_is_quarantined_not_merged(self):
        original = build_match("EFL", "results", {
            "date": "2026-12-15", "home": "Manchester City",
            "away": "Manchester United", "ft_home": "1", "ft_away": "0"
        })
        history = {"matches": {original["id"]: original}, "changes": []}
        moved = build_match("EFL", "fixtures", {
            "date": "2026-12-17", "home": "Man City", "away": "Man Utd"
        })
        _, issues = reconcile([moved], history, "2026-11-03T00:00:00Z")
        self.assertEqual(issues, [])  # No false positive from past results
        self.assertEqual(len(history["matches"]), 1)

    def test_score_conflict_preserves_original(self):
        original = build_match("UCL", "results", {
            "date": "2026-10-21", "home": "Arsenal", "away": "Chelsea",
            "ft_home": "2", "ft_away": "0"
        })
        incoming = dict(original, score={"home": 1, "away": 0})
        history = {"matches": {original["id"]: original}, "changes": []}
        _, issues = reconcile([incoming], history, "2026-11-03T00:00:00Z")
        self.assertEqual(history["matches"][original["id"]]["score"]["home"], 2)
        self.assertEqual(issues[0]["type"], "result_conflict")

    def test_schedule_date_change_detected(self):
        old = build_match("EFL", "fixtures", {
            "date": "2026-12-15", "home": "Manchester City",
            "away": "Manchester United"
        })
        new = build_match("EFL", "fixtures", {
            "date": "2026-12-17", "home": "Man City",
            "away": "Man Utd"
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schedule.json"
            path.write_text(json.dumps({"matches": [old]}))
            with patch("update_competition_schedule.OUT", path):
                issues = compare_previous_schedule([new])
        self.assertEqual(issues[0]["type"], "schedule_date_or_name_change")

if __name__ == "__main__":
    unittest.main()
