import unittest
from datetime import datetime, timezone
import refresh_lineups as feed


class LineupBridge(unittest.TestCase):
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
