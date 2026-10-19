import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('lineup_capture',Path(__file__).resolve().parents[1]/'nba ftb shi/lineup_capture.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CaptureValidation(unittest.TestCase):
    def test_official_capture_has_a_five_minute_limit(self):
        now=datetime(2026,10,20,22,tzinfo=timezone.utc)
        record={'kind':'NBA lineups','url':'https://stats.nba.com/js/data/leaders/00_daily_lineups_20261020.json','payload':{'games':[]},'capturedAt':(now-timedelta(minutes=4)).isoformat()}
        self.assertTrue(module.validate_lineup_capture(record,now))
        record['capturedAt']=(now-timedelta(minutes=6)).isoformat()
        with self.assertRaises(ValueError):module.validate_lineup_capture(record,now)

    def test_depth_fallback_retains_its_original_capture_time(self):
        now=datetime(2026,10,20,22,tzinfo=timezone.utc)
        record={'kind':'ESPN depth chart','url':'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/2/depthcharts','payload':{'team':{'id':'2'},'depthchart':[]},'capturedAt':(now-timedelta(hours=2)).isoformat()}
        original=record['capturedAt']
        self.assertTrue(module.validate_lineup_capture(record,now));self.assertEqual(record['capturedAt'],original)
        for changed in ({'capturedAt':(now+timedelta(seconds=1)).isoformat()},{'capturedAt':(now-timedelta(hours=7)).isoformat()},{'url':'https://untrusted.example/depthcharts'},{'payload':{'team':{'id':'8'},'depthchart':[]}}):
            with self.assertRaises(ValueError):module.validate_lineup_capture({**record,**changed},now)
