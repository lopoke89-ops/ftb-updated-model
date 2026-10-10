"""NBA gamebook final boxes are authoritative for the completed 2025-26 stats.

The workbook continues to supply first-score events and specific role references.
Original ESPN captures and workbooks are retained as historical source evidence.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIELDS = ('points', 'fgm', 'fga', 'threeMade', 'threeAttempted', 'ftm', 'fta',
          'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'fouls',
          'offensiveRebounds', 'defensiveRebounds', 'plusMinus', 'minutesSeconds')


def content_hash(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def load(base=BASE):
    path = Path(base) / 'official_boxscores.json'
    if not path.exists():
        raise FileNotFoundError('NBA official statistics ledger missing; run build_official_gamebook_data.py. Refusing to restore superseded ESPN statistics.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if content_hash(data['games']) != data['meta']['contentHash']:
        raise ValueError('Official gamebook ledger hash mismatch')
    if data['meta']['season'] != '2025-26' or len(data['games']) != 1322:
        raise ValueError('Incomplete official gamebook ledger')
    return data


def apply_analysis(data, official):
    if official is None:
        return data
    if {g['id'] for g in data['games']} != set(official['games']):
        raise ValueError('Official game coverage differs from analysis')
    prior = data['meta'].get('supersedesEvidenceContentHash', data['meta']['evidenceContentHash'])
    for game in data['games']:
        source = official['games'][game['id']]
        if (game['date'], game['home'], game['away'], game['phase']) != tuple(source[k] for k in ('date', 'home', 'away', 'phase')):
            raise ValueError('Official fixture mismatch: ' + game['id'])
        for team, box in game['teams'].items():
            actual = source['teams'][team]
            by_id = {p['id']: p for p in box['players'] if p['id']}
            players = []
            for pid, row in actual.items():
                old = by_id.pop(pid, {})
                players.append({**old, **row, 'id': pid,
                                'name': old.get('name') or row['nbaName'],
                                'rawPosition': old.get('rawPosition') or row.get('officialPosition') or '',
                                'played': True, 'statsSource': source['source'],
                                'statsSourceHash': source['sha256']})
            # Preserve dated roster membership, but a player absent from the
            # official played rows must never contribute an appearance/start.
            for old in by_id.values():
                players.append({**old, **{k: None for k in FIELDS}, 'minutes': None,
                                'played': False, 'starter': False,
                                'status': source.get('nonappearances', {}).get(team, {}).get(old['id'], 'not a played row in NBA final box'),
                                'statsSource': source['source'], 'statsSourceHash': source['sha256']})
            starters = [p['id'] for p in players if p['starter']]
            if len(starters) != 5 or sum(p['points'] for p in players if p['played']) != box['points']:
                raise ValueError('Official team reconciliation failed: ' + game['id'] + ' ' + team)
            old_order = [pid for pid in box['starters'] if pid in starters]
            box['players'] = players
            box['starters'] = old_order + [pid for pid in starters if pid not in old_order]
            for actors in (game['firstScores'], game['firstFieldGoals']):
                if actors[team]['id'] not in actual:
                    raise ValueError('First-scoring actor missing from official final box')
        if 'openingSource' not in game:
            game['openingSource'], game['openingSourceHash'] = game['source'], game['sourceHash']
        game.update(source=source['source'], sourceHash=source['sha256'],
                    boxScoreSource='NBA official final box', capturedAt=source['capturedAt'],
                    lineupSource='NBA official final box')
    data['meta'].update(datasetId='nba-2025-26-analysis-evidence-official-gamebooks-v1',
                        builtAt=official['meta']['builtAt'],
                        supersedesEvidenceContentHash=prior,
                        statisticalAuthority='Downloaded NBA official gamebook final boxes; PDF wins every conflict',
                        officialBoxscoreContentHash=official['meta']['contentHash'],
                        optionalStatGaps={},
                        sourceCaptureMeaning='NBA final-box PDF statistics; retained ESPN opening-play evidence and dated role references')
    data['meta']['evidenceContentHash'] = content_hash({'games': data['games'], 'datedRoleEvidence': data['datedRoleEvidence']})
    return data


def apply_canonical(players, meta, official):
    if official is None:
        return
    by_player = defaultdict(list)
    for g in official['games'].values():
        for team, rows in g['teams'].items():
            for pid, r in rows.items():
                by_player[pid].append({**r, 'team': team, 'date': g['date'], 'phase': g['phase']})
    for p in players.values():
        rows = by_player.get(p.get('sourcePlayerId'), [])
        gp = len(rows)
        p.update(gp=gp, ppg=sum(r['points'] for r in rows)/gp if gp else None,
                 threePm=sum(r['threeMade'] for r in rows)/gp if gp else None,
                 threePa=sum(r['threeAttempted'] for r in rows)/gp if gp else None,
                 minutesSampleGames=gp, plusMinusSampleGames=gp)
        p['ppgByPhase'] = {}
        for phase in meta['phaseCounts']:
            sample = [r for r in rows if r['phase'] == phase]
            p['ppgByPhase'][phase] = {'gp': len(sample), 'ppg': sum(r['points'] for r in sample)/len(sample) if sample else None}
        p['seasonStatTotals'] = {k: sum(r[k] for r in rows) for k in FIELDS}
        p['provenance']['ppg'] = 'NBA official gamebook final boxes'
    meta['statisticalAuthority'] = official['meta']['authority']
    meta['sources']['ppg'] = {'file': 'official_boxscores.json', 'sha256': hashlib.sha256((BASE/'official_boxscores.json').read_bytes()).hexdigest()}
    meta['sources']['officialBoxscores'] = {'file': 'official_boxscores.json', 'contentHash': official['meta']['contentHash']}


def supplement(data, official):
    games = {gid: g['teams'] for gid, g in official['games'].items()}
    totals = {k: sum(r[k] for g in games.values() for t in g.values() for r in t.values()) for k in FIELDS}
    totals['minutes'] = totals['minutesSeconds']/60
    return {'meta': {'schemaVersion': 2, 'season': '2025-26',
                    'parentEvidenceContentHash': data['meta']['evidenceContentHash'],
                    'officialBoxscoreContentHash': official['meta']['contentHash'],
                    'asOfDate': data['meta']['asOfDate'], 'coverageComplete': True,
                    'games': len(games), 'phaseCounts': data['meta']['phaseCounts'], 'totals': totals,
                    'contentHash': content_hash(games),
                    'verification': 'All 1,322 NBA official gamebook final boxes. PDF values govern participation and all box-score statistics. Minutes retain seconds; season shooting percentages and TS% use summed counts.'},
            'games': games}
