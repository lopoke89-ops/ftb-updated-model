"""Contract regression cases from observed November 11 FanDuel labels."""
import unittest
import fanduel_odds as fd
from test_fanduel_odds import payload,runner,FIXTURE,EVENT,ROSTER,STAMP as AT

class ShortLabels(unittest.TestCase):
    def test_observed_short_labels_preserve_exact_market_threshold(self):
        cases=[('TO_SCORE_20+_POINTS','20+ Points','player-points','Player Points','points',20),
               ('3+_MADE_THREES','3+ Threes','player-threes','Player Threes','threes',3),
               ('TO_RECORD_6+_ASSISTS','6+ Assists','player-assists','Player Assists','assists',6),
               ('TO_RECORD_8+_REBOUNDS','8+ Rebounds','player-rebounds','Player Rebounds','rebounds',8)]
        for kind,label,tab,title,market,target in cases:
            with self.subTest(label=label):
                quotes,issues=fd.parse_markets(payload(kind,label,[runner('Player One',line=0)],title),FIXTURE,EVENT,ROSTER,AT,tab)
                self.assertFalse(issues)
                self.assertEqual(len(quotes),1)
                self.assertEqual((quotes[0]['market'],quotes[0]['side'],quotes[0]['line']),(market,'at-least',target))

    def test_short_label_wrong_threshold_or_stat_stays_rejected(self):
        for label in ['15+ Points','20+ Rebounds','20+ Points First Half','Over 20 Points']:
            with self.subTest(label=label):
                quotes,issues=fd.parse_markets(payload('TO_SCORE_20+_POINTS',label,[runner('Player One',line=0)]),FIXTURE,EVENT,ROSTER,AT,'player-points')
                self.assertFalse(quotes)
                self.assertIn('Milestone target/name mismatch',issues)

if __name__=='__main__':unittest.main()
