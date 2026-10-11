import copy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from test_pages_build import temporary_output
import parlay_journal as j
import evaluate_parlay_transition as ev

class ParlayJournal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = j.read(j.SOURCE/'analyst_data.json')
        cls.game = copy.deepcopy(cls.archive['games'][0])
        cls.game['date'] = '2026-10-20'  # Synthetic prospective-window fixture; never written to source data.

    def payload(self, now):
        g = self.game
        fixture = {'id':g['id'],'date':'2026-10-20','season':'2026-27','phase':'regular-season','home':g['home'],'away':g['away'],'scheduledTipoff':(now+timedelta(minutes=10)).isoformat()}
        slots = []
        for team,opp in ((g['home'],g['away']),(g['away'],g['home'])):
            pid = str(g['firstScores'][team]['id'])
            for market in sorted(j.MARKETS):
                target = None if market=='first-team-basket' else {'average':10.4 if market=='points' else 1.3,'threshold':11 if market=='points' else 2}
                p = {'id':pid,'score':30,'provisional':False,'seasonTarget':target}
                if market=='first-team-basket':
                    p['confirmation']={'id':pid,'team':team,'fixtureId':fixture['id'],'status':'confirmed','source':'https://stats.nba.com/js/data/leaders/00_daily_lineups_20261020.json','capturedAt':now.isoformat()}
                research = {'pick':copy.deepcopy(p),'configurationHash':j.read(j.SOURCE/'parlay_research_config.json')['configurationHash'],'baselines':{}}
                slots.append({'fixtureId':fixture['id'],'fixture':fixture,'team':team,'opponent':opp,'market':market,'pick':p,'research':research,'transition':{'teamGames':1}})
        snapshot = {'meta':{'season':'2026-27','evidenceContentHash':j.digest([])},'games':[]}
        return {'schemaVersion':3,'capturedAt':now.isoformat(),'analysisMode':'pregame','upcoming':True,'firstBasketTarget':'first-team-score-including-free-throws','date':'2026-10-20','competition':'regular-season',
            'modelHashes':{'synthetic':'hash'},'protocolHash':j.hashlib.sha256((j.ROOT/'PARLAY_RESEARCH_PROTOCOL.json').read_bytes()).hexdigest(),'archiveEvidenceHash':'archive','currentEvidenceHash':snapshot['meta']['evidenceContentHash'],'selections':slots}, snapshot

    def test_receipts_preserve_revisions_and_settlement_uses_pdf_targets(self):
        now = datetime(2026,10,20,23,tzinfo=timezone.utc);record,snapshot=self.payload(now)
        verifier=lambda f,n:{'scheduledTipoff':f['scheduledTipoff'],'source':'synthetic schedule test'}
        with temporary_output() as store:
            a=j.record_export(record,store,snapshot,now,verifier,{'synthetic':'hash'},'archive',True)
            b=j.record_export(record,store,snapshot,now+timedelta(seconds=10),verifier,{'synthetic':'hash'},'archive',True)
            self.assertNotEqual(a['id'],b['id']);self.assertEqual(len(j.lines(store/'receipts.jsonl')),2)
            self.assertEqual(j.sealed_lines(store/'receipts.jsonl')[-1]['revisionOf'],a['id'])
            self.assertEqual(j.settle(store,{'games':[self.game]})['updated'],2)
            self.assertEqual(j.settle(store,{'games':[self.game]})['updated'],0)
            report=ev.evaluate(store,expected_hashes={'synthetic':'hash'})
            self.assertTrue(report['markets']);self.assertFalse(any(r['promotable'] for r in report['markets'].values()))
            self.assertEqual(report['markets']['points|season-average']['models']['production']['issued'],2)

    def test_late_old_or_wrong_model_exports_cannot_be_received_prospectively(self):
        now=datetime(2026,10,20,23,tzinfo=timezone.utc);record,snapshot=self.payload(now)
        with temporary_output() as store:
            for mutate in (lambda r:r.update(schemaVersion=2),lambda r:r.update(capturedAt=(now-timedelta(minutes=2)).isoformat()),lambda r:r.update(modelHashes={}),lambda r:r['selections'].pop(),lambda r:r['selections'][0].update(research=None)):
                bad=copy.deepcopy(record);mutate(bad)
                with self.assertRaises(ValueError):j.record_export(bad,store,snapshot,now,lambda f,n:{},{'synthetic':'hash'},'archive',True)
            imported=j.record_export(record,store,now=now+timedelta(hours=3));self.assertEqual(imported['recordType'],'research-snapshot')
            j.settle(store,{'games':[self.game]});self.assertFalse(ev.evaluate(store)['markets'])

    def test_missing_outcomes_remain_pending_and_unverified_boxes_are_rejected(self):
        now=datetime(2026,10,20,23,tzinfo=timezone.utc);record,_=self.payload(now)
        with temporary_output() as store:
            j.record_export(record,store,now=now)
            self.assertEqual(j.settle(store,{'games':[]})['pending'],1)
            bad=copy.deepcopy(self.game);bad['boxScoreSource']='ESPN'
            with self.assertRaises(ValueError):j.settle(store,{'games':[bad]})
            bad=copy.deepcopy(self.game);bad['teams'][bad['home']]['points']+=1
            with self.assertRaises(ValueError):j.settle(store,{'games':[bad]})

    def test_fixture_status_and_checkpoint_verified_against_schedule(self):
        from unittest.mock import patch
        import io,json
        now=datetime(2026,10,20,23,tzinfo=timezone.utc);record,_=self.payload(now);f=record['selections'][0]['fixture']
        payload={'header':{'id':f['id'],'competitions':[{'date':f['scheduledTipoff'],'status':{'type':{'state':'pre'}},'competitors':[{'homeAway':side,'team':{'abbreviation':f[side]}} for side in ('home','away')]}]}}
        with patch.object(j,'urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
            self.assertEqual(j.verify_fixture(f,now)['scheduledTipoff'],f['scheduledTipoff'])
        payload['header']['competitions'][0]['status']['type']['state']='post'
        with patch.object(j,'urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
            with self.assertRaises(ValueError):j.verify_fixture(f,now)
        payload['header']['competitions'][0]['status']['type']['state']='pre'
        payload['header']['competitions'][0]['date']=(now+timedelta(minutes=16)).isoformat()
        with patch.object(j,'urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
            with self.assertRaises(ValueError):j.verify_fixture(f,now)

    def test_modified_receipts_or_outcomes_fail_integrity_and_versions_do_not_mix(self):
        now=datetime(2026,10,20,23,tzinfo=timezone.utc);record,snapshot=self.payload(now)
        with temporary_output() as store:
            j.record_export(record,store,snapshot,now,lambda f,n:{},{'synthetic':'hash'},'archive',True)
            j.settle(store,{'games':[self.game]})
            self.assertFalse(ev.evaluate(store)['markets'])
            self.assertEqual(ev.evaluate(store)['differentReleaseReceiptsExcluded'],1)
            original=(store/'outcomes.jsonl').read_text()
            (store/'outcomes.jsonl').write_text(original.replace('"hit": true','"hit": false'))
            with self.assertRaises(ValueError):ev.evaluate(store)
            (store/'outcomes.jsonl').write_text(original)
            records=j.lines(store/'receipts.jsonl');records[0]['receivedAt']=(now-timedelta(days=1)).isoformat()
            (store/'receipts.jsonl').write_text(j.json.dumps(records[0])+'\n')
            with self.assertRaises(ValueError):j.settle(store,{'games':[self.game]})

    def test_official_correction_appends_revision_and_regrades(self):
        now=datetime(2026,10,20,23,tzinfo=timezone.utc);record,snapshot=self.payload(now)
        with temporary_output() as store:
            j.record_export(record,store,snapshot,now,lambda f,n:{},{'synthetic':'hash'},'archive',True)
            j.settle(store,{'games':[self.game]})
            corrected=copy.deepcopy(self.game);old=corrected['sourceHash'];corrected['sourceHash']='corrected-pdf-hash'
            for box in corrected['teams'].values():
                for p in box['players']:p['statsSourceHash']=corrected['sourceHash']
            team=corrected['home'];old_id=corrected['firstScores'][team]['id']
            corrected['firstScores'][team]['id']=next(p['id'] for p in corrected['teams'][team]['players'] if p['played'] and p['id'] != old_id)
            self.assertEqual(j.settle(store,{'games':[corrected]})['updated'],1)
            outcomes=j.sealed_lines(store/'outcomes.jsonl');self.assertEqual(len(outcomes),2);self.assertEqual(outcomes[-1]['revisionOf'],old)
            hits=ev.evaluate(store,expected_hashes={'synthetic':'hash'})['markets']['first-team-basket|first-team-score-including-free-throws']['models']['production']['hits']
            self.assertEqual(hits,1)
            self.assertEqual(j.settle(store,{'games':[corrected]})['updated'],0)

    def test_same_data_new_publication_metadata_has_separate_frozen_snapshot(self):
        now=datetime(2026,10,20,23,tzinfo=timezone.utc);record,snapshot=self.payload(now)
        with temporary_output() as store:
            j.record_export(record,store,snapshot,now,lambda f,n:{},{'synthetic':'hash'},'archive',True)
            snapshot['publication']={'publishedAt':now.isoformat()}
            j.record_export(record,store,snapshot,now,lambda f,n:{},{'synthetic':'hash'},'archive',True)
            self.assertEqual(len(list((store/'snapshots').glob('*.json'))),2)
            record['selections'][1]['research']['pick']['seasonTarget']={'average':99.3,'threshold':100}
            with self.assertRaises(ValueError):j.record_export(record,store,snapshot,now,lambda f,n:{},{'synthetic':'hash'},'archive',True)

    def test_empty_evaluation_never_promotes(self):
        with temporary_output() as store:
            r=ev.evaluate(store);self.assertFalse(r['markets']);self.assertFalse(r['defaultModelChanged'])

if __name__=='__main__':unittest.main()
