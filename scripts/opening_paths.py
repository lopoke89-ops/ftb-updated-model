"""Source-linked first-attempt / rebound / next-attempt paths. No possession inference."""
import argparse, hashlib, json, re, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='opening-paths-v1'
CODE_HASH=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
def packed(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(v):return hashlib.sha256(packed(v).encode()).hexdigest()
def event(e):
    if e is None:return None
    role='rebounder' if e['type']=='rebound' else 'committer' if e['type']=='turnover' else 'shooter'
    return {'sequence':e['sequence'],'period':e['period'],'clock':e['clock'],'team':e['team'],'playerId':e.get('participants',{}).get(role,{}).get('id'),'page':e['page'],'text':e['text'],'made':e.get('result')=='made','freeThrow':e['type']=='free_throw','teamRebound':bool(e.get('teamRebound')),'kind':e.get('reboundKind')}
def derive(events,game,expected,discrepancies=()):
    answer={}
    for team in (game['home'],game['away']):
        answer[team]={}
        for target,kinds in [('first-score',('shot','free_throw')),('first-field-goal',('shot',))]:
            first=next((e for e in events if e['team']==team and e['type'] in kinds and e.get('result')=='made'),None)
            reference=expected.get('firstScores' if target=='first-score' else 'firstFieldGoals',{}).get(team)
            reason=None
            if not first or not reference or str(reference.get('id'))!=first['participants']['shooter']['id'] or reference['clock'].lstrip('0')!=first['clock'].lstrip('0') or reference['points']!=first['points']:reason='Opening target differs from independently verified quarter extract'
            prefix=[e for e in events if first and e['period']==1 and e['sequence']<=first['sequence']]
            if first and first['period']!=1:reason='Opening score outside the verified first quarter'
            if any(d.get('sequence',10**9)<=first['sequence'] for d in discrepancies) if first else False:reason='Unresolved event discrepancy before the selected opening score'
            for e in prefix:
                for role in ('shooter','rebounder'):
                    actor=e.get('participants',{}).get(role)
                    if actor and not actor.get('id') and not e.get('teamRebound'):reason='Unresolved player identity in opening path'
            if reason:
                answer[team][target]={'available':False,'reason':reason};continue
            own_attempts=[e for e in prefix if e['team']==team and e['type'] in kinds]
            initial=own_attempts[0] if own_attempts else None
            misses=[]
            for miss in own_attempts:
                if miss.get('result')!='missed':continue
                rebound=None;next_attempt=None;terminal=None;team_rebounds=[]
                for after in prefix:
                    if after['sequence']<=miss['sequence']:continue
                    if after['type'] in ('shot','free_throw'):
                        next_attempt=after;break
                    if after['type']=='turnover':terminal=after;break
                    if after['type']=='rebound' and rebound is None:
                        if after.get('teamRebound'):team_rebounds.append(event(after))
                        else:rebound=after
                misses.append({'attempt':event(miss),'rebound':event(rebound),'teamRebounds':team_rebounds,'nextAttempt':event(next_attempt),'terminalTurnover':event(terminal),'rebounderScoredNext':bool(rebound['participants']['rebounder']['id']==next_attempt['participants']['shooter']['id'] and rebound['team']==next_attempt['team'] and next_attempt['result']=='made') if rebound and next_attempt else None,'reboundStatus':'player rebound observed' if rebound else 'team/dead-ball only' if team_rebounds else 'no player rebound before next attempt or turnover'})
            orebs=[e for e in prefix if e['team']==team and e['type']=='rebound' and not e.get('teamRebound') and e.get('reboundKind')=='offensive']
            direct=next((m for m in reversed(misses) if m['rebound'] and m['rebound']['team']==team and m['rebound']['kind']=='offensive' and m['nextAttempt'] and m['nextAttempt']['sequence']==first['sequence']),None)
            answer[team][target]={'available':True,'initialAttempt':event(initial),'firstScore':event(first),'attemptsBeforeScore':len(own_attempts),'misses':misses,'offensiveRebounds':[event(e) for e in orebs],'teamReboundsBeforeScore':sum(e['type']=='rebound' and e['team']==team and bool(e.get('teamRebound')) for e in prefix),'explicitPutbackFinish':first['type']=='shot' and bool(re.search(r'\bPutback\b|\bTip(?:[- ]?In)? (?:Layup|Dunk|Shot)\b',first['text'],re.I)),'directOffensiveReboundFinish':direct is not None,'rebounderFinished':direct['rebounderScoredNext'] if direct else None}
    return answer

def build(database,games,expected,parent_hash):
    db=sqlite3.connect(database);output={}
    for g in games:
        row=db.execute('SELECT r.id,r.source_hash,r.result FROM active a JOIN revisions r ON a.revision=r.id WHERE a.game_id=?',(g['id'],)).fetchone()
        if not row or row[1]!=g['sourceHash']:
            output[g['id']]={'sourceHash':g['sourceHash'],'available':False,'reason':'Matching full-game source ledger unavailable'};continue
        events=[json.loads(e[0]) for e in db.execute('SELECT event FROM events WHERE revision=? ORDER BY sequence',(row[0],))]
        result=json.loads(row[2]);reference=expected.get(g['id'],{})
        if reference.get('sourceHash')!=g['sourceHash']:
            output[g['id']]={'sourceHash':g['sourceHash'],'available':False,'reason':'Independent opening source hash mismatch'};continue
        output[g['id']]={'sourceHash':row[1],'ledgerRevision':row[0],'source':g['source'],'date':g['date'],'phase':g['phase'],'season':g.get('season'),'home':g['home'],'away':g['away'],'teams':derive(events,g,reference,result['discrepancies'])}
    db.close()
    body={'schemaVersion':1,'version':VERSION,'builderHash':CODE_HASH,'parentEvidenceContentHash':parent_hash,'games':output,'definitions':{'initialAttempt':'First shot/free throw for First Team Score; first field-goal attempt for field-goal-only.','offensiveRebound':'Explicit player-credited offensive rebound before the selected team opening score; team/dead-ball rebounds remain separate.','rebounderScoredNext':'Same identified rebounder made the next recorded scoring attempt before the selected team opening score. Unknown or absent next attempts remain unavailable.','putback':'Printed Putback or Tip Layup/Dunk/Shot description; direct second-chance finish shown separately, without inferring possession or defender.'}}
    body['contentHash']=digest(body);return body
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',type=Path,default=ROOT/'.pbp/archive.sqlite');p.add_argument('--output',type=Path,default=ROOT/'nba ftb shi/opening_paths_data.json');a=p.parse_args()
    data=json.loads((ROOT/'nba ftb shi/analyst_data.json').read_text());ref=json.loads((ROOT/'nba ftb shi/opening_data.json').read_text())['games'];body=build(a.database,data['games'],ref,data['meta']['evidenceContentHash']);a.output.write_bytes((packed(body)+'\n').encode());a.output.with_suffix('.js').write_bytes(('window.__FTB_OPENING_PATHS__ = '+packed(body)+';\n').encode());print(json.dumps({'games':len(body['games']),'availableTeamTargets':sum(t['available'] for g in body['games'].values() for team in g.get('teams',{}).values() for t in team.values()),'bytes':a.output.stat().st_size}))
