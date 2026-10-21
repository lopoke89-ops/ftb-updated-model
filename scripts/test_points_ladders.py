import copy,json,unittest
from pathlib import Path
import audit_points_ladders as audit
ROOT=Path(__file__).resolve().parents[1]
class PointsLadderAudit(unittest.TestCase):
 def setUp(self):
  self.snapshot=json.loads((ROOT/'scripts/fixtures/points_ladder_audit.json').read_text());self.archive=json.loads((ROOT/'nba ftb shi/analyst_data.json').read_text());self.model=json.loads((ROOT/'nba ftb shi/ev_model.json').read_text())
 def test_saved_keldon_contract_reconstructs_without_production_forecast_helpers(self):
  r=audit.audit(self.snapshot,self.archive,self.model)['rows'][0];self.assertEqual(r['historicalHits'],13);self.assertEqual(r['appearances'],82);self.assertAlmostEqual(r['estimatedEV'],3.357040693061869);self.assertAlmostEqual(r['calibratedThresholdProbability'],.24205781628121492);self.assertGreater(r['rawDistributionVariance'],r['historicalVariance']);self.assertLess(r['sensitivity'][0]['thresholdProbability'],r['breakEven'])
 def test_wrong_saved_minutes_and_same_day_mutations_do_not_escape_the_trace(self):
  altered=copy.deepcopy(self.snapshot);altered['results'][0]['features']['minutes']+=1
  with self.assertRaises(AssertionError):audit.audit(altered,self.archive,self.model)
  baseline=audit.audit(self.snapshot,self.archive,self.model)['rows'][0];g=copy.deepcopy(self.archive['games'][0]);g.update(id='future',date='2026-10-20');self.archive['games'].append(g);self.assertEqual(audit.audit(self.snapshot,self.archive,self.model)['rows'][0],baseline)
if __name__=='__main__':unittest.main()
