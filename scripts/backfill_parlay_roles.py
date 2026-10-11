"""Retain dated NBA roles only after matching all five PDF-verified starters.

This enriches Parlay evidence without changing the frozen Analyst dataset or any
PDF statistics. Captures are retrospective observations, never pregame notices.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unicodedata
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = {'PG', 'SG', 'SF', 'PF', 'C'}


def encoded(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value).lower() if c.isascii() and c.isalnum())


def match_roles(game, payload, source, source_hash, captured):
    matches = [g for g in payload.get('games', []) if g.get('gameStatus') == 3
               and g.get('homeTeam', {}).get('teamAbbreviation') == game['home']
               and g.get('awayTeam', {}).get('teamAbbreviation') == game['away']]
    if len(matches) != 1:
        return []
    nba = matches[0]
    roles = []
    for side, team in (('homeTeam', game['home']), ('awayTeam', game['away'])):
        starters = [p for p in game['teams'][team]['players'] if p['played'] and p['starter']]
        listed = [p for p in nba[side].get('players', []) if p.get('position') in POSITIONS]
        if len(starters) != 5 or len(listed) != 5 or len({p['position'] for p in listed}) != 5 or len({str(p.get('personId')) for p in listed}) != 5:
            continue
        matched = []
        for p in listed:
            candidates = [r for r in starters if norm(p.get('playerName', '')) in {norm(r['name']), norm(r.get('nbaName', r['name']))}]
            if len(candidates) != 1 or p.get('lineupStatus') != 'Confirmed' or p.get('rosterStatus') != 'Active':
                break
            matched.append({'playerId': candidates[0]['id'], 'position': p['position'], 'team': team,
                            'effectiveGameDate': game['date'], 'gameId': game['id'], 'nbaGameId': str(nba['gameId']),
                            'nbaPlayerId': str(p['personId']), 'source': source, 'sourceHash': source_hash,
                            'gamebookSourceHash': game['sourceHash'], 'capturedAt': captured,
                            'status': 'Postgame NBA lineup role; not pregame confirmation'})
        if len(matched) == 5 and len({p['playerId'] for p in matched}) == 5:
            roles.extend(matched)
    return roles


def collect_date(day, library):
    source = 'https://stats.nba.com/js/data/leaders/00_daily_lineups_' + day.replace('-', '') + '.json'
    cache = library / (day + '.json')
    if cache.exists():
        retained = json.loads(cache.read_text(encoding='utf-8'))
        if retained['source'] != source or hashlib.sha256(encoded(retained['payload'])).hexdigest() != retained['sha256']:
            raise ValueError('Invalid retained lineup capture: ' + day)
        return retained
    request = urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nba.com/'})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload.get('games'), list):
        raise ValueError('NBA lineup games unavailable: ' + day)
    retained = {'source': source, 'capturedAt': datetime.now(timezone.utc).isoformat(),
                'sha256': hashlib.sha256(encoded(payload)).hexdigest(), 'payload': payload}
    cache.write_bytes(encoded(retained))
    return retained


def run(library, workers=4):
    source = ROOT / 'nba ftb shi'
    data = json.loads((source / 'analyst_data.json').read_text(encoding='utf-8'))
    supplement = json.loads((source / 'parlay_data.json').read_text(encoding='utf-8'))
    library.mkdir(parents=True, exist_ok=True)
    dates = sorted({g['date'] for g in data['games']})
    captures, failures = {}, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(collect_date, day, library): day for day in dates}
        for future in as_completed(jobs):
            day = jobs[future]
            try:
                captures[day] = future.result()
            except Exception as exc:
                failures.append({'date': day, 'error': str(exc)})
    roles, unmatched = [], []
    for game in data['games']:
        capture = captures.get(game['date'])
        found = match_roles(game, capture['payload'], capture['source'], capture['sha256'], capture['capturedAt']) if capture else []
        roles.extend(found)
        for team in (game['home'], game['away']):
            if sum(r['team'] == team for r in found) != 5:
                unmatched.append({'gameId': game['id'], 'date': game['date'], 'team': team})
    meta = {'version': 'nba-pdf-matched-roles-v1', 'parentEvidenceContentHash': data['meta']['evidenceContentHash'],
            'contentHash': hashlib.sha256(encoded(roles)).hexdigest(), 'roleRecords': len(roles),
            'matchedTeamGames': len(roles) // 5, 'totalTeamGames': len(data['games']) * 2,
            'capturedDates': len(captures), 'requestedDates': len(dates), 'failedDates': failures, 'unmatchedTeamGames': unmatched,
            'interpretation': 'Dated postgame NBA role observations matched to all five PDF starters. Exact PDF roles take precedence. Earlier roles may support later games; retrospective captures are not pregame announcement evidence.'}
    (library / 'coverage.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    if meta['matchedTeamGames'] < .9 * meta['totalTeamGames']:
        raise ValueError('Fewer than 90% of team games matched; retained captures but did not publish enrichment')
    supplement.update(datedRoleEvidence=roles, roleEvidenceMeta=meta)
    (source / 'parlay_data.json').write_bytes(encoded(supplement))
    (source / 'parlay_data.js').write_bytes(b'window.__FTB_PARLAY_DATA__ = ' + encoded(supplement) + b';\n')
    print(json.dumps({k: v for k, v in meta.items() if k not in ('unmatchedTeamGames', 'failedDates')}, indent=2))
    print('Unmatched team games:', len(unmatched), 'Failed dates:', len(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    run(args.library, args.workers)
