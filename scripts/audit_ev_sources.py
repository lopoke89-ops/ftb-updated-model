"""Re-extract downloaded final boxes, read-only, and reconcile both app ledgers."""
import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nba ftb shi'
FIELDS = dict(points='pts', fgm='fgm', fga='fga', threeMade='three_pm', threeAttempted='three_pa', ftm='ftm', fta='fta',
              rebounds='reb', assists='ast', steals='stl', blocks='blk', turnovers='tov', fouls='pf',
              offensiveRebounds='oreb', defensiveRebounds='dreb', plusMinus='plus_minus', minutesSeconds='minutes_seconds')
_parser = _identities = None

def initialize(parser_path, identities):
    global _parser, _identities
    spec = importlib.util.spec_from_file_location('gamebook_source_parser', parser_path)
    _parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_parser)
    _identities = identities

def extract(task):
    from pypdf import PdfReader
    game, doc, library = task
    try:
        path = Path(library) / doc['pdf_path']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != doc['sha256']:
            raise ValueError('Stored NBA PDF hash changed')
        text = PdfReader(path).pages[0].extract_text(extraction_mode='layout')
        if 'FINAL BOX' not in text:
            raise ValueError('Missing final-box heading')
        expected = datetime.fromisoformat(game['date']).strftime('%B %d, %Y').replace(' 0', ' ')
        if expected not in text:
            raise ValueError('Printed report date mismatch')
        rows, issues = _parser.parse_final_box(text, game, _identities)
        return {'gameId': game['id'], 'source': doc['source_url'], 'pdf': doc['pdf_path'], 'sha256': digest,
                'textSha256': hashlib.sha256(text.encode()).hexdigest(), 'rows': rows, 'issues': issues}
    except Exception as error:
        return {'gameId': game['id'], 'issues': [str(error)], 'rows': []}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    start = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=True)
    data = json.loads((SOURCE / 'analyst_data.json').read_text(encoding='utf-8', newline='\n'))
    supplement = json.loads((SOURCE / 'parlay_data.json').read_text(encoding='utf-8', newline='\n'))
    official = json.loads((SOURCE / 'official_boxscores.json').read_text(encoding='utf-8', newline='\n'))
    manifest = json.loads((args.library / 'manifest.json').read_text(encoding='utf-8', newline='\n'))
    docs = {r['espn_game_id']: r for r in manifest['documents']}
    identities = defaultdict(set)
    for game in data['games']:
        for box in game['teams'].values():
            for p in box['players']:
                import unicodedata, re
                name = re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', p['name']).encode('ascii', 'ignore').decode().lower())
                identities[name].add(str(p['id']))
    tasks = [(g, docs[g['id']], str(args.library)) for g in data['games']]
    connection = sqlite3.connect('file:' + (args.library / 'gamebooks.sqlite').as_posix() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    db_rows = {(r['espn_game_id'], r['team'], r['espn_player_id']): dict(r) for r in connection.execute('SELECT * FROM player_game_stats WHERE played=1')}
    integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
    assert integrity == 'ok'
    connection.close()
    games = {g['id']: g for g in data['games']}
    comparisons, played, zero_minutes, differences, document_results, seen = 0, 0, 0, [], [], set()
    initialize(str(args.library.parent / 'collect_gamebooks.py'), dict(identities))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, result in enumerate(pool.map(extract, tasks, chunksize=4), 1):
            gid = result['gameId']
            if result['issues']:
                differences.append({'gameId': gid, 'extractionIssues': result['issues']})
            game = games[gid]
            rows = [r for r in result['rows'] if r['played']]
            for row in rows:
                key = gid, row['team'], str(row['espn_player_id'])
                seen.add(key)
                played += 1
                zero_minutes += row['minutes_seconds'] == 0
                candidates = [p for p in game['teams'][row['team']]['players'] if str(p['id']) == key[2] and p['played']]
                if len(candidates) != 1 or key not in db_rows:
                    differences.append({'key': key, 'reason': 'Missing/ambiguous source-to-app/database appearance'})
                    continue
                app = candidates[0]
                targets = {'app': app, 'parlay': supplement['games'][gid][row['team']][key[2]],
                           'official': official['games'][gid]['teams'][row['team']][key[2]]}
                for field, raw in FIELDS.items():
                    for target, record in targets.items():
                        comparisons += 1
                        if record.get(field) != row[raw]:
                            differences.append({'key': key, 'target': target, 'field': field, 'pdf': row[raw], 'stored': record.get(field)})
                    comparisons += 1
                    if db_rows[key][raw] != row[raw]:
                        differences.append({'key': key, 'target': 'database', 'field': raw, 'pdf': row[raw], 'stored': db_rows[key][raw]})
                if app['minutes'] != row['minutes_seconds']/60 or bool(app['starter']) != bool(row['starter']):
                    differences.append({'key': key, 'reason': 'Minutes or starter mismatch'})
            document_results.append({k: v for k, v in result.items() if k != 'rows'} | {'playedRows': len(rows)})
            if index % 100 == 0 or index == len(tasks):
                print(json.dumps({'pdfs': index, 'expected': len(tasks), 'playedRows': played, 'differences': len(differences)}), flush=True)
    if seen != set(db_rows):
        differences.append({'reason': 'PDF and database appearance sets differ', 'missing': sorted(set(db_rows)-seen), 'extra': sorted(seen-set(db_rows))})
    app_keys = {(g['id'], team, str(p['id'])) for g in data['games'] for team, b in g['teams'].items() for p in b['players'] if p['played']}
    if app_keys != seen:
        differences.append({'reason': 'PDF and active app appearance sets differ', 'missing': sorted(seen-app_keys), 'extra': sorted(app_keys-seen)})
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'status': 'passed' if not differences else 'failed',
              'method': 'Fresh first-page extraction from every original PDF, with the existing documented name crosswalk/parser; no library or application mutation.',
              'games': len(tasks), 'phaseCounts': dict(Counter(g['phase'] for g in data['games'])), 'playedRows': played,
              'zeroPrintedMinuteAppearances': zero_minutes, 'statComparisons': comparisons, 'databaseIntegrity': integrity,
              'elapsedSeconds': round(time.monotonic()-start, 2), 'differences': differences, 'documents': document_results}
    (args.output / 'source-reconciliation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'documents'}), flush=True)
    return bool(differences)

if __name__ == '__main__':
    raise SystemExit(main())
