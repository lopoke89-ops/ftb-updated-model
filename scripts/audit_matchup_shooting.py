"""Audit displayed shooting against official boxes without production aggregation."""
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'nba ftb shi';OUT=ROOT/'audits/2026-10-19-full-game-pbp'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def run():
    OUT.mkdir(parents=True,exist_ok=True);scratch=ROOT/'.build-tests/shooting-chart-inputs.json'
    js=r'''
const fs=require('fs'),path=require('path'),base=process.argv[1],out=process.argv[2],M=require(path.join(base,'matchup.js')),data=require(path.join(base,'analyst_data.json'));
data.roleEvidence=require(path.join(base,'parlay_data.json')).datedRoleEvidence;
const results=[],fixtures=[['BOS','DET'],['PHI','NYK'],['OKC','SAS']].map(([away,home],i)=>({id:'fixture'+i,away,home,date:'2026-10-20',season:'2026-27'}));
function capture(o){const opts={date:'2026-10-20',mode:'upcoming',trusted:true,...o};const r=M.build({meta:{season:'2026-27'},games:[]},data,fixtures,opts);results.push({options:r.options,directions:r.comparisons.flatMap(c=>c.directions.map(d=>({team:d.production.team,opponent:d.allowance.team,productionIds:d.production.gameIds,allowanceIds:d.allowance.gameIds,rows:M.shootingRows(d),threes:['per48','perGame','share'].map(rate=>({rate,rows:M.rows(d,'threes',rate)}))})))});}
for(const phase of ['all','regular-season','playoffs','regular-and-playoffs','play-in','nba-cup-final'])for(const window of ['0','5','10','20'])for(const headToHead of [false,true])for(const positions of ['broad','strict'])capture({phase,window,headToHead,positions});
fs.writeFileSync(out,JSON.stringify(results));'''
    subprocess.run(['node','-e',js,str(BASE),str(scratch)],check=True,cwd=ROOT)
    official=read(BASE/'official_boxscores.json')['games'];history=read(BASE/'analyst_data.json'); indexed={g['id']:g for g in history['games']};failures=[];checks=0
    def eq(a,b,context):
        nonlocal checks
        checks+=1
        if not (math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9) if isinstance(a,(int,float)) and isinstance(b,(int,float)) else a==b):failures.append({'context':context,'displayed':a,'expected':b})
    nba_roles={}
    groups={}
    for r in read(BASE/'parlay_data.json')['datedRoleEvidence']:groups.setdefault((r['gameId'],r['team']),[]).append(r)
    for (gid,team),rs in groups.items():
        if len(rs)==5 and len({r['position'] for r in rs})==5 and len({r['playerId'] for r in rs})==5 and all(r['gamebookSourceHash']==official[gid]['sha256'] and r['effectiveGameDate']==official[gid]['date'] and r['playerId'] in official[gid]['teams'][team] and official[gid]['teams'][team][r['playerId']]['starter'] for r in rs):
            nba_roles.update({(gid,team,r['playerId']):r['position'] for r in rs})
    def role(gid,team,pid,basis):
        source=official[gid]['teams'][team][pid];appearance=next(p for p in indexed[gid]['teams'][team]['players'] if p['id']==pid)
        raw=source.get('officialPosition') or appearance.get('rawPosition') or ''
        if basis=='strict' and (gid,team,pid) in nba_roles:return nba_roles[(gid,team,pid)]
        if basis=='strict':return raw if raw in ('PG','SG','SF','PF','C') else 'unknown'
        return 'G' if raw in ('PG','SG','G') else 'F' if raw in ('SF','PF','F') else 'C' if raw=='C' else 'unknown'
    def ids(team,opponent,o):
        gs=[(gid,g) for gid,g in official.items() if team in (g['home'],g['away']) and (not o['headToHead'] or opponent in (g['home'],g['away'])) and (o['phase']=='all' or g['phase']==o['phase'] or o['phase']=='regular-and-playoffs' and g['phase'] in ('regular-season','playoffs'))]
        gs.sort(key=lambda x:(x[1]['date'],x[0]));return [gid for gid,g in (gs[-int(o['window']):] if int(o['window']) else gs)]
    cases=read(scratch)
    for case in cases:
        o=case['options']
        for d in case['directions']:
            expected_ids={'production':ids(d['team'],d['opponent'],o),'allowance':ids(d['opponent'],d['team'],o)}
            for side in ('production','allowance'):
                eq(d[side+'Ids'],expected_ids[side],f'{o}/{d["team"]}/{side}/games')
                for row in d['rows']:
                    totals=Counter();seconds=0;appearances=0
                    all_threes=0
                    for gid in expected_ids[side]:
                        g=official[gid];team=d['team'] if side=='production' else g['away'] if g['home']==d['opponent'] else g['home']
                        for pid,p in g['teams'][team].items():
                            all_threes+=p['threeMade']
                            if role(gid,team,pid,o['positions'])!=row['position']:continue
                            appearances+=1;seconds+=p['minutesSeconds']
                            for k in ('fgm','fga','threeMade','threeAttempted','ftm','fta'):totals[k]+=p[k]
                    totals['twoMade']=totals['fgm']-totals['threeMade'];totals['twoAttempted']=totals['fga']-totals['threeAttempted']
                    for name,m,a in [('FG','fgm','fga'),('2P','twoMade','twoAttempted'),('3P','threeMade','threeAttempted'),('FT','ftm','fta')]:
                        expected={'made':totals[m] if appearances else None,'attempted':totals[a] if appearances else None,'percentage':100*totals[m]/totals[a] if appearances and totals[a] else None,'games':len(expected_ids[side]),'appearances':appearances}
                        for k,v in expected.items():eq(row[side][name][k],v,f'{o}/{d["team"]}/{side}/{row["position"]}/{name}/{k}')
                    for chart in d['threes']:
                        actual=next(r for r in chart['rows'] if r['position']==row['position'])[side]
                        rate=chart['rate'];den=seconds/2880 if rate=='per48' else len(expected_ids[side]) if rate=='perGame' else all_threes/100
                        expected=totals['threeMade']/den if den and appearances else None
                        eq(actual,expected,f'{o}/{d["team"]}/{side}/{row["position"]}/threes/{rate}')
    report={'scopeCases':len(cases),'comparisons':checks,'differences':failures,'source':'official_boxscores.json, PDF hash-linked immutable extracts; historical raw positions only when PDF role absent'}
    (OUT/'shooting_independent_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({**report,'differences':len(failures)}));return report
if __name__=='__main__':
    if run()['differences']:raise SystemExit(1)
