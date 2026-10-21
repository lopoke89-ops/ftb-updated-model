"""Independent source-action checks for published opening path counts and links."""
import argparse,hashlib,json,re,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def audit(database,data):
 db=sqlite3.connect(database);checks=0;totals={'teamTargets':0,'initialAttempts':0,'misses':0,'offensiveRebounds':0,'printedPutbacks':0,'rebounderScoredNext':0};failures=[]
 for gid,g in data['games'].items():
  if not g.get('teams'):continue
  row=db.execute('SELECT r.id,r.source_hash FROM active a JOIN revisions r ON a.revision=r.id WHERE a.game_id=?',(gid,)).fetchone();assert row and row[1]==g['sourceHash']
  events=[json.loads(r[0]) for r in db.execute('SELECT event FROM events WHERE revision=? ORDER BY sequence',(row[0],))];by_id={e['sequence']:e for e in events}
  for team,targets in g['teams'].items():
   for target,p in targets.items():
    if not p['available']:continue
    kinds=('shot','free_throw') if target=='first-score' else ('shot',)
    own=[e for e in events if e['team']==team and e['type'] in kinds];first=next(e for e in own if e['result']=='made');prefix=[e for e in events if e['period']==1 and e['sequence']<=first['sequence']];totals['teamTargets']+=1
    assert p['firstScore']['sequence']==first['sequence'] and p['firstScore']['playerId']==first['participants']['shooter']['id'];checks+=2
    assert p['initialAttempt']['sequence']==own[0]['sequence'];totals['initialAttempts']+=1;checks+=1
    orebs=[e['sequence'] for e in prefix if e['type']=='rebound' and e['team']==team and e.get('reboundKind')=='offensive' and not e.get('teamRebound')];assert [e['sequence'] for e in p['offensiveRebounds']]==orebs;totals['offensiveRebounds']+=len(orebs);checks+=1
    putback=bool(first['type']=='shot' and re.search(r'Putback|Tip(?:[- ]?In)? (?:Layup|Dunk|Shot)',first['text'],re.I));assert p['explicitPutbackFinish']==putback;totals['printedPutbacks']+=putback;checks+=1
    missed=[e['sequence'] for e in own if e['sequence']<=first['sequence'] and e['result']=='missed'];assert [m['attempt']['sequence'] for m in p['misses']]==missed;checks+=1
    for m in p['misses']:
     totals['misses']+=1;attempt=by_id[m['attempt']['sequence']];candidate=[e for e in prefix if e['sequence']>attempt['sequence']]
     boundary=next((e for e in candidate if e['type'] in ('shot','free_throw','turnover')),None);early=[e for e in candidate if not boundary or e['sequence']<boundary['sequence']]
     credited=next((e for e in early if e['type']=='rebound' and not e.get('teamRebound')),None)
     assert (m['rebound']['sequence'] if m['rebound'] else None)==(credited['sequence'] if credited else None)
     nxt=boundary if boundary and boundary['type'] in ('shot','free_throw') else None
     assert (m['nextAttempt']['sequence'] if m['nextAttempt'] else None)==(nxt['sequence'] if nxt else None)
     if credited:assert credited['linkedAttemptSequence']==attempt['sequence']
     same=bool(credited['team']==nxt['team'] and credited['participants']['rebounder']['id']==nxt['participants']['shooter']['id'] and nxt['result']=='made') if credited and nxt else None
     assert m['rebounderScoredNext']==same;totals['rebounderScoredNext']+=same is True;checks+=4
 db.close();return {'checks':checks,'totals':totals,'failures':failures,'dataHash':data['contentHash'],'auditorHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'method':'Independently query active source actions, reconstruct prefix counts and stop-at-next-attempt/turnover links; do not import production path helpers.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--database',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.database,json.loads(a.data.read_text()));a.output.write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps(r))
