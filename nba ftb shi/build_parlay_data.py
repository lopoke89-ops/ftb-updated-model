"""Build Parlay statistics from authoritative NBA gamebooks when available."""
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIELDS = {'fgm': 'FGM', 'fga': 'FGA', 'threeMade': 'FG3M', 'threeAttempted': 'FG3A',
          'ftm': 'FTM', 'fta': 'FTA', 'points': 'PTS', 'minutes': 'MIN'}


def build(base=BASE, cache=None):
    base = Path(base)
    cache = Path(cache or base.parent / 'season_merge_2026-10-04/source_cache')
    evidence = json.loads((base / 'analyst_data.json').read_text(encoding='utf-8'))
    from official_stats import load,supplement
    official=load(base)
    if official is not None:
        if evidence['meta'].get('officialBoxscoreContentHash') != official['meta']['contentHash']:
            raise ValueError('Analysis must be rebuilt from this official ledger first')
        result=supplement(evidence,official)
        text=json.dumps(result,separators=(',', ':'),ensure_ascii=False,allow_nan=False)
        (base/'parlay_data.json').write_text(text,encoding='utf-8')
        (base/'parlay_data.js').write_text('window.__FTB_PARLAY_DATA__ = '+text+';\n',encoding='utf-8')
        print(json.dumps(result['meta'],indent=2))
        return result
    games, phases, totals = {}, Counter(), Counter()
    for game in evidence['games']:
        file = cache / ('summary_' + game['id'] + '.json')
        raw_bytes = file.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != game['sourceHash']:
            raise ValueError('Source capture changed: ' + game['id'])
        capture = json.loads(raw_bytes)
        if capture['fixture']['eventId'] != game['id'] or capture['fixture']['date'] != game['date']:
            raise ValueError('Fixture mismatch: ' + game['id'])
        boxes = {}
        for team, box in game['teams'].items():
            source = capture['teams'][team]
            source_players = {p['athleteId']: p for p in source['players']}
            if len(source_players) != len(source['players']):
                raise ValueError('Duplicate source player')
            rows = {}
            for player in box['players']:
                p = source_players[player['id']]
                if p['played'] != player['played'] or p['starter'] != player['starter']:
                    raise ValueError('Appearance mismatch')
                if not p['played']:
                    continue
                row = {name: p['stats'][stat] for name, stat in FIELDS.items()}
                if any(row[k] is None or row[k] < 0 for k in FIELDS if k != 'minutes'):
                    raise ValueError('Incomplete shooting evidence')
                if not (row['threeMade'] <= row['fgm'] <= row['fga'] and
                        row['threeMade'] <= row['threeAttempted'] <= row['fga'] and row['ftm'] <= row['fta']):
                    raise ValueError('Invalid made/attempted totals')
                if 2 * row['fgm'] + row['threeMade'] + row['ftm'] != row['points']:
                    raise ValueError('Points do not reconcile to shooting')
                for key in ('points', 'fga', 'fta', 'threeMade', 'threeAttempted', 'minutes'):
                    if row[key] != player[key]:
                        raise ValueError('Analysis differs from capture: ' + key)
                rows[player['id']] = row
                for name, value in row.items():
                    if value is not None:
                        totals[name] += value
            if sum(p['points'] for p in rows.values()) != source['points'] or source['points'] != box['points']:
                raise ValueError('Team score mismatch')
            boxes[team] = rows
        games[game['id']] = boxes
        phases[game['phase']] += 1
    content = json.dumps(games, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    result = {'meta': {'schemaVersion': 1, 'season': evidence['meta']['season'],
                      'parentEvidenceContentHash': evidence['meta']['evidenceContentHash'],
                      'asOfDate': evidence['meta']['asOfDate'], 'coverageComplete': evidence['meta']['coverageComplete'],
                      'games': len(games), 'phaseCounts': dict(phases), 'totals': dict(totals),
                      'contentHash': hashlib.sha256(content.encode()).hexdigest(),
                      'verification': 'Every played-player row reconciled to its hash-matched saved ESPN box score; shooting reconciles to player and team points. No independent live season-total reconciliation claimed.'},
              'games': games}
    text = json.dumps(result, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    (base / 'parlay_data.json').write_text(text, encoding='utf-8')
    (base / 'parlay_data.js').write_text('window.__FTB_PARLAY_DATA__ = ' + text + ';\n', encoding='utf-8')
    print(json.dumps(result['meta'], indent=2))
    return result


if __name__ == '__main__':
    build()
