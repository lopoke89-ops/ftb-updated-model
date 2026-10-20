"""Compare the full-game opening slice with the independently frozen opening ledger."""
import json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def compare(events,expected,teams):
    differences=[];checks=0
    for team in teams:
        for target,kinds in [('firstScores',('shot','free_throw')),('firstFieldGoals',('shot',))]:
            first=next((e for e in events if e['team']==team and e['type'] in kinds and e['result']=='made'),None);old=expected[target][team]
            for key,actual,wanted in [('id',first['participants']['shooter']['id'] if first else None,str(old['id'])),('clock',first['clock'].lstrip('0') if first else None,old['clock'].lstrip('0')),('points',first['points'] if first else None,old['points'])]:
                checks+=1
                if actual!=wanted:differences.append({'team':team,'target':target,'key':key,'observed':actual,'expected':wanted})
            if target=='firstFieldGoals' and first:
                extras=[e for e in events if e.get('linkedBasketSequence')==first['sequence']]
                for key,actual in [('andOneAwarded',bool(extras)),('andOneAttempts',len(extras)),('andOneMade',sum(e['result']=='made' for e in extras))]:
                    checks+=1
                    if actual!=old.get(key):differences.append({'team':team,'target':target,'key':key,'observed':actual,'expected':old.get(key)})
        for target,kinds in [('firstAttempts',('shot','free_throw')),('firstFieldGoalAttempts',('shot',))]:
            first=next((e for e in events if e['team']==team and e['type'] in kinds),None);old=expected[target][team]
            checks+=1
            if not old.get('identityUnresolved') and (not first or first['participants']['shooter']['id'] not in old['athleteIds'] or first['clock'].lstrip('0')!=old['clock'].lstrip('0') or (first['result']=='made')!=old['scoringPlay']):differences.append({'team':team,'target':target,'observed':first,'expected':old})
    return checks,differences

if __name__=='__main__':
    old=json.loads((ROOT/'nba ftb shi/opening_data.json').read_text(encoding='utf-8'))['games'];c=sqlite3.connect(ROOT/'.pbp/archive.sqlite');checks=0;differences=[];withheld=[]
    for gid,rid,result,g in c.execute('SELECT a.game_id,a.revision,r.result,r.game FROM active a JOIN revisions r ON a.revision=r.id'):
        result=json.loads(result);g=json.loads(g)
        if not all(result['components'].get(s) for s in ('pts','fga','fta')):withheld.append(gid);continue
        events=[json.loads(x[0]) for x in c.execute('SELECT event FROM events WHERE revision=? ORDER BY sequence',(rid,))]
        count,ds=compare(events,old[gid],(g['home'],g['away']));checks+=count;differences.extend({'gameId':gid,**d} for d in ds)
    report={'checks':checks,'eligibleGames':len(old)-len(withheld),'withheldGames':withheld,'differences':differences}
    (ROOT/'audits/2026-10-19-full-game-pbp/opening_independent_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print({'checks':checks,'eligibleGames':report['eligibleGames'],'differences':len(differences)});raise SystemExit(bool(differences))
