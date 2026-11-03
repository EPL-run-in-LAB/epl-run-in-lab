import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from diagnose_prediction_errors import analyse,group
class DiagnosisTests(unittest.TestCase):
    def test_mean_probability_and_draw(self):
        rows=[{"capturedAt":"2026-10-09T12:00:00Z","date":"2026-10-10","home":"A","away":"B",
          "homeGoals":1,"awayGoals":1,"correctTop1":0,"actualOutcome":"draw",
          "mostLikelyOutcome":"home","brier":.7,"logLoss":1.2,
          "probabilities":{"home":.4,"draw":.3,"away":.3}}]
        d=analyse({"sample":{"eligibleFinalizedFixtures":1},"fixtures":rows,
          "results":{"uniformOneThirdBrier":.666667,"uniformOneThirdLogLoss":1.098612,
          "alwaysPredictHomeAccuracyOnSample":0.0}})
        self.assertEqual(d["byActual"]["draw"]["matches"],1)
        self.assertEqual(d["byTopPick"]["draw"]["matches"],0)
        self.assertEqual(d["calibration"]["draw"]["meanProbability"],.3)
    def test_empty_group_does_not_invent_accuracy(self):
        self.assertIsNone(group([])["accuracy"])
    def test_reject_missing_captures(self):
        with self.assertRaises(ValueError):
            analyse({"sample":{"eligibleFinalizedFixtures":1},"fixtures":[{}]})
if __name__=="__main__":unittest.main()
