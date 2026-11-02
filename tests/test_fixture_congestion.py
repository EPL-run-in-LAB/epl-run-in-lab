import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_fixture_congestion import build, utc_verified

def cup(date, ident, t=None, proof=None):
    return dict(id=ident, date=date, competition="UCL", homeRaw="Arsenal",
                awayRaw="Ajax", home="Arsenal", away="Ajax",
                homeClubId="arsenal", awayClubId=None, homeEpl=True,
                awayEpl=False, timeVerifiedUTC=t, timeVerification=proof,
                status="SCHEDULED")

def league(date, opponent, venue="H"):
    return dict(date=date, opponent=opponent, venue=venue)

class CongestionTests(unittest.TestCase):
    def dataset(self, cup_matches, fixtures=None):
        return build({"season":"2026/27","updatedAt":"test","matches":cup_matches},
                     {"asOf":"test","games":{"Arsenal": fixtures or []}})

    def test_calendar_rest_and_rolling_windows(self):
        d = self.dataset([cup("2026-11-04", "cup-1")],
                         [league("2026-11-01","Chelsea"), league("2026-11-07","Chelsea")])
        m = d["teams"]["arsenal"]["matches"]
        self.assertEqual([x["calendarRestDays"] for x in m], [None, 2, 2])
        self.assertEqual([x["gamesIn7Days"] for x in m], [1, 2, 3])
        self.assertEqual(m[1]["restBasis"], "calendar_date")

    def test_automatic_upgrade_only_with_verified_provenance(self):
        a = cup("2026-11-01","c1","2026-11-01T20:00:00Z",
                {"status":"verified","source":"official-fixture-id-1"})
        b = cup("2026-11-04","c2","2026-11-04T18:00:00Z",
                {"status":"verified","source":"official-fixture-id-2"})
        d = self.dataset([a,b])
        matches=d["teams"]["arsenal"]["matches"]
        self.assertEqual(matches[1]["kickoffGapHours"],70.0)
        self.assertEqual(matches[1]["restBasis"],"verified_kickoff")
        b["timeVerification"]={"status":"unverified","source":"raw-csv"}
        d = self.dataset([a,b])
        self.assertIsNone(d["teams"]["arsenal"]["matches"][1]["kickoffGapHours"])

    def test_stale_epl_membership_recomputed(self):
        m = dict(cup("2026-11-01","west-ham"),homeRaw="West Ham United",
                 awayRaw="Ipswich Town",homeEpl=True,awayEpl=False)
        result=self.dataset([m])
        self.assertEqual(len(result["teams"]["ipswich"]["matches"]),1)
        self.assertEqual(len(result["teams"]["arsenal"]["matches"]),0)
        self.assertNotIn("west-ham",result["teams"])

    def test_invalid_utc_does_not_upgrade(self):
        m=cup("2026-11-04","c1","2026-11-04T20:00:00",
              {"status":"verified","source":"trusted"})
        self.assertIsNone(utc_verified(m))

if __name__ == "__main__":
    unittest.main()
