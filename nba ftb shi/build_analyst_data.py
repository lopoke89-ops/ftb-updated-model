"""Build dated analysis evidence without changing the canonical workbook."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,sys,gzip,argparse
from data_model import BASE,write_json,classify_shot
ROOT=BASE.parent

def build(cache=ROOT/'season_merge_2026-10-04/source_cache', opening=ROOT/'implementation_2026-10-04/opening_cache',out_dir=BASE,canonical_dir=BASE):
    out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
    canonical=json.loads((Path(canonical_dir)/'merged_dataset.json').read_text(encoding='utf-8'))
    validation=json.loads((Path(canonical_dir)/'validation_report.json').read_text(encoding='utf-8'))
    canonical_events={(e['eventId'],e['scoringTeam']):e for e in validation['events']}
    games=[]; positions=Counter(); stat_gaps=Counter(); points=0
    dated_roles=json.loads((BASE/'dated_role_evidence.json').read_text(encoding='utf-8'))
    for file in sorted(cache.glob('summary_*.json')):
        d=json.loads(file.read_text(encoding='utf-8')); f=d['fixture']; teams={}; scores={}; fields={}
        for team,t in d['teams'].items():
            roster=[]
            for p in t['players']:
                stat=p['stats']; positions[p['position'] or 'unknown']+=1
                if p['played']:
                    points+=int(stat['PTS'])
                    for k in ('MIN','PLUS_MINUS'):
                        if stat[k] is None:stat_gaps[k]+=1
                roster.append({'id':p['athleteId'],'name':p['name'],'rawPosition':p['position'],
                    'starter':p['starter'],'played':p['played'],'points':stat['PTS'],'threeMade':stat['FG3M'],
                    'threeAttempted':stat['FG3A'],'minutes':stat['MIN'],'fga':stat['FGA'],'fta':stat['FTA']})
            teams[team]={'players':roster,'starters':t['starters'],'points':t['points']}
            ce=canonical_events[(f['eventId'],team)]
            scores[team]={'id':ce['sourcePlayerId'],'name':ce['scoringPlayer'],'shot':ce['shotType'],
                'position':ce['pos'],'clock':ce['clock'],'period':ce['period'],'sequence':ce['sequence'],'points':ce['points']}
            fg=d['firstFieldGoals'].get(team)
            if fg:fields[team]={'id':fg.get('athleteId',''),'name':fg['name'],'clock':fg['clock'],'period':fg['period'],'sequence':fg['sequence'],'points':fg['points'],'shot':classify_shot(fg['text'],fg['points'])}
        opath=opening/(f['eventId']+'.json')
        op=json.loads(opath.read_text(encoding='utf-8')) if opath.exists() else None
        games.append({'id':f['eventId'],'date':f['date'],'home':f['home'],'away':f['away'],'phase':f['gameType'],
            'teams':teams,'firstScores':scores,'firstFieldGoals':fields,'opening':op,
            'scheduledTipoff':op.get('scheduledTipoff') if op else None,'capturedAt':d['fetchedAt'],
            'source':d['source'],'sourceHash':hashlib.sha256(file.read_bytes()).hexdigest(),
            'availabilityHistory':'unavailable','lineupSource':'postgame-box-score'})
    games.sort(key=lambda g:(g['date'],g['id']))
    assert len(games)==1322 and sum(len(g['firstScores']) for g in games)==2644
    assert sum(s['shot']=='ft' for g in games for s in g['firstScores'].values())==249
    assert points==304328
    manifest={'schemaVersion':1,'datasetId':'nba-2025-26-analysis-evidence','parentDatasetId':canonical['meta']['datasetId'],
        'viewType':'dated-analysis-evidence','season':'2025-26','coverageComplete':True,'totalGames':len(games),
        'scoringDefinition':canonical['meta']['scoringDefinition'],'asOfDate':canonical['meta']['asOfDate'],
        'phaseCounts':dict(Counter(g['phase'] for g in games)),
        'canonicalWorkbookHash':canonical['meta']['sources']['ftb']['sha256'],
        'builtAt':datetime.now(timezone.utc).isoformat(),'sourceCaptureMeaning':'retrospective corrected-data capture; original publication times unavailable',
        'historicalInjuries':'unavailable','pregameLineupAnnouncements':'unavailable',
        'openingCoverage':sum(g['opening'] is not None and not g['opening'].get('error') for g in games),
        'rawPositionCounts':dict(positions),'optionalStatGaps':dict(stat_gaps)}
    manifest['evidenceContentHash']=hashlib.sha256(json.dumps({'games':games,'datedRoleEvidence':dated_roles},separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
    data={'meta':manifest,'games':games,'datedRoleEvidence':dated_roles}
    from official_stats import load,apply_analysis
    data=apply_analysis(data,load())
    write_json(out_dir/'analyst_data.json',data)
    (out_dir/'analyst_data.js').write_text('window.__FTB_ANALYST_DATA__ = '+json.dumps(data,separators=(',',':'),ensure_ascii=False,allow_nan=False)+';\n',encoding='utf-8')
    write_json(ROOT/'implementation_2026-10-04/source_coverage.json',manifest)
    print(json.dumps({'games':len(games),'points':points,'openingCoverage':manifest['openingCoverage'],'optionalGaps':dict(stat_gaps)}))
    return data
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out-dir',type=Path,default=BASE);p.add_argument('--canonical-dir',type=Path,default=BASE);a=p.parse_args();build(out_dir=a.out_dir,canonical_dir=a.canonical_dir)
