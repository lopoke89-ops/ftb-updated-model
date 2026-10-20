"""Auditable same-game event identity crosswalk; never imports provider statistics."""
import json,re,hashlib
from pathlib import Path

def clock(value):
    parts=value.lstrip(':').split(':')
    return round((float(parts[0])*60+float(parts[1])) if len(parts)==2 else float(parts[0]),1)
def resolve(events,game,record,path):
    path=Path(path)
    if not path.exists():return None
    raw=path.read_bytes();data=json.loads(raw);meta=json.loads(path.with_suffix('.source.json').read_text(encoding='utf-8'));digest=hashlib.sha256(raw).hexdigest()
    if digest!=meta['sha256'] or (record.get('pbpIdentitySource',{}).get('sha256') not in (None,digest)) or data.get('header',{}).get('id')!=game['id']:raise ValueError('Identity evidence game/hash mismatch')
    teams={str(t['team']['id']):{'GS':'GSW','NY':'NYK','SA':'SAS','NO':'NOP','WSH':'WAS','UTAH':'UTA','PHO':'PHX'}.get(t['team']['abbreviation'],t['team']['abbreviation']) for t in data['header']['competitions'][0]['competitors']}
    if set(teams.values())!={game['home'],game['away']}:raise ValueError('Identity evidence teams mismatch')
    roster={(p['team'],str(p['espn_player_id'])) for p in record['player_rows'] if p.get('espn_player_id')}
    index={}
    for play in data.get('plays',[]):index.setdefault((play['period']['number'],clock(play['clock']['displayValue'])),[]).append(play)
    by_row={}
    for e in events:
        if e.get('rowId'):by_row.setdefault(e['rowId'],[]).append(e)
    resolved=0
    for e in events:
        if e.get('clock') is None:continue
        peers=by_row.get(e.get('rowId'),[])
        for role,person in e['participants'].items():
            if person.get('id') or person.get('nonPlayer') or (role=='rebounder' and e.get('teamRebound')) or (role=='committer' and e.get('teamTurnover')):continue
            candidates=[]
            for play in index.get((e['period'],clock(e['clock'])),[]):
                typ=play.get('type',{}).get('text','').lower();text=play.get('text','').lower();ps=[str(x['athlete']['id']) for x in play.get('participants',[]) if x.get('athlete',{}).get('id')];team=teams.get(str(play.get('team',{}).get('id')));n=None
                if role in ('shooter','assister'):
                    if not play.get('shootingPlay') or not ps:continue
                    if ('free throw' in typ)!=(e['type']=='free_throw'):continue
                    if int(play.get('pointsAttempted',0))!=e['shotValue'] or bool(play.get('scoringPlay'))!=(e['result']=='made') or team!=e['team']:continue
                    ordinal=re.search(r'(\d+) of (\d+)',text)
                    if e['type']=='free_throw' and e.get('freeThrowAttempt') and (not ordinal or int(ordinal[1])!=e['freeThrowAttempt'] or int(ordinal[2])!=e['freeThrowAwarded']):continue
                    if e.get('printedScore') and [play.get('homeScore'),play.get('awayScore')]!=e['score']:continue
                    if role=='assister':
                        if ' assists' not in text or len(ps)<2:continue
                        shooter=e['participants']['shooter']
                        if shooter.get('id') and ps[0]!=shooter['id']:continue
                        n=1
                    else:n=0
                elif role=='rebounder':
                    if 'rebound' not in typ or team!=e['team']:continue
                    n=0
                elif role=='committer':
                    if not ('turnover' in typ or 'turnover' in text or typ in ('traveling','traveling turnover')) or team!=e['team']:continue
                    n=0
                elif role in ('incoming','outgoing'):
                    if 'substitution' not in typ or team!=e['team'] or len(ps)<2:continue
                    n=0 if role=='incoming' else 1;other=e['participants'].get('outgoing' if n==0 else 'incoming',{})
                    if other.get('id') and ps[1-n]!=other['id']:continue
                elif role in ('fouler','otherFouler'):
                    if not ('foul' in typ or 'technical' in typ or 'foul' in text) or team!=person.get('team',e['team']):continue
                    if ('technical' in text)!=bool(re.search(r'technical|defensive three seconds',e['text'],re.I)):continue
                    n=0
                elif role in ('blocker','stealer'):
                    if len(ps)<2 or ('blocks' if role=='blocker' else 'steals') not in text:continue
                    counterpart=next((p for p in peers if p['type']==('shot' if role=='blocker' else 'turnover')),None)
                    if counterpart:
                        cp=counterpart['participants'].get('shooter' if role=='blocker' else 'committer',{})
                        if cp.get('id') and cp['id']!=ps[0]:continue
                    n=1
                if n is None or n>=len(ps):continue
                pid=ps[n]
                if (person.get('team',e['team']),pid) not in roster or person.get('candidates') and pid not in person['candidates']:continue
                candidates.append((pid,play['id']))
            unique={pid for pid,_ in candidates}
            if len(unique)==1:
                pid=next(iter(unique));person.update(id=pid,method='same-game period/clock/action/role provider event-ID crosswalk; PDF statistics unchanged',identityEvidence={'url':meta['url'],'sha256':digest,'playIds':sorted({play for _,play in candidates}),'capturedAt':meta['capturedAt']},sourceIds={'espnPlayerId':pid,'nbaPlayerId':next((str(r['nbaPlayerId']) for r in game.get('identityCrosswalk',[]) if str(r.get('playerId'))==pid and r.get('team')==person.get('team',e['team']) and r.get('gamebookSourceHash')==record['sha256'] and r.get('nbaPlayerId')),person.get('sourceIds',{}).get('nbaPlayerId'))});resolved+=1
    return {'url':meta['url'],'sha256':digest,'capturedAt':meta['capturedAt'],'resolvedRoles':resolved,'path':str(path)}
