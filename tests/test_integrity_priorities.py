import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_match_archive import find_result, match_date
from enrich_schedule_integrity import audit_dates, collect

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


class ExtendedLeagueTests(unittest.TestCase):
    @staticmethod
    def rows(count=18):
        clubs = [f"Club-{i:02d}" for i in range(count)]
        lines = ["gw,date,time,home,away"]
        for i,h in enumerate(clubs):
            for j,a in enumerate(clubs):
                if i != j:
                    lines.append(f"1,2026-12-01,20:00,{h},{a}")
        return "\\n".join(lines).replace("\\n", "\n") + "\n"
    def test_complete_league_and_unknown_clubs(self):
        class Response:
            def __init__(self,body): self.text=body
            def raise_for_status(self): pass
        class Session:
            def __init__(self, body): self.body=body
            def get(self,url,timeout=35):
                if "/results_" in url: return Response("gw,date,time,home,away,ft_home,ft_away\n")
                return Response(self.body)
        fixtures, coverage = collect(Session(self.rows()), {"other": {}}, "2026-11-04")
        self.assertEqual(coverage["NL1"]["count"],306)
        self.assertEqual(coverage["PT1"]["count"],306)
        self.assertEqual(len(fixtures),612)
        self.assertTrue(all(m["kickoffUTC"] is None for m in fixtures))
        self.assertTrue(all(m["dateAuditStatus"] == "SINGLE_SOURCE_PROVISIONAL" for m in fixtures))
        self.assertTrue(all(m["homeClubId"] and m["awayClubId"] for m in fixtures))
    def test_incomplete_leagues_quarantined(self):
        class Response:
            def __init__(self,body):self.text=body
            def raise_for_status(self):pass
        class Session:
            def get(self,url,timeout=35):
                if "/results_" in url:return Response("gw,date,time,home,away,ft_home,ft_away\n")
                return Response("gw,date,time,home,away\n1,2026-12-01,20:00,A,B\n")
        fixtures, coverage = collect(Session(), {"other": {}}, "2026-11-04")
        self.assertEqual(fixtures, [])
        self.assertEqual(coverage["NL1"]["status"],"INCOMPLETE_QUARANTINED")

if __name__ == "__main__":
    unittest.main()
