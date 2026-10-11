import unittest
import backfill_parlay_roles as roles


class RoleMatchingTests(unittest.TestCase):
    def setUp(self):
        self.game = {'id': 'espn', 'date': '2026-01-01', 'home': 'AAA', 'away': 'BBB', 'sourceHash': 'pdfhash',
                     'teams': {t: {'players': [{'id': t+str(i), 'name': t+' Player '+str(i), 'played': True, 'starter': True} for i in range(5)]} for t in ['AAA', 'BBB']}}
        self.payload = {'games': [{'gameId': 'nba', 'gameStatus': 3, **{s: {'teamAbbreviation': t, 'players': [
            {'personId': 100+i, 'playerName': t+' Player '+str(i), 'position': p, 'lineupStatus': 'Confirmed', 'rosterStatus': 'Active'}
            for i, p in enumerate(['PG', 'SG', 'SF', 'PF', 'C'])]} for s, t in [('homeTeam', 'AAA'), ('awayTeam', 'BBB')]}}]}

    def match(self):
        return roles.match_roles(self.game, self.payload, 'source', 'hash', 'capture')

    def test_complete_pdf_starters_are_required_on_each_side(self):
        self.assertEqual(len(self.match()), 10)
        self.game['teams']['AAA']['players'][0]['starter'] = False
        found = self.match()
        self.assertEqual(len(found), 5)
        self.assertTrue(all(r['team'] == 'BBB' for r in found))

    def test_identity_mismatch_rejects_the_entire_team(self):
        self.payload['games'][0]['homeTeam']['players'][0]['playerName'] = 'Different player'
        self.assertEqual(len(self.match()), 5)

    def test_expected_and_nonfinal_lineups_cannot_become_historical_role_evidence(self):
        self.payload['games'][0]['homeTeam']['players'][0]['lineupStatus'] = 'Expected'
        self.assertEqual(len(self.match()), 5)
        self.payload['games'][0]['gameStatus'] = 1
        self.assertEqual(self.match(), [])

    def test_evidence_preserves_stable_ids_and_both_sources(self):
        r = self.match()[0]
        self.assertEqual(r['gameId'], 'espn')
        self.assertEqual(r['nbaGameId'], 'nba')
        self.assertEqual(r['gamebookSourceHash'], 'pdfhash')
        self.assertEqual(r['sourceHash'], 'hash')
        self.assertEqual(r['effectiveGameDate'], self.game['date'])


if __name__ == '__main__':
    unittest.main()
