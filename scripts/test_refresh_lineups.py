import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from subprocess import CompletedProcess
import refresh_lineups as feed


class LineupBridge(unittest.TestCase):
    def test_advance_depth_capture_keeps_source_order_season_and_real_capture_time(self):
        now=datetime(2026,10,18,22,tzinfo=timezone.utc)
        event={'id':'future','date':'2026-10-20T23:00Z','season':{'year':2027},'status':{'type':{'state':'pre'}},'competitions':[{'competitors':[{'team':{'abbreviation':'BOS'}}]}]}
        payload={'team':{'id':'2'},'season':{'year':2027},'timestamp':'2026-10-18T20:00Z','depthchart':[{'positions':{p:{'athletes':[{'id':str(i),'displayName':'Player','injuries':[]}]} for i,p in enumerate(('pg','sg','sf','pf','c'))}}]}
        result=feed.capture_projections(now,lambda url:payload if 'depthcharts' in url else {'events':[event]},2)
        self.assertEqual(result['checkedThrough'],'2026-10-20')
        entry=result['teams']['BOS']
        self.assertEqual(entry['source'],feed.depth_url('BOS'))
        self.assertEqual(entry['payload']['timestamp'],payload['timestamp'])
        self.assertEqual(entry['payload']['depthchart'][0]['positions']['pg']['athletes'][0]['id'],'0')
        self.assertIsNotNone(datetime.fromisoformat(entry['capturedAt']))

    def test_wrong_season_depth_chart_is_withheld(self):
        event={'id':'future','date':'2026-10-20T23:00Z','season':{'year':2027},'status':{'type':{'state':'pre'}},'competitions':[{'competitors':[{'team':{'abbreviation':'BOS'}}]}]}
        result=feed.capture_projections(datetime(2026,10,18,tzinfo=timezone.utc),lambda url:{'team':{'id':'2'},'season':{'year':2026}} if 'depthcharts' in url else {'events':[event]},1)
        self.assertFalse(result['teams']);self.assertTrue(any('season mismatch' in e for e in result['errors']))

    def test_watch_worker_polls_after_a_source_failure_and_hands_off_at_deadline(self):
        start=datetime(2026,10,20,22,tzinfo=timezone.utc)
        elapsed=[0];sleeps=[];published=[];nba_calls=[0]
        event={'id':'match','date':'2026-10-20T23:00Z','status':{'type':{'state':'pre'}}}
        def fetch(url):
            if 'scoreboard' in url:return {'events':[event]}
            nba_calls[0]+=1
            if nba_calls[0]==1:raise OSError('temporary source failure')
            return {'games':[]}
        def sleep(seconds):sleeps.append(seconds);elapsed[0]+=seconds
        with patch.object(feed,'capture_projections',return_value={'teams':{},'errors':[]}):
            failed=feed.run(True,11,1,fetch,published.append,lambda:start+timedelta(seconds=elapsed[0]),lambda:elapsed[0],sleep)
        self.assertFalse(failed)
        self.assertEqual(sleeps,[300,300]);self.assertEqual(nba_calls[0],3);self.assertEqual(len(published),2)

    def test_projection_publish_preserves_the_existing_official_capture(self):
        trees=[]
        def git(*args,data=None,check=True):
            output=b''
            if args[0]=='hash-object':output=b'new-projection-blob\n'
            if args[0]=='rev-parse':output=b'old-parent\n'
            if args[0]=='ls-tree':output=b'100644 blob official-blob\tlive-lineups.json\n'
            if args[0]=='mktree':
                self.assertIn('--missing',args,'partial checkout does not contain the unchanged remote cache blob')
                trees.append(data);output=b'new-tree\n'
            if args[0]=='commit-tree':output=b'new-commit\n'
            return CompletedProcess(args,0,output,b'')
        with patch.object(feed,'git',side_effect=git):
            self.assertEqual(feed.publish({feed.PROJECTIONS:{'schemaVersion':1}}),'new-commit')
        self.assertIn(b'official-blob\tlive-lineups.json',trees[0]);self.assertIn(b'new-projection-blob\tprojected-lineups.json',trees[0])

    def test_official_source_failure_does_not_drop_successful_projection_capture(self):
        now=datetime(2026,10,20,22,tzinfo=timezone.utc)
        event={'id':'match','date':'2026-10-20T23:00Z','status':{'type':{'state':'pre'}}}
        def fetch(url):
            if 'scoreboard' in url:return {'events':[event]}
            raise OSError('NBA source unavailable')
        records=[]
        with patch.object(feed,'capture_projections',return_value={'teams':{'BOS':{}},'errors':[]}):
            feed.run(False,1,1,fetch,records.append,lambda:now)
        self.assertEqual(len(records),1);self.assertEqual(set(records[0]),{feed.PROJECTIONS})

    def test_publication_failure_returns_a_failed_run_instead_of_false_success(self):
        now=datetime(2026,10,18,22,tzinfo=timezone.utc)
        def fail(records):raise RuntimeError('publication unavailable')
        with patch.object(feed,'capture_projections',return_value={'teams':{'BOS':{}},'errors':[]}):
            failed=feed.run(False,1,1,lambda url:{'events':[]},fail,lambda:now)
        self.assertTrue(failed)

    def test_only_pregame_fixtures_within_two_hours_trigger_nba_request(self):
        now=datetime(2026,10,20,22,tzinfo=timezone.utc)
        event={'id':'match','date':'2026-10-20T23:00Z','status':{'type':{'state':'pre'}}}
        calls=[]
        def fetch(url):
            calls.append(url)
            return {'events':[event]} if 'scoreboard' in url else {'games':[]}
        record=feed.capture(now,fetch)
        self.assertEqual(record['date'],'2026-10-20')
        self.assertEqual(record['activeFixtures'],['match'])
        self.assertEqual(record['payload'],{'games':[]})
        self.assertTrue(record['source'].startswith('https://stats.nba.com/'))
        self.assertEqual(len(calls),2)
        for state, tip in (('post','2026-10-20T23:00Z'),('pre','2026-10-21T03:00Z'),('pre','2026-10-20T21:00Z')):
            event['status']['type']['state']=state;event['date']=tip;calls.clear()
            self.assertIsNone(feed.capture(now,fetch));self.assertEqual(len(calls),1)

    def test_missing_schedule_or_nba_data_cannot_publish_a_fresh_empty_capture(self):
        now=datetime(2026,10,20,22,tzinfo=timezone.utc)
        with self.assertRaises(ValueError):feed.capture(now,lambda url:{})
        event={'id':'match','date':'2026-10-20T23:00Z','status':{'type':{'state':'pre'}}}
        with self.assertRaises(ValueError):feed.capture(now,lambda url:{'events':[event]} if 'scoreboard' in url else {})
