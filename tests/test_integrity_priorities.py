import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_match_archive import find_result, match_date
from enrich_schedule_integrity import audit_dates

class ResultIdentityTests(unittest.TestCase):
    def setUp(self):
        self.s = {"date": "2026-11-08", "season": "2026/27",
                  "home": "Arsenal", "away": "Chelsea", "footballDataId": 112}
        self.result = {"id": "goal-101", "matchStatus": "FINISHED",
                       "homeTeamName": "Arsenal", "awayTeamName": "Chelsea",
                       "matchDate": "2026-11-08", "homeTeamScore": 2, "awayTeamScore": 1}
    def test_exact_match(self):
        self.assertEqual(find_result(self.s, [self.result])["id"], "goal-101")
    def test_previous_season_same_teams_rejected(self):
        other = dict(self.result, id="old", matchDate="2025-11-08")
        self.assertIsNone(find_result(self.s, [other]))
    def test_no_date_is_not_a_match(self):
        bad = dict(self.result)
        bad.pop("matchDate")
        self.assertIsNone(find_result(self.s, [bad]))
    def test_multiple_matching_ids_are_ambiguous(self):
        self.assertIsNone(find_result(self.s, [self.result, dict(self.result, id="second")]))
    def test_goal_api_id_lease(self):
        self.assertIsNone(find_result(self.s, [self.result], known_goal_id="wrong"))
        self.assertIsNotNone(find_result(self.s, [self.result], known_goal_id="goal-101"))
    def test_london_timezone(self):
        self.assertEqual(match_date({"utcDate": "2026-07-31T23:30:00Z"}), "2026-08-01")

class ConflictAuditTests(unittest.TestCase):
    def test_conflicts_not_silently_confirmed(self):
        stage = {"matches": [
            {"id":"m1","competition":"EN1","home":"Arsenal","away":"Chelsea",
             "date":"2026-11-08","cc0Date":"2026-11-07",
             "dateDisagreement":True,"status":"SCHEDULED"},
            {"id":"m2","competition":"EN1","home":"Arsenal","away":"Everton",
             "date":"2026-11-18","cc0Date":"2026-11-18",
             "dateDisagreement":False,"status":"SCHEDULED"}]}
        r = audit_dates(stage)
        self.assertEqual(r["unresolvedCount"],1)
        self.assertEqual(r["byStatus"]["SCHEDULED"],1)
        self.assertIsNone(r["issues"][0]["kickoffVerifiedUTC"])
        self.assertFalse(r["issues"][0]["dateVerified"])

if __name__ == "__main__":
    unittest.main()
