import copy, hashlib, json, shutil, unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch
import official_gamebooks as boxes
import morning_collect as morning
import full_game_pbp as pbp
import opening_paths
import pbp_collect
from test_pages_build import temporary_output
CASES=json.loads((Path(__file__).parent/'fixtures/new_gamebooks/cases.json').read_text(encoding='utf-8'))
for case in CASES:
    case['game'].update(firstScores=case['expected']['firstScores'],firstFieldGoals=case['expected']['firstScores'])

def collected(folder,case):
    library=folder/'library';g=case['game'];target=library/'pdf'/g['date']/case['file'];target.parent.mkdir(parents=True,exist_ok=True);(library/'records').mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).parent/'fixtures/new_gamebooks'/case['file'],target)
    identities=defaultdict(set)
    for b in g['teams'].values():
        for p in b['players']:identities[boxes.norm(p['name'])].add(p['id'])
    with patch('official_gamebooks.urlopen',side_effect=AssertionError('Unchanged local PDF must not redownload')):
        r=boxes.collect_one(g,library,folder/'no-seed',identities)
    return library,r,identities

class NewGamebooks(unittest.TestCase):
    def test_three_real_font_layouts_match_independent_review_and_all_printed_totals(self):
        for case in CASES:
            with temporary_output() as folder:
                library,r,_=collected(folder,case);self.assertEqual(r['verification_status'],'verified',r.get('issues'));self.assertEqual(r['text_extraction']['textEngine'],'pdfium-box');self.assertEqual(r['sha256'],case['expected']['sourceHash'])
                for row in r['player_rows']:
                    if not row['played']:continue
                    expected=next(p for p in case['expected']['teams'][row['team']]['players'] if p['id']==row['espn_player_id'])
                    for key,field in morning.FIELDS.items():self.assertEqual(row[field],expected[key],(case['file'],row['nba_name'],field))
                for team,total in r['team_totals'].items():
                    for field in boxes.STAT_COLUMNS:
                        if field!='plus_minus':self.assertEqual(sum(p[field] for p in r['player_rows'] if p['played'] and p['team']==team),total[field])
                _,o,error=morning.opening.one_job((library,library/'text/opening_quarter',case['game'],r));self.assertIsNone(error)
                self.assertEqual({t:v['id'] for t,v in o['firstScores'].items()},{t:v['id'] for t,v in case['expected']['firstScores'].items()})

    def test_wrapped_clock_rows_and_both_team_columns_reconcile_without_guessing(self):
        for case in CASES:
            with temporary_output() as folder:
                library,r,_=collected(folder,case);parsed=pbp.parse_job((str(library),case['game'],r));self.assertIsNone(parsed[-1]);result=parsed[-2]
                if case['game']['id']!='401909090':self.assertEqual(result['status'],'verified',result['discrepancies'])
                else:
                    self.assertNotEqual(result['status'],'verified');self.assertTrue(any(d['kind']=='uninterpreted score adjustment' for d in result['discrepancies']))
                    self.assertTrue(any(e['text']=='A.Mara' and e['points']==2 for e in parsed[3]));self.assertFalse(any(result['components'].values()))
                _,opening,error=morning.opening.one_job((library,library/'text/opening_quarter',case['game'],r));self.assertIsNone(error)
                paths=opening_paths.derive(parsed[3],case['game'],opening,result['discrepancies']);self.assertEqual(sum(x['available'] for t in paths.values() for x in t.values()),4)

    def test_collins_and_bridges_initial_misses_rebounds_and_putbacks_trace_to_pdf(self):
        for case,team,player,rebounder in [(CASES[0],'DET','3908845','3908845'),(CASES[1],'NYK','3147657','162840')] :
            with temporary_output() as folder:
                library,r,_=collected(folder,case);_,o,error=morning.opening.one_job((library,library/'text/opening_quarter',case['game'],r));self.assertIsNone(error)
                parsed=pbp.parse_job((str(library),case['game'],r));paths=opening_paths.derive(parsed[3],case['game'],o,parsed[-2]['discrepancies']);path=paths[team]['first-score'];self.assertTrue(path['available']);self.assertEqual(path['firstScore']['playerId'],player)
                self.assertTrue(all(m['attempt']['page']>=9 for m in path['misses']))
                if team=='DET':
                    self.assertTrue(path['explicitPutbackFinish']);self.assertTrue(path['rebounderFinished']);self.assertEqual(path['offensiveRebounds'][0]['playerId'],player)
                else:
                    self.assertTrue(path['explicitPutbackFinish']);self.assertTrue(path['rebounderFinished']);self.assertEqual(path['offensiveRebounds'][0]['playerId'],player)

    def test_unchanged_retries_preserve_capture_time_and_revisions_retain_original_bytes(self):
        case=CASES[0]
        with temporary_output() as folder:
            library,r,ids=collected(folder,case);again=boxes.collect_one(case['game'],library,folder/'no-seed',ids);self.assertEqual(again,r)
            pdf=library/r['pdf_path'];original=pdf.read_bytes();pdf.write_bytes(original+b'\n');revised=boxes.collect_one(case['game'],library,folder/'no-seed',ids)
            self.assertEqual(revised['verification_status'],'verified');self.assertNotEqual(revised['sha256'],r['sha256']);self.assertEqual((library/'source_versions'/(r['sha256']+'.pdf')).read_bytes(),original);self.assertEqual((library/'source_versions'/(revised['sha256']+'.pdf')).read_bytes(),original+b'\n')

    def test_stale_fallback_cache_is_replaced_and_changed_pdf_hash_cannot_reuse_events(self):
        case=CASES[1]
        with temporary_output() as folder:
            library,r,_=collected(folder,case);cache=library/'text/opening_quarter'/(''+case['game']['id']+'.json');pages=morning.opening.quarter_pages(library/r['pdf_path'],cache,r['sha256']);saved=json.loads(cache.read_text());saved['pages'][1].update(text='corrupt cached interpretation',textCodeHash='obsolete');cache.write_text(json.dumps(saved))
            fresh=morning.opening.quarter_pages(library/r['pdf_path'],cache,r['sha256']);self.assertEqual(fresh[1]['text'],pages[1]['text'])
            pdf=library/r['pdf_path'];pdf.write_bytes(pdf.read_bytes()+b'\n');_,_,error=morning.opening.one_job((library,library/'new-cache',case['game'],r));self.assertIn('PDF hash changed',error)

    def test_unresolved_opening_identity_suppresses_paths_instead_of_zero(self):
        case=CASES[0]
        with temporary_output() as folder:
            library,r,_=collected(folder,case);parsed=pbp.parse_job((str(library),case['game'],r));_,o,_=morning.opening.one_job((library,library/'text/opening_quarter',case['game'],r));events=copy.deepcopy(parsed[3]);e=next(e for e in events if e['type']=='shot');e['participants']['shooter']['id']=None
            paths=opening_paths.derive(events,case['game'],o);self.assertFalse(paths[e['team']]['first-score']['available']);self.assertIn('identity',paths[e['team']]['first-score']['reason'])

    def test_failed_latest_box_does_not_destroy_independently_verified_prior_events(self):
        case=CASES[0]
        with temporary_output() as folder:
            library,r,_=collected(folder,case);_,o,_=morning.opening.one_job((library,library/'text/opening_quarter',case['game'],r));r['opening']=o;g=morning.official_game(case['game'],r,o);morning.save(library/'records'/(g['id']+'.json'),r)
            first,_=pbp_collect.update(folder,[g]);self.assertEqual(first['games'][g['id']]['status'],'verified')
            morning.save(library/'records'/(g['id']+'.json'),{'verification_status':'unavailable','error':'Revised source temporarily unavailable'})
            after,_=pbp_collect.update(folder,[g]);self.assertEqual(after['games'][g['id']]['sourceHash'],first['games'][g['id']]['sourceHash']);self.assertEqual(after['games'][g['id']]['status'],'verified');self.assertEqual(after['attempts'][g['id']]['status'],'pending')

if __name__=='__main__':unittest.main()
