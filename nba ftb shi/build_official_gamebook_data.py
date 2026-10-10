"""Promote verified downloaded NBA gamebooks into the app's active stats ledger."""
import argparse
import hashlib
import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from official_stats import apply_analysis, content_hash, FIELDS

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
FIELD_MAP = dict(points='pts', fgm='fgm', fga='fga', threeMade='three_pm', threeAttempted='three_pa',
                 ftm='ftm', fta='fta', rebounds='reb', assists='ast', steals='stl', blocks='blk',
                 turnovers='tov', fouls='pf', offensiveRebounds='oreb', defensiveRebounds='dreb',
                 plusMinus='plus_minus', minutesSeconds='minutes_seconds')


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, default=ROOT/'nba_gamebook_library/2025-26')
    parser.add_argument('--output', type=Path, default=ROOT/'official_correction_2026-10-10')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    backup = args.output/'before'
    backup.mkdir(exist_ok=True)
    for name in ('analyst_data.json','analyst_data.js','parlay_data.json','parlay_data.js',
                 'merged_dataset.json','ftb_data_output.json','validation_report.json',
                 'ftb-scout.html','analyst_evaluation.json','analyst_evaluation.js'):
        if not (backup/name).exists():
            shutil.copy2(BASE/name, backup/name)
    previous = read(backup/'analyst_data.json')
    db = sqlite3.connect(f'file:{args.library.as_posix()}/gamebooks.sqlite?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    docs = {r['espn_game_id']: dict(r) for r in db.execute('SELECT * FROM documents')}
    games = {}
    changes = []
    for g in previous['games']:
        doc = docs[g['id']]
        if doc['verification_status'] != 'verified':
            raise ValueError('Unverified NBA final box: '+g['id'])
        if hashlib.sha256((args.library/doc['pdf_path']).read_bytes()).hexdigest() != doc['sha256']:
            raise ValueError('NBA PDF hash changed: '+g['id'])
        teams = {g['home']: {}, g['away']: {}}
        nonappearances = {t: {} for t in teams}
        for r in db.execute('SELECT * FROM player_game_stats WHERE espn_game_id=?', (g['id'],)):
            pid = r['espn_player_id']
            if not r['played']:
                if pid:
                    nonappearances[r['team']][pid] = r['status']
                continue
            if not pid or pid in teams[r['team']]:
                raise ValueError('Missing or duplicate played identity')
            row = {k:r[v] for k,v in FIELD_MAP.items()}
            if any(row[k] is None for k in FIELDS):
                raise ValueError('Incomplete official played stat line')
            row.update(minutes=row['minutesSeconds']/60, starter=bool(r['starter']),
                       nbaName=r['nba_name'], officialPosition=r['position'], jersey=r['jersey'])
            teams[r['team']][pid] = row
        games[g['id']] = dict(date=g['date'], home=g['home'], away=g['away'], phase=g['phase'],
                              source=doc['source_url'], sha256=doc['sha256'], capturedAt=doc['captured_at'],
                              teams=teams, nonappearances=nonappearances)
        for team, box in g['teams'].items():
            old = {p['id']:p for p in box['players'] if p['played']}
            actual = teams[team]
            for pid in old.keys()-actual.keys():
                changes.append(dict(gameId=g['id'],team=team,playerId=pid,name=old[pid]['name'],action='remove-nonappearance',source=doc['source_url']))
            for pid in actual.keys()-old.keys():
                changes.append(dict(gameId=g['id'],team=team,playerId=pid,name=actual[pid]['nbaName'],action='add-appearance',source=doc['source_url']))
            for pid in old.keys()&actual.keys():
                fields = {k:dict(before=old[pid][k],after=actual[pid][k]) for k in FIELDS+('minutes',) if k in old[pid] and old[pid][k] != actual[pid][k]}
                if fields:
                    changes.append(dict(gameId=g['id'],team=team,playerId=pid,name=old[pid]['name'],action='replace-stat-fields',fields=fields,source=doc['source_url']))
    official = {'meta': {'season':'2025-26', 'schemaVersion':1,
                         'authority':'Downloaded NBA official gamebook PDFs are the absolute statistical source of truth, per user instruction.',
                         'builtAt':datetime.now(timezone.utc).isoformat(), 'games':len(games),
                         'contentHash':content_hash(games)}, 'games':games}
    write(BASE/'official_boxscores.json', official)
    data = apply_analysis(read(BASE/'analyst_data.json'), official)
    write(BASE/'analyst_data.json', data)
    (BASE/'analyst_data.js').write_text('window.__FTB_ANALYST_DATA__ = '+json.dumps(data,separators=(',', ':'),ensure_ascii=False,allow_nan=False)+';\n', encoding='utf-8')
    write(args.output/'applied_changes.json', {'authority':official['meta']['authority'], 'beforeEvidenceHash':previous['meta']['evidenceContentHash'],
                                             'afterEvidenceHash':data['meta']['evidenceContentHash'], 'actions':changes,
                                             'counts':dict(Counter(c['action'] for c in changes))})
    print(json.dumps({'games':len(games),'playedRows':sum(len(t) for g in games.values() for t in g['teams'].values()),
                      'changes':dict(Counter(c['action'] for c in changes)), 'evidenceContentHash':data['meta']['evidenceContentHash']}))


if __name__ == '__main__':
    main()
