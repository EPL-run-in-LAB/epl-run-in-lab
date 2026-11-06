import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_epl_kickoffs import reconcile

class KickoffReconcileTests(unittest.TestCase):
    def test_conflict_resolved_only_when_third_source_matches(self):
        stage={"status":"STAGING_NOT_MODEL_INPUT","season":"2026-27",
               "matches":[{"id":"a","competition":"EN1","home":"Arsenal FC","away":"Chelsea FC",
                           "date":"2026-11-08","cc0Date":"2026-11-07","dateDisagreement":True}]}
        payload={"matches":[{"id":12345,"utcDate":"2026-11-08T16:00:00Z",
                            "homeTeam":{"name":"Arsenal FC"},"awayTeam":{"name":"Chelsea FC"}}]}
        x=reconcile(stage,payload)
        self.assertEqual(x["coverage"]["STAGING_DATE_CORROBORATED"],1)
        self.assertEqual(x["dateDisagreements"],1)
        self.assertIsNone(x["issues"][0]["timeVerifiedUTC"])
    def test_ambiguous_fixture_not_accepted(self):
        stage={"status":"STAGING_NOT_MODEL_INPUT","season":"2026-27",
               "matches":[{"id":"a","competition":"EN1","home":"Arsenal FC","away":"Chelsea FC",
                           "date":"2026-11-08","cc0Date":"2026-11-07","dateDisagreement":True}]}
        m={"id":12345,"utcDate":"2026-11-08T16:00:00Z",
           "homeTeam":{"name":"Arsenal FC"},"awayTeam":{"name":"Chelsea FC"}}
        x=reconcile(stage,{"matches":[m,dict(m,id=12346)]})
        self.assertEqual(x["coverage"]["UNMATCHED_OR_AMBIGUOUS"],1)
    def test_invalid_season_rejected(self):
        with self.assertRaises(ValueError):
            reconcile({"status":"STAGING_NOT_MODEL_INPUT","season":"2025-26","matches":[]},{"matches":[]})

if __name__=="__main__":
    unittest.main()
