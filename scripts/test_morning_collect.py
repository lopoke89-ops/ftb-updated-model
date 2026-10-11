import copy
import hashlib
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import archive_store
import morning_collect as collect
import official_gamebooks as boxes
import build_pages as pages
from test_pages_build import temporary_output

FIXTURES = Path(__file__).parent / 'fixtures'
GAME = archive_store.read(FIXTURES / 'probe_game.json')
RECORD = archive_store.read(FIXTURES / 'probe_record.json')
QUARTERS = archive_store.read(collect.SOURCE / 'tests/fixtures/opening_gamebooks.json')


class FakeArchive:
    def content_file(self, path, runtime, season, day):
        if not Path(path).is_file():
            raise AssertionError('Attempted to archive a missing file')
        return 'https://github.com/example/data/releases/download/test/' + Path(path).name


def event(day, gid='401809243', completed=True, phase=2, status='Final'):
    return {'id':gid,'date':day+'T23:00Z','season':{'year':2027,'type':phase},
            'status':{'type':{'completed':completed,'description':status}},
            'competitions':[{'competitors':[{'homeAway':side,'team':{'abbreviation':GAME[side]},'score':GAME['teams'][GAME[side]]['points']}
                                           for side in ('home','away')]}]}


def fake_ingest(f, state, fetcher, store, force=False):
    g = {**copy.deepcopy(GAME),**f}
    g['teams'] = copy.deepcopy(GAME['teams'])
    record = copy.deepcopy(RECORD)
    text = (FIXTURES/'final_box.txt').read_text(encoding='utf-8')
    record['team_totals'] = boxes.printed_totals(text,g)
    record.update(espn_game_id=f['id'],game_date=f['date'],season=collect.SEASON,
                  archiveUrl='https://github.com/example/data/releases/download/test/book.pdf')
    quarter = QUARTERS[GAME['id']]
    events = collect.opening.parse_pages(quarter['pages'],GAME,quarter['record'])
    for name in ('records','text/final_boxes'):
        (state/'library'/name).mkdir(parents=True,exist_ok=True)
    archive_store.save(state/'library/records'/(f['id']+'.json'),record)
    target = state/'library'/record['final_box_text_path']
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text,encoding='utf-8')
    return collect.official_game(g,record,events)


def new_source(folder):
    source = folder/'source'
    shutil.copytree(collect.SOURCE/'seasons/2026-27',source/'seasons/2026-27')
    return source


class MorningCollection(unittest.TestCase):
    def test_postgame_roles_require_same_game_five_pdf_starters_and_never_confirm_pregame(self):
        game = copy.deepcopy(GAME)
        for team, box in game['teams'].items():
            for i, p in enumerate(box['players']):
                p['starter'] = i < 5
        sides = {}
        for side in ('home', 'away'):
            team = game[side]
            starters = [p for p in game['teams'][team]['players'] if p['starter']]
            sides[side+'Team'] = dict(teamAbbreviation=team, players=[dict(personId=i+1, playerName=p['name'], position=position,
                lineupStatus='Confirmed', rosterStatus='Active') for i, (p, position) in enumerate(zip(starters, ('PG','SG','SF','PF','C')))])
        payload = {'games':[dict(gameStatus=3, **sides)]}
        roles = collect.dated_lineup_roles(game, payload, 'official-url', 'captured-time')
        self.assertEqual(len(roles), 10)
        self.assertTrue(all(r['effectiveGameDate'] == game['date'] and 'not pregame' in r['status'] for r in roles))
        result, _ = collect.payload_for([{**game, 'roleEvidence':roles, 'opening':{}, 'firstScores':{}, 'firstFieldGoals':{}, 'source':'official', 'sourceHash':'hash'}], {})
        self.assertEqual(result['datedRoleEvidence'], roles)
        payload['games'][0]['homeTeam']['players'][0]['playerName'] = 'Unknown Person'
        self.assertEqual(len(collect.dated_lineup_roles(game, payload, 'official-url', 'captured-time')), 5)
        payload['games'][0]['gameStatus'] = 1
        self.assertEqual(collect.dated_lineup_roles(game, payload, 'official-url', 'captured-time'), [])

    def test_unicode_hashes_match_season_and_supplement_contracts(self):
        value = {'name':'Nikola Jokić'}
        expected = hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(collect.digest(value,True),expected)
        self.assertEqual(collect.digest(value),pages.digest_value(value))

    def test_pdf_printed_totals_are_independent_of_espn(self):
        g = copy.deepcopy(GAME)
        g['teams'][g['home']]['points'] += 10
        text = (FIXTURES/'final_box.txt').read_text(encoding='utf-8')
        totals = boxes.printed_totals(text,g)
        self.assertEqual(totals[g['home']]['pts'],GAME['teams'][g['home']]['points'])
        authority = {**g,'teams':{t:{**b,'points':totals[t]['pts']} for t,b in g['teams'].items()}}
        rows, issues = boxes.parse_final_box(text,authority,{})
        self.assertFalse(issues)
        self.assertEqual(sum(r['pts'] for r in rows if r['played'] and r['team']==g['home']),totals[g['home']]['pts'])

    def test_incomplete_printed_totals_fail(self):
        with self.assertRaisesRegex(ValueError,'Both printed'):
            boxes.printed_totals('VISITOR: Oklahoma City Thunder',GAME)

    def test_success_builds_full_nba_rows_openings_and_database(self):
        with temporary_output() as folder:
            source = new_source(folder)
            state = folder/'state'
            fetcher = lambda url:{'events':[event('2026-10-20')]}
            result = collect.collect(state,source,'2026-10-20',fetcher=fetcher,store=FakeArchive(),ingester=fake_ingest)
            self.assertEqual(result['pending'],0)
            manifest = archive_store.read(source/'seasons/2026-27/manifest.json')
            payload = archive_store.read(source/'seasons/2026-27/versions'/manifest['activeVersion'])
            self.assertEqual(manifest['totalGames'],1)
            self.assertTrue(manifest['collection']['targetComplete'])
            self.assertEqual(manifest['collection']['databaseChecks']['integrity_check'],'ok')
            self.assertTrue(payload['parlay']['openingEvidence']['games'][GAME['id']]['firstFieldGoals'][GAME['home']]['andOneAwarded'])
            row = next(r for r in payload['games'][0]['teams'][GAME['home']]['players'] if r['played'])
            self.assertTrue(all(row[k] is not None for k in collect.FIELDS))
            self.assertEqual(collect.digest(payload['games'],True),manifest['evidenceContentHash'])

    def test_completed_batch_skips_network_and_ingestion(self):
        with temporary_output() as folder:
            source = new_source(folder)
            state = folder/'state'
            collect.collect(state,source,'2026-10-20',fetcher=lambda url:{'events':[]},store=FakeArchive())
            status = archive_store.read(state/'state.json')
            status['publishedKey'] = status['readyKey']
            archive_store.save(state/'state.json',status)
            with patch.object(collect,'fetch_json',side_effect=AssertionError('network')):
                result = collect.collect(state,source,'2026-10-20',fetcher=lambda url:self.fail('network'))
            self.assertTrue(result['skipped'])
            self.assertFalse(result['publish_needed'])

    def test_missing_pdf_is_retained_then_retried_next_morning(self):
        with temporary_output() as folder:
            source = new_source(folder)
            state = folder/'state'
            schedule = lambda url:{'events':[event('2026-10-20')]}
            def unavailable(*args,**kwargs):raise ValueError('NBA PDF not available')
            first = collect.collect(state,source,'2026-10-20',fetcher=schedule,store=FakeArchive(),ingester=unavailable)
            self.assertEqual(first['pending'],1)
            self.assertEqual(archive_store.read(source/'seasons/2026-27/manifest.json')['totalGames'],0)
            second = collect.collect(state,source,'2026-10-21',fetcher=schedule,store=FakeArchive(),ingester=fake_ingest)
            self.assertEqual(second['pending'],0)
            self.assertEqual(second['verified_games'],1)
            status = archive_store.read(state/'state.json')
            self.assertTrue(status['batches']['2026-10-20']['complete'])

    def test_failed_schedule_is_not_a_confirmed_empty_day(self):
        with temporary_output() as folder:
            def fail(url):raise OSError('source unavailable')
            source = new_source(folder)
            result = collect.collect(folder/'state',source,'2026-10-20',fetcher=fail,store=FakeArchive())
            self.assertEqual(result['schedule_errors'],1)
            health = archive_store.read(source/'seasons/2026-27/manifest.json')
            self.assertFalse(health['collection']['targetComplete'])
            self.assertEqual(health['totalGames'],0)

    def test_preseason_postponed_and_canceled_do_not_require_pdfs(self):
        with temporary_output() as folder:
            events = [event('2026-10-20','1',phase=1),event('2026-10-20','2',completed=False,status='Postponed'),
                      event('2026-10-20','3',completed=False,status='Canceled')]
            result = collect.collect(folder/'state',new_source(folder),'2026-10-20',fetcher=lambda url:{'events':events},
                                     store=FakeArchive(),ingester=lambda *a,**k:self.fail('excluded fixture'))
            self.assertEqual(result['pending'],0)

    def test_late_unfinished_game_is_pending(self):
        with temporary_output() as folder:
            result = collect.collect(folder/'state',new_source(folder),'2026-10-20',
                fetcher=lambda url:{'events':[event('2026-10-20',completed=False,status='In Progress')]},store=FakeArchive())
            self.assertEqual(result['pending'],1)

    def test_repeat_collection_does_not_duplicate_games(self):
        with temporary_output() as folder:
            state, source = folder/'state',new_source(folder)
            kwargs = dict(fetcher=lambda url:{'events':[event('2026-10-20')]},store=FakeArchive(),ingester=fake_ingest)
            collect.collect(state,source,'2026-10-20',**kwargs)
            result = collect.collect(state,source,'2026-10-20',force=True,**kwargs)
            self.assertEqual(result['verified_games'],1)

    def test_failed_new_game_preserves_verified_history(self):
        with temporary_output() as folder:
            state, source = folder/'state',new_source(folder)
            collect.collect(state,source,'2026-10-20',fetcher=lambda url:{'events':[event('2026-10-20')]},store=FakeArchive(),ingester=fake_ingest)
            def fail(*a,**k):raise ValueError('bad PDF')
            result = collect.collect(state,source,'2026-10-21',fetcher=lambda url:{'events':[event('2026-10-21','bad')]},store=FakeArchive(),ingester=fail)
            self.assertEqual(result['verified_games'],1)
            self.assertEqual(result['pending'],1)

    def test_restore_rejects_unsafe_season_version(self):
        with temporary_output() as folder:
            archive_store.save(folder/'state/seasons/2026-27/manifest.json',{'activeVersion':'../../private.json'})
            with self.assertRaisesRegex(ValueError,'Unsafe'):
                archive_store.overlay(folder/'state',folder/'source')

    def test_fixture_dates_follow_chicago_across_dst(self):
        e = event('2026-10-20')
        e['date']='2026-10-21T04:30Z'
        self.assertEqual(collect.fixture(e)['date'],'2026-10-20')
        e['date']='2026-11-02T05:30Z'
        self.assertEqual(collect.fixture(e)['date'],'2026-11-01')
        e['date']='2026-11-02T06:30Z'
        self.assertEqual(collect.fixture(e)['date'],'2026-11-02')

    def checked_snapshot(self,folder):
        source=new_source(folder)
        collect.collect(folder/'state',source,'2026-10-20',fetcher=lambda url:{'events':[event('2026-10-20')]},store=FakeArchive(),ingester=fake_ingest)
        return source

    def test_nonempty_collected_season_passes_full_publication_validation(self):
        with temporary_output() as folder:
            source=self.checked_snapshot(folder)
            original=pages.read
            def read_with_current(path):
                if path.is_relative_to(pages.SOURCE/'seasons/2026-27'):
                    return original(source/path.relative_to(pages.SOURCE))
                return original(path)
            with patch.object(pages,'read',side_effect=read_with_current):
                _,current,_=pages.validate(pages.SOURCE)
                self.assertEqual(len(current['games']),1)
                manifest=pages.build(output=folder/'site')
                self.assertEqual(manifest['currentSeasonGames'],1)
                self.assertTrue((folder/'site/data/seasons/2026-27.json').exists())

    def test_tampered_current_shooting_is_rejected(self):
        with temporary_output() as folder:
            source=self.checked_snapshot(folder)
            original=pages.read
            def altered(path):
                if path.is_relative_to(pages.SOURCE/'seasons/2026-27'):
                    data=original(source/path.relative_to(pages.SOURCE))
                    if 'games' in data:
                        next(iter(next(iter(data['parlay']['games'].values())).values())).clear()
                    return data
                return original(path)
            with patch.object(pages,'read',side_effect=altered),self.assertRaisesRegex(ValueError,'Current shooting hash'):
                pages.validate(pages.SOURCE)

    def test_completed_but_unpublished_batch_requests_publication_again(self):
        with temporary_output() as folder:
            source=new_source(folder)
            state=folder/'state'
            collect.collect(state,source,'2026-10-20',fetcher=lambda url:{'events':[]},store=FakeArchive())
            result=collect.collect(state,source,'2026-10-20',fetcher=lambda url:self.fail('unneeded download'))
            self.assertTrue(result['publish_needed'])


if __name__=='__main__':unittest.main()
