"""Unit tests for domestic/UEFA descriptive match statistics."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_team_competition_analysis import add, empty, combine, metrics
class ComparisonTests(unittest.TestCase):
    def test_points_and_winrate(self):
        s=empty()
        add(s,3,0);add(s,0,0);add(s,1,2)
        r=metrics(s)
        self.assertEqual(r["points"],4)
        self.assertEqual(r["ppg"],1.333)
        self.assertEqual(r["winPct"],33.33)
        self.assertEqual(r["gd"],2)
    def test_empty(self):
        self.assertIsNone(metrics(empty())["ppg"])
    def test_seasons_merge(self):
        a=empty();b=empty()
        add(a,2,0);add(b,0,0)
        self.assertEqual(metrics(combine([a,b]))["ppg"],2.0)
    def test_invalid_scores(self):
        for gf,ga in ((None,1),(-1,1),(0.0,1)):
            with self.assertRaises(ValueError):add(empty(),gf,ga)
if __name__=="__main__":
    unittest.main()
