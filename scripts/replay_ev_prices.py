"""Replay retained public market fields and independently check current ESPN identities."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import fanduel_odds as fd

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'audits/2026-10-19-ev'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ARCHIVE)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'price-replay.json').exists():parser.error('Choose a new output folder to preserve the previous replay')
    snapshot=json.loads((args.input/'live-price-snapshot.json').read_text(encoding='utf-8'))
    envelopes=json.loads((args.input/'live-market-evidence.json').read_text(encoding='utf-8'))['envelopes']
    client=fd.Client()
    teams=sorted({q['team'] for f in snapshot['fixtures'].values() for q in f['quotes']})
    def roster(team):
        url='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+str(fd.TEAMS[team])+'/roster'
        p=client.json(url)
        if str(p.get('team',{}).get('id'))!=str(fd.TEAMS[team]):raise ValueError('Roster identity changed')
        people=[a for g in p['athletes'] for a in g.get('items',[g])]
        return team,{'source':url,'capturedAt':datetime.now(timezone.utc).isoformat(),'players':[{'id':str(a['id']),'name':a['displayName'],'team':team} for a in people]}
    with ThreadPoolExecutor(max_workers=4) as pool:
        rosters=dict(pool.map(roster,teams))
    differences=[];replayed=0;paired=0
    for entry in snapshot['fixtures'].values():
        fixture=entry['fixture'];team_roster=[p for t in [fixture['home'],fixture['away']] for p in rosters.get(t,{}).get('players',[])]
        for capture in entry['captures']:
            envelope=next(e for e in envelopes if e['eventId']==entry['fanduelEventId'] and e['tab']==capture['tab'])
            event=envelope['payload']['attachments']['events'][entry['fanduelEventId']]
            quotes,issues=fd.parse_markets(envelope['payload'],fixture,event,team_roster,capture['capturedAt'],capture['tab'])
            expected=[q for q in entry['quotes'] if q['market']==fd.TAB_MARKET[capture['tab']]]
            if sorted(quotes,key=lambda q:q['key'])!=sorted(expected,key=lambda q:q['key']):differences.append({'fixture':fixture['id'],'tab':capture['tab'],'expected':len(expected),'actual':len(quotes),'issues':issues})
            replayed+=len(quotes)
        groups={}
        for q in entry['quotes']:
            groups.setdefault((q['marketId'],q['playerId'],q['line'],q['capturedAt']),{})[q['side']]=q
        paired+=sum('over' in sides and 'under' in sides for sides in groups.values())
    result={'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'passed' if not differences else 'failed','snapshotCapturedAt':snapshot['checkedAt'],
            'quotesReplayed':replayed,'matchingTwoWayPairs':paired,'sourceEnvelopes':len(envelopes),'currentRosterProof':rosters,'differences':differences,
            'interpretation':'Minimal captured source fields replay exactly through the parser against independently retrieved current rosters. This does not prove historic market executability or source stability after capture. No vig removal for overlapping milestones.'}
    (args.output/'price-replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='currentRosterProof'}))
    return bool(differences)

if __name__=='__main__':raise SystemExit(main())
