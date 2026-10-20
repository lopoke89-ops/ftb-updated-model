"""Independent accepted-component audit from stored actions and PDF box extracts."""
import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATS=['fgm','fga','three_pm','three_pa','ftm','fta','pts','ast','stl','blk','tov','oreb','dreb','reb']
def run(database,library,output):
    db=sqlite3.connect(database);checks=0;failures=[];box_totals=Counter();event_totals=Counter();component_games=Counter();games=0;events_count=0;unavailable=Counter();periods=Counter()
    for gid,rid,result_json,source_hash,pages_json in db.execute('SELECT a.game_id,a.revision,r.result,r.source_hash,r.pages FROM active a JOIN revisions r ON a.revision=r.id'):
        games+=1;r=json.loads(result_json);record=json.loads((Path(library)/'records'/(gid+'.json')).read_text(encoding='utf-8'));counts=defaultdict(Counter)
        if source_hash!=record['sha256']:failures.append({'game':gid,'kind':'source mismatch'})
        events=[json.loads(x[0]) for x in db.execute('SELECT event FROM events WHERE revision=? ORDER BY sequence',(rid,))];events_count+=len(events);periods[len(r.get('periods',{}))]+=1
        for e in events:
            participants=e.get('participants',{});text=e['text'];team=e['team']
            shooter=participants.get('shooter',{}).get('id')
            if shooter:
                c=counts[(team,shooter)];made=not text.startswith('MISS ');ft='Free Throw' in text
                c['fta' if ft else 'fga']+=1;c['ftm' if ft else 'fgm']+=made
                three=not ft and '3PT' in text
                c['three_pa']+=three;c['three_pm']+=three and made;c['pts']+=(1 if ft else 3 if three else 2)*made
            for role,stat in [('assister','ast'),('blocker','blk'),('stealer','stl'),('committer','tov')]:
                pid=participants.get(role,{}).get('id')
                if pid and not (role=='committer' and e.get('teamTurnover')):counts[(team,pid)][stat]+=1
            pid=participants.get('rebounder',{}).get('id')
            if pid and not e.get('teamRebound'):
                c=counts[(team,pid)];c['reb']+=1
                if e.get('reboundKind') in ('offensive','defensive'):c['oreb' if e['reboundKind']=='offensive' else 'dreb']+=1
        for stat in STATS:
            if not r['components'].get(stat):unavailable[stat]+=1;continue
            component_games[stat]+=1
            for p in record['player_rows']:
                if not p['played']:continue
                observed=counts[(p['team'],str(p['espn_player_id']))][stat];expected=p[stat];checks+=1;box_totals[stat]+=expected;event_totals[stat]+=observed
                if observed!=expected:failures.append({'game':gid,'team':p['team'],'player':p['nba_name'],'stat':stat,'observed':observed,'expected':expected})
        checks+=1
        if len({e['sequence'] for e in events})!=len(events):failures.append({'game':gid,'kind':'duplicate sequence'})
        # Stored source content really is the hash-linked official file.
        source=db.execute('SELECT pdf FROM sources WHERE hash=?',(source_hash,)).fetchone()[0];checks+=1
        if hashlib.sha256(source).hexdigest()!=source_hash:failures.append({'game':gid,'kind':'stored PDF hash mismatch'})
    for digest,source in db.execute('SELECT hash,source FROM parsers'):
        checks+=1
        if hashlib.sha256(source.encode('utf-8')).hexdigest()!=digest:failures.append({'kind':'retained parser source hash mismatch','hash':digest})
    report={'games':games,'events':events_count,'periodCounts':dict(periods),'checks':checks,'differences':failures,'acceptedComponentGames':dict(component_games),'withheldComponentGames':dict(unavailable),'sameSampleBoxTotals':dict(box_totals),'sameSampleEventTotals':dict(event_totals),'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'foreignKeys':db.execute('PRAGMA foreign_key_check').fetchall(),'method':'Independent text/result recount from stored credits, compared with the library final-box extracts. Identity mappings and rebound links remain shared evidence, not independently proven defender or possession assignments.'}
    Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('sameSampleBoxTotals','sameSampleEventTotals','differences')},separators=(',',':')));db.close();return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--library',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if run(a.database,a.library,a.output)['differences']:raise SystemExit(1)
