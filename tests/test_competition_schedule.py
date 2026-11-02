"""Offline checks for club identity, data normalization and archive safety.

Run from repository root: python -m unittest discover -s tests -p 'test_competition_schedule.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from team_identity import EPL_CLUBS, resolve
from update_competition_schedule import build_match

class ClubIdentityTests(unittest.TestCase):
    def test_all_canonical_names_resolve(self):
        self.assertEqual(len(EPL_CLUBS), 20)
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
        }
        for alias, club_id in pairs.items():
            self.assertEqual(resolve(alias)["clubId"], club_id)

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

if __name__ == "__main__":
    unittest.main()
