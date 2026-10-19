"""Separate local Parlay research receipts and authoritative NBA-PDF outcomes."""
import argparse
import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nba ftb shi'
MARKETS = {'first-team-basket', 'points', 'threes'}
TARGETS = {'first-team-score-including-free-throws', 'first-team-made-field-goal'}
CODE_FILES = ('parlay.js','scouting_history.js','lineups.js','lineup_projections.js','parlay_transition.js','parlay_research.js','parlay_research_config.js','parlay_ui.js','analyst_ui.js')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def dataset_digest(games):
    # Match the collector's canonical, ASCII-escaped season hash exactly.
    return hashlib.sha256(json.dumps(games, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()).hexdigest()

def utc():
    return datetime.now(timezone.utc)

def iso(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('Timestamp must have a timezone')
    return d.astimezone(timezone.utc)

def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line] if Path(path).exists() else []

def sealed_lines(path):
    records = lines(path)
    for record in records:
        content = {key:value for key,value in record.items() if key != 'sealedHash'}
        if record.get('sealedHash') != digest(content):
            raise ValueError('Research journal integrity check failed')
    return records

def release_hashes():
    return {name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in CODE_FILES}

def append(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()

def verify_fixture(fixture, now):
    fid = str(fixture.get('id', ''))
    if not fid.isdigit():
        raise ValueError('A source fixture ID is required')
    url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=' + fid
    with urlopen(Request(url, headers={'User-Agent': 'FTB research/1.0'}), timeout=20) as response:
        payload = json.load(response)
    competition = payload['header']['competitions'][0]
    aliases = {'GS':'GSW','NY':'NYK','SA':'SAS','NO':'NOP','WSH':'WAS','UTAH':'UTA','PHO':'PHX'}
    roles = {c['homeAway']:aliases.get(c['team']['abbreviation'],c['team']['abbreviation']) for c in competition['competitors']}
    if roles != {'home':fixture['home'], 'away':fixture['away']} or str(payload['header']['id']) != fid:
        raise ValueError('Fixture differs from the current source schedule')
    if competition['status']['type']['state'] != 'pre':
        raise ValueError('Fixture is no longer pregame')
    tip = competition.get('date') or payload['header']['date']
    minutes = (iso(tip) - now).total_seconds()/60
    if not 0 < minutes <= 15:
        raise ValueError('Research receipt must be within 15 minutes before verified tipoff')
    return {'url':url, 'scheduledTipoff':tip, 'verifiedAt':now.isoformat(), 'captureHash':digest(payload), 'payload':payload}

def validate_export(record):
    if record.get('schemaVersion') not in (2, 3) or not isinstance(record.get('selections'), list):
        raise ValueError('Unsupported Parlay export schema')
    if record.get('firstBasketTarget') not in TARGETS:
        raise ValueError('Unknown first-score definition')
    seen = set()
    for s in record['selections']:
        key = (s.get('fixtureId'), s.get('team'), s.get('market'))
        if s.get('market') not in MARKETS or key in seen:
            raise ValueError('Invalid or duplicate market slot')
        seen.add(key)
        production,adaptive=s.get('pick'),(s.get('research') or {}).get('pick')
        if s['market']!='first-team-basket' and production and adaptive and production['id']==adaptive['id'] and production.get('seasonTarget')!=adaptive.get('seasonTarget'):
            raise ValueError('Models must share the frozen target for the same candidate')
        for pick in [s.get('pick'), (s.get('research') or {}).get('pick')] + list(((s.get('research') or {}).get('baselines') or {}).values()):
            if pick is None:
                continue
            if not str(pick.get('id', '')).isdigit() or not isinstance(pick.get('score'), (int, float)) or isinstance(pick['score'], bool) or not math.isfinite(pick['score']):
                raise ValueError('Invalid selected identity or evidence score')
            target = pick.get('seasonTarget')
            if s['market'] != 'first-team-basket' and (not target or not isinstance(target.get('threshold'), int) or target['threshold'] < 0 or not math.isfinite(target.get('average', float('nan'))) or math.ceil(target['average']-1e-10) != target['threshold']):
                raise ValueError('Invalid frozen season-average target')
    return record

def record_export(record, store, snapshot=None, now=None, verifier=verify_fixture, hashes=None, archive_hash=None, prospective=False):
    record = validate_export(record)
    now = now or utc()
    received = {'id':str(uuid.uuid4()), 'receivedAt':now.isoformat(), 'recordType':'research-snapshot', 'export':record, 'fixtureEvidence':{}}
    if prospective:
        if record['schemaVersion'] != 3 or record.get('analysisMode') != 'pregame' or not record.get('upcoming'):
            raise ValueError('Only current schema upcoming exports can be received prospectively')
        if abs((now-iso(record['capturedAt'])).total_seconds()) > 60:
            raise ValueError('Export is stale, future-dated or backdated; import as a research snapshot')
        if not hashes or record.get('modelHashes') != hashes:
            raise ValueError('Code/configuration differs from this local research release')
        expected_protocol = hashlib.sha256((ROOT/'PARLAY_RESEARCH_PROTOCOL.json').read_bytes()).hexdigest()
        if record.get('protocolHash') != expected_protocol:
            raise ValueError('Research protocol differs from this release')
        if record.get('archiveEvidenceHash') != archive_hash:
            raise ValueError('Prior-season source hash differs from the verified archive')
        if not snapshot or snapshot.get('meta', {}).get('season') != '2026-27' or snapshot['meta'].get('evidenceContentHash') != record.get('currentEvidenceHash') or dataset_digest(snapshot['games']) != record['currentEvidenceHash']:
            raise ValueError('Matching verified current-season snapshot is required')
        validate_final_dataset(snapshot)
        fixture_ids = set()
        for s in record['selections']:
            f = s.get('fixture') or {}
            if str(f.get('id')) != str(s.get('fixtureId')) or f.get('season') != '2026-27' or f.get('phase') not in ('regular-season', 'playoffs') or {s['team'], s['opponent']} != {f.get('home'), f.get('away')}:
                raise ValueError('Parlay slot does not match a supported fixture')
            if f.get('date') != record.get('date') or f['phase'] != record.get('competition') or not s.get('research'):
                raise ValueError('Use one competition/date and enable the research comparison before recording')
            if f['id'] not in received['fixtureEvidence']:
                received['fixtureEvidence'][f['id']] = verifier(f, now)
            fixture_ids.add(f['id'])
            if snapshot['games'] and any(g['date'] >= f['date'] for g in snapshot['games'] if g['id'] in {r['gameId'] for r in (s.get('pick') or {}).get('sources', [])}):
                raise ValueError('Selected-day or future result leaked into pregame evidence')
            if s.get('research') and s['research'].get('configurationHash') != read(SOURCE/'parlay_research_config.json')['configurationHash']:
                raise ValueError('Research configuration hash differs')
            if s['research'].get('pick') and s['research']['pick'].get('statsThrough') and s['research']['pick']['statsThrough'] >= f['date']:
                raise ValueError('Future research input date')
            for pick in (s.get('pick'),s['research'].get('pick')):
                if pick and not isinstance(pick.get('provisional'),bool):
                    raise ValueError('Selection eligibility status is required')
                if pick and s['market']=='first-team-basket' and pick['provisional'] is False:
                    c = pick.get('confirmation') or {}
                    age = (now-iso(c['capturedAt'])).total_seconds() if c.get('capturedAt') else float('inf')
                    url = 'https://stats.nba.com/js/data/leaders/00_daily_lineups_'+f['date'].replace('-','')+'.json'
                    if c.get('id') != pick['id'] or c.get('team') != s['team'] or c.get('fixtureId') != f['id'] or c.get('status') != 'confirmed' or c.get('source') != url or not 0 <= age <= 300:
                        raise ValueError('Final first-score record requires fresh fixture-matched NBA starter confirmation')
        if not fixture_ids:
            raise ValueError('No fixture slots supplied')
        for fid in fixture_ids:
            group = [s for s in record['selections'] if s['fixtureId'] == fid]
            f = group[0]['fixture']
            if {(s['team'],s['market']) for s in group} != {(team,market) for team in (f['home'],f['away']) for market in MARKETS}:
                raise ValueError('All three market slots for both teams are required')
        received['recordType'] = 'prospective-research'
        received['currentSnapshotHash'] = record['currentEvidenceHash']
        received['currentSnapshotFileHash'] = digest(snapshot)
        snapshot_path = Path(store)/'snapshots'/(received['currentSnapshotFileHash']+'.json')
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        if snapshot_path.exists() and digest(read(snapshot_path)) != digest(snapshot):
            raise ValueError('Stored snapshot with this hash differs')
        if not snapshot_path.exists():
            snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    prior = [r for r in sealed_lines(Path(store)/'receipts.jsonl') if r['recordType']==received['recordType'] and r['export'].get('date')==record.get('date') and r['export'].get('modelHashes')==record.get('modelHashes') and r['export']['firstBasketTarget']==record['firstBasketTarget'] and {s.get('fixtureId') for s in r['export']['selections']}=={s.get('fixtureId') for s in record['selections']}]
    received['revisionOf'] = prior[-1]['id'] if prior else None
    received['sealedHash'] = digest(received)
    append(Path(store)/'receipts.jsonl', received)
    return {'id':received['id'], 'recordType':received['recordType'], 'sealedHash':received['sealedHash']}

def settle(store, dataset, now=None):
    now = now or utc()
    validate_final_dataset(dataset)
    games = {g['id']:g for g in dataset['games']}
    outcomes = sealed_lines(Path(store)/'outcomes.jsonl')
    existing = {(r['receiptId'],r['fixtureId'],r['sourceHash']) for r in outcomes}
    updated = pending = 0
    for receipt in sealed_lines(Path(store)/'receipts.jsonl'):
        for fid in {str(s.get('fixtureId')) for s in receipt['export']['selections']}:
            g = games.get(fid)
            if not g:
                pending += 1
                continue
            if g.get('boxScoreSource') != 'NBA official final box' or not g.get('sourceHash'):
                raise ValueError('Settlement requires a verified NBA final gamebook')
            if (receipt['id'],fid,g['sourceHash']) in existing:
                continue
            if receipt['recordType']=='prospective-research' and any(s['fixture']['date'] != g['date'] or s['fixture']['phase'] != g['phase'] for s in receipt['export']['selections'] if str(s.get('fixtureId'))==fid):
                raise ValueError('Final PDF fixture date/competition differs from the frozen receipt')
            results = []
            for s in receipt['export']['selections']:
                if str(s.get('fixtureId')) != fid:
                    continue
                r = s.get('research') or {}
                choices = {'production':s.get('pick'), 'adaptive':r.get('pick'), **(r.get('baselines') or {})}
                for model,pick in choices.items():
                    actual = next((p for p in g['teams'][s['team']]['players'] if pick and str(p['id']) == pick['id']), None)
                    played = bool(actual and actual['played'])
                    threshold = None if s['market'] == 'first-team-basket' or not pick else pick['seasonTarget']['threshold']
                    scorer = g['firstFieldGoals' if receipt['export']['firstBasketTarget']=='first-team-made-field-goal' else 'firstScores'][s['team']]['id']
                    hit = None if not pick else str(scorer)==pick['id'] if s['market']=='first-team-basket' else played and actual['points' if s['market']=='points' else 'threeMade']>=threshold
                    results.append({'team':s['team'],'market':s['market'],'model':model,'id':pick['id'] if pick else None,'hit':hit,'played':played,'threshold':threshold,
                                    'provisional':pick.get('provisional') if pick else None,'teamGames':(s.get('transition') or {}).get('teamGames'),
                                    'targetBasis':(pick.get('targetBasis') or (s.get('transition') or {}).get('targetBasis')) if pick else None})
            previous = [r for r in outcomes if r['receiptId']==receipt['id'] and r['fixtureId']==fid]
            outcome = {'receiptId':receipt['id'],'fixtureId':fid,'date':g['date'],'observedAt':now.isoformat(),'source':g['source'],'sourceHash':g['sourceHash'],
                'revisionOf':previous[-1]['sourceHash'] if previous else None,'recordType':receipt['recordType'],'results':results}
            outcome['sealedHash'] = digest(outcome)
            append(Path(store)/'outcomes.jsonl', outcome)
            outcomes.append(outcome)
            updated += 1
    return {'updated':updated,'pending':pending}

def validate_final_dataset(dataset):
    if not isinstance(dataset.get('games'), list) or len({g['id'] for g in dataset['games']}) != len(dataset['games']):
        raise ValueError('Invalid or duplicate final game dataset')
    if dataset.get('meta', {}).get('season') == '2026-27' and dataset_digest(dataset['games']) != dataset['meta'].get('evidenceContentHash'):
        raise ValueError('Final dataset content hash differs')
    for g in dataset['games']:
        if g.get('boxScoreSource') != 'NBA official final box' or not g.get('sourceHash') or not g.get('source', '').startswith('https://') or '.nba.com/' not in g['source']:
            raise ValueError('Settlement requires the verified NBA PDF dataset')
        for team in (g['home'], g['away']):
            players = [p for p in g['teams'][team]['players'] if p['played']]
            if sum(p['points'] for p in players) != g['teams'][team]['points'] or sum(bool(p['starter']) for p in players) != 5:
                raise ValueError('Final team statistics do not reconcile')
            for p in players:
                if p.get('statsSourceHash') != g['sourceHash'] or 2*p['fgm']+p['threeMade']+p['ftm'] != p['points'] or p['fgm'] > p['fga'] or p['threeMade'] > p['threeAttempted'] or p['ftm'] > p['fta']:
                    raise ValueError('Final player statistics do not reconcile')
            for key in ('firstScores','firstFieldGoals'):
                if not any(str(p['id']) == str(g[key][team]['id']) for p in players):
                    raise ValueError('Unresolved final opening scorer')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['import','record','settle'])
    parser.add_argument('--store', type=Path, default=ROOT/'.parlay-research')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    if not args.input:
        parser.error('--input is required (export for import/record, verified season dataset for settle)')
    if args.action == 'settle':
        result = settle(args.store, read(args.input))
    else:
        hashes = release_hashes()
        result = record_export(read(args.input), args.store, read(args.snapshot) if args.snapshot else None,
                               hashes=hashes, archive_hash=read(SOURCE/'analyst_data.json')['meta']['evidenceContentHash'], prospective=args.action=='record')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
