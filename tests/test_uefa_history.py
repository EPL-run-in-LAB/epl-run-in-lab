"""Offline parsing tests for CC0 UEFA football.txt tournament files."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_uefa_history import parse_football_txt, parse_result, source_key

class UEFAParserTests(unittest.TestCase):
    def test_regulation_aet_penalties_are_not_mixed(self):
        self.assertEqual(parse_result("5-4 pen. 1-1 a.e.t. (1-1, 0-0)"),
            {"status":"FINISHED","regulation":[1,1],"afterExtra":[1,1],"penalties":[5,4]})
        self.assertEqual(parse_result("2-3 a.e.t. (1-3, 0-1)"),
            {"status":"FINISHED","regulation":[1,3],"afterExtra":[2,3],"penalties":None})
        self.assertEqual(parse_result("0-0"),
            {"status":"FINISHED","regulation":[0,0],"afterExtra":None,"penalties":None})
        self.assertEqual(parse_result("[cancelled]"),
            {"status":"CANCELLED","regulation":None,"afterExtra":None,"penalties":None})

    def test_date_inference_and_source_count(self):
        src="""= Test
# Matches    3
▪ Group A
  Tue Sep 14 2021
    21:00  Arsenal FC (ENG) v Bayern München (GER) 0-0
  Thu Feb 17
    21:00  Bayern München (GER) v Arsenal FC (ENG) 5-4 pen. 1-1 a.e.t. (1-1, 0-0)
▪ Knockouts
  Thu Mar 3
    RB Leipzig (GER) v Spartak Moskva (RUS) [cancelled]
"""
        ms=parse_football_txt(src,"2021-22","UEL")
        self.assertEqual(len(ms),3)
        self.assertEqual(ms[0]["date"],"2021-09-14")
        self.assertEqual(ms[1]["date"],"2022-02-17")
        self.assertEqual(ms[2]["status"],"CANCELLED")
        self.assertEqual(ms[2]["stage"],"Knockouts")
        self.assertNotEqual(source_key("UEL","2021-22",ms[0]),source_key("UEL","2021-22",ms[1]))

    def test_header_mismatch_quarantined(self):
        with self.assertRaisesRegex(ValueError,"mismatch"):
            parse_football_txt("# Matches    2\n▪ Group\nTue Sep 14 2021\n"+
                "Arsenal FC (ENG) v Bayern München (GER) 1-0", "2021-22","UCL")

    def test_unknown_score_rejected(self):
        with self.assertRaises(ValueError):
            parse_result("3-2 pen. 2-1")  # incomplete, do not invent 90-minute score

if __name__=="__main__":
    unittest.main()
