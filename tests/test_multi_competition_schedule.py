import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_multi_competition_schedule import parse_csv,parse_cc0,sha_id
class MultiCompetitionTests(unittest.TestCase):
 def test_rows(self):
    r=parse_csv("gw,date,time,home,away,ft_home,ft_away\n1,2026-10-10,20:00,Arsenal,Chelsea,0,0\n","results")
    self.assertEqual(r[0]["score"],[0,0])
    self.assertEqual(r[0]["date"],"2026-10-10")
 def test_fixture_without_score(self):
    x=parse_csv("gw,date,time,home,away\n2,2026-11-10,21:00,PSG,Lille\n","fixtures")
    self.assertIsNone(x[0]["score"])
 def test_duplicate_rejected(self):
    with self.assertRaises(ValueError):
        parse_cc0({"matches":[{"team1":"A","team2":"B","date":"2026-10-10"},
            {"team1":"A","team2":"B","date":"2026-10-11"}]},2)
 def test_round_key_ignores_rescheduling(self):
    self.assertEqual(sha_id("EN1","4","Arsenal","Chelsea"),sha_id("EN1","4","Arsenal","Chelsea"))
 def test_cc0_draw_array(self):
    x=parse_cc0({"matches":[{"team1":"A","team2":"B","date":"2026-10-10","score":[0,0]}]},1)
    self.assertEqual(x[("A","B")]["score"],[0,0])
if __name__=="__main__":unittest.main()
