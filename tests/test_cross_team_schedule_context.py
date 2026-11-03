import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_cross_team_schedule_context import build
class CrossTeamScheduleTests(unittest.TestCase):
    def test_both_sides_and_unknown_domestic(self):
        matches=[{"id":"a","date":"2026-10-15","competition":"DE1","homeClubId":"de-bayern","awayClubId":"de-berlin","status":"FINISHED"},
                 {"id":"b","date":"2026-10-17","competition":"EN1","homeClubId":"en-arsenal","awayClubId":"en-chelsea","status":"FINISHED"},
                 {"id":"c","date":"2026-10-21","competition":"UCL","homeClubId":"de-bayern","awayClubId":"en-arsenal","home":"Bayern","away":"Arsenal","status":"FINISHED","score":[2,2]},
                 {"id":"d","date":"2026-10-22","competition":"UEL","homeClubId":None,"awayClubId":"en-arsenal","home":"Unknown","away":"Arsenal","status":"FINISHED"}]
        d=build({"status":"STAGING_NOT_MODEL_INPUT","season":"2026-27","matches":matches})
        self.assertEqual(d["coverage"]["uefaFixtures"],2)
        self.assertEqual(d["coverage"]["bothDomesticSchedules"],1)
        self.assertEqual(d["coverage"]["oneDomesticSchedule"],1)
        first=d["fixtures"][0]
        self.assertEqual(first["homeSchedule"]["calendarRestDays"],5)
        self.assertEqual(first["awaySchedule"]["calendarRestDays"],3)
        self.assertIsNone(d["fixtures"][1]["homeSchedule"]["calendarRestDays"])
    def test_disputed_previous_date(self):
        m=[{"id":"a","date":"2026-10-15","competition":"EN1","homeClubId":"X","awayClubId":"Y","status":"FINISHED","dateDisagreement":True},
           {"id":"b","date":"2026-10-20","competition":"UCL","homeClubId":"X","awayClubId":"Y","home":"X","away":"Y","status":"FINISHED"}]
        d=build({"status":"STAGING_NOT_MODEL_INPUT","season":"2026-27","matches":m})
        self.assertIsNone(d["fixtures"][0]["homeSchedule"]["calendarRestDays"])
if __name__=="__main__":unittest.main()
