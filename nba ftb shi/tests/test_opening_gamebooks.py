"""Regression cases from the downloaded official NBA first-quarter pages."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('opening_parser', BASE/'build_opening_gamebook_data.py')
PARSER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PARSER)
FIXTURES = json.loads((BASE/'tests/fixtures/opening_gamebooks.json').read_text(encoding='utf-8'))


def parse(gid, pages=None):
    case = FIXTURES[gid]
    return PARSER.parse_pages(pages or case['pages'], case['game'], case['record'])


class OfficialOpening(unittest.TestCase):
    def test_first_field_goal_and_linked_made_extra_free_throw(self):
        e = parse('401809243')['firstFieldGoals']['OKC']
        self.assertEqual(e['id'], '4433255')
        self.assertEqual(e['points'], 2)
        self.assertTrue(e['andOneAwarded'])
        self.assertEqual((e['andOneAttempts'],e['andOneMade']), (1,1))
        self.assertEqual(e['andOneFreeThrows'][0]['clock'], e['clock'])

    def test_missed_extra_free_throw_still_counts_as_awarded(self):
        e = parse('401809949')['firstFieldGoals']['NOP']
        self.assertTrue(e['andOneAwarded'])
        self.assertEqual((e['andOneAttempts'],e['andOneMade']), (1,0))
        self.assertTrue(e['andOneFreeThrows'][0]['text'].startswith('MISS '))

    def test_special_one_shot_free_throw_does_not_become_and_one(self):
        pages = copy.deepcopy(FIXTURES['401809243']['pages'])
        for page in pages:
            page['text'] = page['text'].replace('C.Holmgren Free Throw 1 of 1', 'C.Holmgren Technical Free Throw 1 of 1')
        e = parse('401809243', pages)['firstFieldGoals']['OKC']
        self.assertFalse(e['andOneAwarded'])

    def test_first_score_and_first_field_goal_remain_independent(self):
        e = parse('401809235')
        self.assertEqual(e['firstScores']['SAS']['shot'], 'ft')
        self.assertEqual(e['firstFieldGoals']['SAS']['id'], '5104157')
        self.assertFalse(e['firstFieldGoals']['SAS']['isFreeThrow'])

    def test_shared_surnames_use_official_quarter_box_evidence(self):
        two = parse('401810178')['firstFieldGoals']['OKC']
        three = parse('401810218')['firstFieldGoals']['OKC']
        self.assertEqual(two['name'], 'Jalen Williams')
        self.assertEqual(three['name'], 'Jaylin Williams')
        self.assertEqual((two['points'], three['points']), (2,3))

    def test_missing_continuation_page_is_rejected(self):
        pages = FIXTURES['401809243']['pages'][:2]
        with self.assertRaisesRegex(ValueError, 'score differs'):
            parse('401809243', pages)

    def test_neutral_site_quarter_boxes_without_home_visitor_prefixes(self):
        e = parse('401809837')
        self.assertEqual(len(e['firstScores']), 2)
        self.assertEqual(len(e['firstFieldGoals']), 2)

    def test_unresolved_missed_attempt_retains_candidates_without_guessing(self):
        e = parse('401810423')
        self.assertTrue(e['firstFieldGoalAttempts']['OKC']['identityUnresolved'])
        self.assertEqual(len(e['firstFieldGoalAttempts']['OKC']['athleteIds']), 2)
        self.assertEqual(len(e['firstFieldGoals']['OKC']['athleteIds']), 1)


if __name__ == '__main__':
    unittest.main()
