"""Offline tests for the independently built CC0 match warehouse."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_history_warehouse import build_warehouse, stable_match_id, club_slug, canonical_name

class TestHistoryWarehouse(unittest.TestCase):
    def test_stable_match_id_and_club_slug(self):
        self.assertEqual(club_slug("FC Bayern München"), "fc-bayern-munchen")
        self.assertEqual(
            stable_match_id("DE1", "2025-26", "de-fc-bayern-munchen", "de-rb-leipzig"),
            stable_match_id("DE1", "2025-26", "de-fc-bayern-munchen", "de-rb-leipzig")
        )

    def test_reviewed_club_aliases(self):
        self.assertEqual(canonical_name("FR", "Paris Saint-Germain FC"), "Paris Saint-Germain")
        self.assertEqual(canonical_name("DE", "Bayern München"), "FC Bayern München")
        self.assertEqual(canonical_name("IT", "Inter"), "FC Internazionale Milano")
        self.assertEqual(canonical_name("ES", "Atlético Madrid"), "Club Atlético de Madrid")
        self.assertEqual(canonical_name("EN", "Arsenal"), "Arsenal FC")
        self.assertEqual(canonical_name("EN", "Tottenham Hotspur"), "Tottenham Hotspur FC")
        self.assertEqual(canonical_name("FR", "Unknown FC"), "Unknown FC")

    def write_sample(self, root, matches):
        directory = root / "snapshots" / "2025-26"
        directory.mkdir(parents=True)
        source = {
            "schemaVersion": 1, "competitionId": "DE1", "country": "DE",
            "season": "2025-26",
            "source": {"project": "openfootball/football.json", "license": "CC0-1.0",
                       "commit": "a"*40, "url": "https://example.org/de.json"},
            "matches": matches,
        }
        (directory / "DE1.json").write_text(json.dumps(source), encoding="utf-8")
        return root / "snapshots"

    def test_warehouse_status_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                {"date":"2025-08-22","round":"Round 1","home":"FC Bayern München",
                 "away":"RB Leipzig","score":[6,0],"origin":"cc0_json_ft"},
                {"date":"2025-08-23","round":"Round 1","home":"Borussia Dortmund",
                 "away":"St. Pauli","score":[0,0],"origin":"cc0_json_array"}
            ]
            source = self.write_sample(root, rows)
            report = build_warehouse(source, root/"history.sqlite", root/"report.json", strict=False)
            self.assertEqual(report["totals"]["matches"], 2)
            with sqlite3.connect(root/"history.sqlite") as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT SUM(home_goals + away_goals) FROM matches").fetchone()[0], 6)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM match_provenance").fetchone()[0], 2)

    def test_duplicate_match_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            match = {"date":"2025-08-22","home":"FC Bayern München","away":"RB Leipzig",
                     "score":[6,0],"origin":"cc0_json_ft"}
            source = self.write_sample(root, [match, dict(match,date="2025-09-22")])
            with self.assertRaises(sqlite3.IntegrityError):
                build_warehouse(source, root/"history.sqlite", root/"report.json", strict=False)

    def test_reject_unapproved_license(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_sample(root, [])
            path = source/"2025-26"/"DE1.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["source"]["license"] = "noncommercial"
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_warehouse(source, root/"history.sqlite", root/"report.json", strict=False)

    def test_awarded_match_not_training_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_sample(root, [{
                "date":"2026-05-17","home":"FC Nantes","away":"Toulouse FC",
                "score":[0,0],"origin":"official_decision",
                "status":"ABANDONED_AWARDED","modelTrainingEligible":False,
                "scoreEvidence":"https://ligue1.com/fr/articles/example"}])
            # Synthetic fixture in DE1, with training exclusion verified independently.
            build_warehouse(source, root/"history.sqlite", root/"report.json", strict=False)
            with sqlite3.connect(root/"history.sqlite") as con:
                self.assertEqual(con.execute("SELECT model_training_eligible FROM matches").fetchone()[0], 0)

if __name__ == "__main__":
    unittest.main()
