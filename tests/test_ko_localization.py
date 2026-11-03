"""Protect display-only localization from altering team IDs or JavaScript."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_i18n import localize_korean_visible_team_names

class ClubLabelsTests(unittest.TestCase):
    def test_visible_club_names_localized(self):
        source = '<h1>Tottenham vs Everton</h1><td>Leeds United</td><p>Manchester City and Nottingham Forest</p>'
        out = localize_korean_visible_team_names(source)
        self.assertIn('<h1>토트넘 vs 에버튼</h1>', out)
        self.assertIn('<td>리즈</td>', out)
        self.assertIn('맨시티 and 노팅엄', out)

    def test_html_attributes_script_and_style_are_untouched(self):
        source = ('<a href="/teams/Everton/" title="Leeds United">Everton</a>'
                  '<script>let team="Everton";</script>'
                  '<style>.Everton{color:red}</style>')
        out = localize_korean_visible_team_names(source)
        self.assertIn('href="/teams/Everton/"', out)
        self.assertIn('title="Leeds United"', out)
        self.assertIn('>에버튼</a>', out)
        self.assertIn('let team="Everton"', out)
        self.assertIn('.Everton{color:red}', out)

if __name__ == "__main__":
    unittest.main()
