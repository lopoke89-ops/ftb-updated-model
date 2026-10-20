import copy
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
import full_game_pbp as p
import pbp_collect
from test_pages_build import temporary_output

CASES=json.loads((Path(__file__).parent/'fixtures/full_game_pbp.json').read_text(encoding='utf-8'))

def parsed(case):
    events,periods,issues=p.parse_pages(case['pages'],case['game'],case['record'])
    return events,p.reconcile(events,periods,issues,case['game'],case['record'])

class FullGameLedger(unittest.TestCase):
    def test_source_edge_cases_and_identity_crosswalk(self):
        import hashlib
        cases=json.loads((Path(__file__).parent/'fixtures/pbp_source_edge_cases.json').read_text(encoding='utf-8'))
        for case in cases:
            original=copy.deepcopy(case['record']);events,periods,issues=p.parse_pages(case['pages'],case['game'],case['record'])
            before=[(e['raw'],e['text'],e['score']) for e in events]
            if case.get('identitySource'):
                with temporary_output() as folder:
                    source=folder/'identity.json';raw=json.dumps(case['identitySource']).encode();source.write_bytes(raw)
                    meta={'sha256':hashlib.sha256(raw).hexdigest(),'url':'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+case['game']['id'],'capturedAt':'fixture'}
                    source.with_suffix('.source.json').write_text(json.dumps(meta))
                    p.pbp_identity.resolve(events,case['game'],case['record'],source)
                    self.assertEqual(before,[(e['raw'],e['text'],e['score']) for e in events])
                    source.write_bytes(raw+b' ')
                    with self.assertRaisesRegex(ValueError,'game/hash mismatch'):p.pbp_identity.resolve(events,case['game'],case['record'],source)
            result=p.reconcile(events,periods,issues,case['game'],case['record'])
            self.assertEqual(result['status'],'verified',(case['game']['id'],result['discrepancies']))
            self.assertEqual(original,case['record'])
            for e in events:
                if e['type']=='team_attempt':self.assertFalse(e['participants']);self.assertTrue(e['teamAttempt'])
                if e.get('teamRebound'):self.assertIsNone(e['participants']['rebounder']['id'])
                if e.get('sourceColumnTeam'):self.assertTrue(e['teamRebound']);self.assertNotEqual(e['team'],e['sourceColumnTeam'])

    def test_same_clock_crosswalk_requires_unique_actor_and_correct_game(self):
        import hashlib
        case=CASES[0];team=case['game']['home'];ids=[str(x['espn_player_id']) for x in case['record']['player_rows'] if x['team']==team and x.get('espn_player_id')][:2]
        event={'period':1,'clock':'01:00','team':team,'type':'turnover','text':'Ambiguous Traveling TURNOVER','participants':{'committer':{'id':None,'candidates':ids,'token':'Ambiguous'}}}
        data={'header':{'id':case['game']['id'],'competitions':[{'competitors':[{'team':{'id':str(i),'abbreviation':case['game'][side]}} for i,side in enumerate(('home','away'))]}]},'plays':[{'id':str(i),'period':{'number':1},'clock':{'displayValue':'1:00'},'team':{'id':'0'},'type':{'text':'Traveling'},'text':'traveling turnover','participants':[{'athlete':{'id':pid}}]} for i,pid in enumerate(ids)]}
        with temporary_output() as folder:
            path=folder/'source.json'
            def save_capture():
                raw=json.dumps(data).encode();path.write_bytes(raw);path.with_suffix('.source.json').write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'url':'fixture','capturedAt':'fixture'}))
            save_capture();p.pbp_identity.resolve([event],case['game'],case['record'],path);self.assertIsNone(event['participants']['committer']['id'])
            data['header']['id']='wrong';save_capture()
            with self.assertRaisesRegex(ValueError,'game/hash mismatch'):p.pbp_identity.resolve([event],case['game'],case['record'],path)

    def test_regulation_and_double_overtime_reconcile_exactly(self):
        for case in CASES[:4]:
            events,r=parsed(case)
            self.assertTrue(r['periodCoverage']);self.assertTrue(all(r['components'].values()),r['discrepancies'])
            self.assertEqual(len(r['periods']),6 if case['game']['id']=='401809243' else 4)
            self.assertEqual(len({e['logicalId'] for e in events}),len(events))
            self.assertEqual([e['sequence'] for e in events],list(range(1,len(events)+1)))
            self.assertTrue(all(e['page'] and e['lineEnd']>=e['line'] for e in events))
    def test_wrapping_repeated_clocks_both_columns_and_links(self):
        e,r=parsed(CASES[2]);self.assertTrue(r['components']['fga'])
        shot=next(x for x in e if 'N.Alexander-Walker Driving Finger Roll Layup' in x['text']);self.assertEqual(shot['type'],'shot')
        e,_=parsed(CASES[0]);blocks=[x for x in e if x['type']=='block'];self.assertTrue(blocks)
        by_seq={x['sequence']:x for x in e}
        for b in blocks:
            self.assertEqual(by_seq[b['linkedAttemptSequence']]['rowId'],b['rowId'])
        self.assertTrue(any(x.get('teamRebound') for x in e));self.assertTrue(any(x['type']=='substitution' for x in e))
        self.assertTrue(any(x.get('andOne') for x in e))
        self.assertTrue(any(x['type']=='free_throw' and x['result']=='missed' for x in e))
    def test_incomplete_period_quarantines_without_changing_boxes(self):
        case=copy.deepcopy(CASES[0]);before=copy.deepcopy(case['record']);case['pages']=[x for x in case['pages'] if p.period_number(x['text'])!=3]
        _,r=parsed(case);self.assertEqual(r['status'],'quarantined');self.assertFalse(any(r['components'].values()));self.assertEqual(before,case['record'])
    def test_name_collisions_suffixes_and_surname_only_are_explicit(self):
        case=copy.deepcopy(CASES[0]);row=copy.deepcopy(case['record']['player_rows'][0]);row.update(nba_name='Example Mobley',espn_player_id='other');case['record']['player_rows'].append(row)
        e,_=parsed(case);ambiguous=[x for x in e if x.get('participants',{}).get('shooter',{}).get('token')=='E.Mobley'];self.assertTrue(ambiguous);self.assertTrue(all(x['participants']['shooter']['id'] is None for x in ambiguous))
        e,r=parsed(CASES[4]);self.assertFalse(r['components']['fga']);self.assertTrue(any(d['kind']=='unresolved participant' and d.get('token')=='Yang' for d in r['discrepancies']))
        self.assertIn('lnancejr',p.aliases('Larry Nance Jr.'));self.assertIn('yniederhauser',p.aliases('Yanic Konan Niederhauser'))
    def test_retries_revisions_and_atomic_active_pointer(self):
        case=CASES[0];events,result=parsed(case)
        with temporary_output() as folder:
            library=folder/'library';library.mkdir();pdf=library/'book.pdf';pdf.write_bytes(b'original')
            r={**case['record'],'sha256':p.sha(b'original'),'pdf_path':'book.pdf'}
            c=p.connect(folder/'ledger.sqlite');job=(case['game'],r,case['pages'],events,result,None)
            p.store_result(c,library,job);p.store_result(c,library,job)
            self.assertEqual(c.execute('select count(*) from revisions').fetchone()[0],1)
            self.assertEqual(c.execute('select count(*) from events').fetchone()[0],len(events))
            old=c.execute('select revision from active').fetchone()[0]
            self.assertNotEqual(p.revision_id(case['game'],r),p.revision_id(case['game'],{**r,'pbpIdentitySource':{'sha256':'new capture'}}))
            pdf.write_bytes(b'revised');r2={**r,'sha256':p.sha(b'revised')};p.store_result(c,library,(case['game'],r2,case['pages'],events,result,None))
            self.assertEqual(c.execute('select count(*) from sources').fetchone()[0],2);self.assertNotEqual(old,c.execute('select revision from active').fetchone()[0])
            self.assertEqual(c.execute('select pdf from sources where hash=?',(r['sha256'],)).fetchone()[0],b'original')
            active=c.execute('select revision from active').fetchone()[0]
            try:
                with c:
                    c.execute('delete from active');raise OSError('interrupted write')
            except OSError: pass
            self.assertEqual(active,c.execute('select revision from active').fetchone()[0]);c.close()
    def test_new_box_revision_with_failed_events_withholds_old_events(self):
        case=CASES[0];events,result=parsed(case)
        with temporary_output() as folder:
            library=folder/'library';(library/'records').mkdir(parents=True);(library/'book.pdf').write_bytes(b'old')
            r={**case['record'],'pdf_path':'book.pdf','sha256':p.sha(b'old')};p.save(library/'records'/(case['game']['id']+'.json'),r)
            with patch.object(p,'parse_job',return_value=(case['game'],r,case['pages'],events,result,None)):
                pbp_collect.update(folder,[{**case['game'],'sourceHash':r['sha256']}])
            new={**r,'sha256':p.sha(b'new')};p.save(library/'records'/(case['game']['id']+'.json'),new);(library/'book.pdf').write_bytes(b'new')
            with patch.object(p,'parse_job',side_effect=OSError('new parser failure')):
                m,_=pbp_collect.update(folder,[{**case['game'],'sourceHash':new['sha256']}],parent_hash='new boxes')
            active=m['games'][case['game']['id']];self.assertEqual(active['status'],'pending');self.assertEqual(active['components'],{});self.assertEqual(active['previousSourceHash'],r['sha256'])

    def test_changed_parser_failure_withholds_prior_event_interpretation(self):
        case=CASES[0];events,result=parsed(case)
        with temporary_output() as folder:
            library=folder/'library';(library/'records').mkdir(parents=True);(library/'book.pdf').write_bytes(b'fixture')
            r={**case['record'],'pdf_path':'book.pdf','sha256':p.sha(b'fixture')};p.save(library/'records'/(case['game']['id']+'.json'),r)
            with patch.object(p,'parse_job',return_value=(case['game'],r,case['pages'],events,result,None)):pbp_collect.update(folder,[{**case['game'],'sourceHash':r['sha256']}])
            with patch.object(p,'CODE_HASH','changed parser'),patch.object(p,'parse_job',side_effect=OSError('new parser unavailable')):
                m,_=pbp_collect.update(folder,[{**case['game'],'sourceHash':r['sha256']}])
            current=m['games'][case['game']['id']];self.assertEqual(current['status'],'pending');self.assertEqual(current['components'],{});self.assertIn('Parser or identity',current['reason'])

    def test_compressed_ledger_archive_restore_and_failure(self):
        import io
        class Store:
            def content_file(self,path,*args):
                self.bytes=Path(path).read_bytes();return 'https://github.com/example/releases/download/data/pbp.gz'
        with temporary_output() as folder:
            source=folder/'source';database=source/'library/play_by_play.sqlite';c=p.connect(database);c.close();store=Store()
            ref=pbp_collect.archive(source,store,'2026-27','2026-10-20')
            restored=folder/'restored';restored.mkdir();p.save(restored/'pbp_database.json',ref)
            with patch.object(pbp_collect,'urlopen',return_value=io.BytesIO(store.bytes)):
                m,_=pbp_collect.update(restored,[],parent_hash='current')
            self.assertEqual(pbp_collect.file_hash(restored/'library/play_by_play.sqlite'),ref['databaseHash'])
            failed=folder/'failed';failed.mkdir();p.save(failed/'pbp_database.json',ref)
            with patch.object(pbp_collect,'urlopen',side_effect=OSError('archive unavailable')):
                m,_=pbp_collect.update(failed,[CASES[0]['game']],parent_hash='new parent')
            self.assertEqual(m['parentEvidenceContentHash'],'new parent');self.assertEqual(m['statusCounts'],{'pending':1});self.assertIn('archive unavailable',m['lastRestoreError'])

    def test_corrupt_or_changed_pdf_never_uses_old_box_hash(self):
        with temporary_output() as folder:
            r={**CASES[0]['record'],'pdf_path':'bad.pdf'};(folder/'bad.pdf').write_bytes(b'corrupt')
            parsed_job=p.parse_job((folder,CASES[0]['game'],r));self.assertIn('hash differs',parsed_job[-1]);self.assertEqual(parsed_job[4]['status'],'quarantined')
    def test_completed_box_pending_event_queue_retries_without_box_ingest(self):
        case=CASES[0];events,result=parsed(case)
        with temporary_output() as folder:
            library=folder/'library';(library/'records').mkdir(parents=True);(library/'book.pdf').write_bytes(b'fixture')
            r={**case['record'],'pdf_path':'book.pdf','sha256':p.sha(b'fixture')};p.save(library/'records'/(case['game']['id']+'.json'),r)
            good=(case['game'],r,case['pages'],events,result,None)
            with patch.object(p,'parse_job',return_value=good) as parser:
                m,changed=pbp_collect.update(folder,[{**case['game'],'sourceHash':r['sha256']}]);self.assertTrue(changed);parser.assert_called_once()
                self.assertEqual(m['expected'],1);self.assertTrue(m['games'][case['game']['id']]['components']['fga'])
            with patch.object(p,'parse_job',side_effect=OSError('partial fixture failure')):
                m,_=pbp_collect.update(folder,[{**case['game'],'sourceHash':r['sha256']}],force=True)
                self.assertTrue(m['games'][case['game']['id']]['components']['fga']);self.assertIn('partial fixture failure',m['attempts'][case['game']['id']]['error'])

if __name__=='__main__':unittest.main()
