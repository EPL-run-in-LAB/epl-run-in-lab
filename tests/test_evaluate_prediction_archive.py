import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from evaluate_prediction_archive import evaluate, classify

def entry(home, away, hg, ag, p, before=True):
    s={"home":home,"away":away,"capturedAt":"2026-10-01T00:00:00Z" if before else "2026-10-12T00:00:00Z",
       "utcDate":"2026-10-10T12:00:00Z","date":"2026-10-10",
       "homeWin":p[0],"draw":p[1],"awayWin":p[2]}
    return {"status":"FINISHED","snapshot":s,"result":{"homeGoals":hg,"awayGoals":ag}}

class ArchiveAccuracyTests(unittest.TestCase):
    def test_simple_accuracy_and_points(self):
        rows={"matches":{"1":entry("Arsenal","Chelsea",2,0,[0.6,0.2,0.2]),
                         "2":entry("Bayern","Arsenal",1,1,[0.3,0.4,0.3])}}
        out=evaluate(rows)
        self.assertEqual(out["sample"]["eligibleFinalizedFixtures"],2)
        self.assertEqual(out["results"]["top1Correct"],2)
        self.assertEqual(out["results"]["top1Accuracy"],1.0)
        arsenal=next(x for x in out["teamRecords"] if x["team"]=="Arsenal")
        self.assertEqual(arsenal["actualPoints"],4)
        self.assertEqual(arsenal["expectedPoints"],3.3)

    def test_future_or_post_kickoff_excluded(self):
        rec=entry("A","B",2,1,[0.5,0.3,0.2],before=False)
        self.assertEqual(classify(rec)[1],"not_frozen_before_kickoff")
        future=entry("C","D",0,0,[0.3,0.4,0.3]);future.pop("result");future["status"]="SNAPSHOT"
        out=evaluate({"matches":{"1":entry("E","F",0,1,[0.2,0.2,0.6]),"2":rec,"3":future}})
        self.assertEqual(out["sample"]["eligibleFinalizedFixtures"],1)
        self.assertEqual(out["sample"]["excludedReasons"]["not_frozen_before_kickoff"],1)
        self.assertEqual(out["sample"]["excludedReasons"]["not_finished"],1)

    def test_bad_probabilities_rejected(self):
        rec=entry("A","B",0,0,[0.5,0.5,0.5])
        self.assertEqual(classify(rec)[1],"not_normalized")

if __name__=="__main__":
    unittest.main()
