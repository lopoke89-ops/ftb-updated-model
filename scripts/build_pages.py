"""Export audited FTB Scout assets to a strict static GitHub Pages artifact."""
import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nba ftb shi'
ASSETS = ('analyst.js', 'readiness_policy.js', 'readiness_evaluation.js', 'lineups.js', 'scouting_history.js', 'analyst_ui.js', 'parlay.js', 'parlay_ui.js', 'parlay_data.js',
          'analyst_data.js', 'analyst_evaluation.js', 'scout-theme.css')
PHASES = {'regular-season': 1230, 'playoffs': 85, 'play-in': 6, 'nba-cup-final': 1}
TARGET = 'first-team-score-including-free-throws'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_asset_references(html, folder):
    # A changed file gets a new URL even when the browser cached the last release.
    for name in ASSETS:
        version = digest(folder / name)[:16]
        for attribute in ('src', 'href'):
            html = html.replace(f'{attribute}="{name}"', f'{attribute}="{name}?v={version}"')
    return html


def require(condition, message):
    if not condition:
        raise ValueError(message)


def javascript_payload(path, variable):
    script = path.read_text(encoding='utf-8')
    prefix = 'window.' + variable + ' = '
    require(script.startswith(prefix) and script.rstrip().endswith(';'), 'Invalid data script: ' + path.name)
    return json.loads(script[len(prefix):].rstrip().removesuffix(';'))


def validate(source):
    canonical = read(source / 'merged_dataset.json')
    analysis = read(source / 'analyst_data.json')
    evaluation = read(source / 'analyst_evaluation.json')
    c, a = canonical['meta'], analysis['meta']
    games = analysis['games']
    require(c['season'] == a['season'] == '2025-26', 'Wrong archived season')
    require(c['scoringDefinition'] == a['scoringDefinition'] == TARGET, 'Scoring definition changed')
    require(c['coverageComplete'] and a['coverageComplete'], 'Incomplete archive')
    require(c['totalGames'] == a['totalGames'] == len(games) == 1322, 'Missing archive games')
    require(len({g['id'] for g in games}) == len(games), 'Duplicate archive games')
    require(dict(Counter(g['phase'] for g in games)) == c['phaseCounts'] == a['phaseCounts'] == PHASES, 'Competition coverage changed')
    require(c['asOfDate'] == a['asOfDate'] == max(g['date'] for g in games) == '2026-06-13', 'Archive end changed')
    require(all(set(g['firstScores']) == {g['home'], g['away']} for g in games), 'Incomplete first scores')
    scores = [score for g in games for score in g['firstScores'].values()]
    require(len(scores) == c['totalEvents'] == 2644, 'First-score total changed')
    require(sum(s['shot'] == 'ft' for s in scores) == c['validation']['freeThrowEvents'] == 249, 'Free-throw total changed')
    require(a['parentDatasetId'] == c['datasetId'], 'Dataset identity mismatch')
    require(a['canonicalWorkbookHash'] == c['sources']['ftb']['sha256'], 'Workbook provenance mismatch')
    content = json.dumps({'games': games, 'datedRoleEvidence': analysis['datedRoleEvidence']}, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    require(hashlib.sha256(content).hexdigest() == a['evidenceContentHash'] == evaluation['evidenceContentHash'], 'Evidence content hash mismatch')
    require(digest(source / 'analyst_data.json') == evaluation['evidenceHash'], 'Evaluation evidence file mismatch')
    require(digest(source / 'analyst.js') == evaluation['modelCodeHash'], 'Evaluated model code mismatch')
    require(javascript_payload(source / 'analyst_data.js', '__FTB_ANALYST_DATA__') == analysis, 'Browser evidence differs from JSON')
    require(javascript_payload(source / 'analyst_evaluation.js', '__FTB_ANALYST_EVALUATION__') == evaluation, 'Browser evaluation differs from JSON')
    parlay = read(source / 'parlay_data.json')
    readiness = read(source / 'readiness_policy.json')
    validation = read(source / 'readiness_evaluation.json')
    require(javascript_payload(source / 'readiness_policy.js', '__FTB_READINESS__') == readiness, 'Browser readiness policy mismatch')
    require(javascript_payload(source / 'readiness_evaluation.js', '__FTB_READINESS_REPORT__') == validation, 'Browser readiness evaluation mismatch')
    require(readiness['status'] == 'retrospective-selected' and readiness['thresholds'] == validation['thresholds'], 'Readiness evaluation not selected')
    require(digest(source / 'readiness_evaluation.json') == readiness['evaluationHash'], 'Readiness report hash mismatch')
    require(digest(ROOT / 'scripts/evaluate_readiness.cjs') == validation['evaluatorHash'], 'Readiness evaluator changed; rerun chronological evaluation')
    require(all(digest(source / name) == expected for name, expected in validation['sourceHashes'].items()), 'Readiness evaluation source changed; rerun chronological evaluation')
    require(parlay['meta']['parentEvidenceContentHash'] == a['evidenceContentHash'], 'Parlay evidence mismatch')
    require(javascript_payload(source / 'parlay_data.js', '__FTB_PARLAY_DATA__') == parlay, 'Browser shooting evidence differs from JSON')
    require(hashlib.sha256(json.dumps(parlay['games'], separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest() == parlay['meta']['contentHash'], 'Parlay shooting content hash mismatch')
    require(set(parlay['games']) == {g['id'] for g in games}, 'Parlay game coverage mismatch')
    opening = parlay.get('openingEvidence')
    require(bool(opening), 'Official opening evidence is required')
    require(opening['meta']['parentEvidenceContentHash'] == a['evidenceContentHash'], 'Opening evidence parent mismatch')
    require(set(opening['games']) == {g['id'] for g in games} and opening['meta']['games'] == len(games), 'Opening fixture coverage mismatch')
    opening_hash = hashlib.sha256(json.dumps(opening['games'], separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    require(opening_hash == opening['meta']['contentHash'] == parlay['meta']['openingContentHash'], 'Opening content hash mismatch')
    for g in games:
        op = opening['games'][g['id']]
        require(op['source'] == g['source'] and op['sourceHash'] == g['sourceHash'], 'Opening PDF provenance mismatch')
        for team in (g['home'], g['away']):
            for key in ('firstScores','firstFieldGoals'):
                event = op[key][team]
                require(event['period'] == 1 and event['points'] > 0 and event['page'] > 1, 'Invalid official opening score')
                require(any(p['played'] and p['id'] == event['id'] for p in g['teams'][team]['players']), 'Opening scorer not in official appearance ledger')
                require(all(g[key][team][field] == event[field] for field in ('id','clock','period','sequence','points','shot')), 'Shared scorer differs from official opening ledger')
            field = op['firstFieldGoals'][team]
            require(not field['isFreeThrow'] and field['points'] in (2,3), 'First field goal cannot be a free throw')
            for ft in field['andOneFreeThrows']:
                require(ft['clock'] == field['clock'] and ft['athleteIds'] == [field['id']] and ft['linkedBasketSequence'] == field['sequence'], 'Invalid and-one basket link')
                foul = next((e for e in op['orderedEvents'] if e['sequence'] == ft['linkedFoulSequence']), None)
                require(foul and foul['team'] != team and 'S.FOUL' in foul['text'], 'And-one shooting foul not supported')
                require('1 of 1' in ft['text'] and not re.search(r'technical|flagrant|clear path|take foul|transition',ft['text'],re.I), 'Special free throw misclassified as and-one')
        for team, box in g['teams'].items():
            rows = parlay['games'][g['id']][team]
            require(set(rows) == {p['id'] for p in box['players'] if p['played']}, 'Parlay appearance mismatch')
            require(sum(r['points'] for r in rows.values()) == box['points'], 'Parlay team score mismatch')
            for p in box['players']:
                if not p['played']:
                    continue
                r = rows[p['id']]
                require(all(r[k] == p[k] for k in ('points','fga','fta','minutes','threeMade','threeAttempted')), 'Parlay frozen statistic mismatch')
                require(0 <= r['threeMade'] <= r['fgm'] <= r['fga'] and r['threeMade'] <= r['threeAttempted'] <= r['fga'] and 0 <= r['ftm'] <= r['fta'], 'Parlay invalid shooting totals')
                require(2*r['fgm']+r['threeMade']+r['ftm'] == r['points'], 'Parlay points mismatch')
    html = (source / 'ftb-scout.html').read_text(encoding='utf-8')
    embedded = html.split('window.__FTB_MERGED__ = ', 1)[1]
    require(json.JSONDecoder().raw_decode(embedded)[0] == canonical, 'Embedded canonical dataset differs from JSON')
    folder = source / 'seasons' / '2026-27'
    health = read(folder / 'manifest.json')
    version = health['activeVersion']
    require(re.fullmatch(r'[0-9a-f]{64}\.json', version), 'Unsafe season version path')
    current = read(folder / 'versions' / version)
    require(current['meta']['season'] == health['season'] == '2026-27', 'Current season mismatch')
    require(current['meta']['parentDatasetId'] == 'nba-2026-27-canonical', 'Current season identity mismatch')
    require(current['meta']['scoringDefinition'] == TARGET, 'Current scoring definition mismatch')
    require(len(current['games']) == current['meta']['totalGames'] == health['totalGames'], 'Current season count mismatch')
    require(len({g['id'] for g in current['games']}) == len(current['games']), 'Duplicate current games')
    require(all(g['phase'] in PHASES for g in current['games']), 'Preseason cannot enter scoring history')
    current_hash = hashlib.sha256(json.dumps(current['games'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(current_hash == health['evidenceContentHash'] == current['meta']['evidenceContentHash'] == version[:-5], 'Current season hash mismatch')
    require(current.get('datedRoleEvidence', []) == [role for g in current['games'] for role in g.get('roleEvidence', [])], 'Current dated roles differ from authenticated game records')
    if current['games']:
        p = current.get('parlay', {})
        require(p.get('meta', {}).get('parentEvidenceContentHash') == current_hash, 'Current shooting evidence mismatch')
        require(digest_value(p['games']) == p['meta']['contentHash'], 'Current shooting hash mismatch')
        opening = p['openingEvidence']
        require(opening['meta']['parentEvidenceContentHash'] == current_hash and digest_value(opening['games']) == opening['meta']['contentHash'], 'Current opening hash mismatch')
        require(set(p['games']) == set(opening['games']) == {g['id'] for g in current['games']}, 'Current supplemental coverage mismatch')
        for g in current['games']:
            require(g.get('boxScoreSource') == 'NBA official final box' and g.get('archivedSource', '').startswith('https://github.com/'), 'Current game lacks archived NBA authority')
            require(opening['games'][g['id']]['sourceHash'] == g['sourceHash'], 'Current opening PDF mismatch')
            for team, box in g['teams'].items():
                played = [r for r in box['players'] if r['played']]
                require(len({r['id'] for r in played}) == len(played) and sum(r['starter'] for r in played) == 5, 'Invalid current appearances/starters')
                require(sum(r['points'] for r in played) == box['points'], 'Current NBA team score mismatch')
                require(set(p['games'][g['id']][team]) == {r['id'] for r in played}, 'Current shooting appearance mismatch')
                for r in played:
                    require(all(r.get(k) is not None for k in ('points','fgm','fga','threeMade','threeAttempted','ftm','fta','minutesSeconds','rebounds','assists','steals','blocks','turnovers','fouls','offensiveRebounds','defensiveRebounds','plusMinus')), 'Current full stat line incomplete')
                    require(r['statsSourceHash'] == g['sourceHash'] and r == p['games'][g['id']][team][r['id']], 'Current row provenance mismatch')
                    require(0 <= r['threeMade'] <= r['fgm'] <= r['fga'] and r['threeMade'] <= r['threeAttempted'] <= r['fga'] and 0 <= r['ftm'] <= r['fta'], 'Current shooting inequality')
                    require(2*r['fgm']+r['threeMade']+r['ftm'] == r['points'], 'Current points equation failed')
                for key in ('firstScores','firstFieldGoals'):
                    event = opening['games'][g['id']][key][team]
                    require(g[key][team] == event and any(r['id'] == event['id'] for r in played), 'Current NBA opening scorer mismatch')
    attempt = folder / 'last_attempt.json'
    if attempt.exists():
        failed = read(attempt)
        if failed['checkedAt'] > health['checkedAt']:
            health = {**health, 'lastFailedAttempt': failed}
    return {'canonical': canonical, 'analysis': analysis, 'evaluation': evaluation, 'parlay': parlay}, {**current, 'health': health}, html


def digest_value(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def build(source=SOURCE, output=ROOT / '_site', published_date=None):
    config = read(ROOT / 'site-config.json')
    published_date = published_date or datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
    date.fromisoformat(published_date)
    history, current, html = validate(source)
    require(not output.exists() or not any(output.iterdir()), 'Output must be a new or empty directory')
    output.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        shutil.copyfile(source / name, output / name)
    vendor_files = ['vendor/manifest.json', 'vendor/fonts/manifest.json', 'vendor/fonts/fonts.css']
    for folder in ('vendor', 'vendor/fonts'):
        for item in read(source / folder / 'manifest.json'):
            name = item['file']
            require(Path(name).name == name, 'Unsafe vendor filename')
            relative = folder + '/' + name
            require(digest(source / relative) == item['sha256'], 'Vendor hash mismatch: ' + relative)
            vendor_files.append(relative)
    for relative in vendor_files:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    published_at = datetime.now(timezone.utc).isoformat()
    hosting = {'mode': 'github-pages', 'publishedDate': published_date, 'publishedAt': published_at}
    marker = '<script src="analyst_ui.js"></script>'
    require(html.count(marker) == 1 and '__FTB_HOSTING__' not in html, 'Hosting insertion marker changed')
    html = html.replace(marker, '<script>window.__FTB_HOSTING__ = ' + json.dumps(hosting) + ';</script>\n' + marker)
    html = version_asset_references(html, output)
    for name in ('index.html', 'ftb-scout.html'):
        (output / name).write_text(html, encoding='utf-8', newline='\n')
    for name, payload in [('history.json', history), ('seasons/2026-27.json', current)]:
        target = output / 'data' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False), encoding='utf-8')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    manifest = {'publishedDate': published_date, 'publishedAt': published_at, 'collection': current.get('health', {}).get('collection'), 'archiveThrough': history['analysis']['meta']['asOfDate'],
                'archiveGames': 1322, 'firstScores': 2644, 'firstFreeThrows': 249,
                'phaseCounts': PHASES, 'currentSeasonGames': len(current['games']),
                'canonicalWorkbookHash': history['analysis']['meta']['canonicalWorkbookHash'],
                'modelCodeHash': history['evaluation']['modelCodeHash'],
                'openingContentHash': history['parlay']['meta']['openingContentHash'],
                'files': {p.relative_to(output).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size}
                          for p in sorted(output.rglob('*')) if p.is_file()}}
    (output / 'deployment-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=ROOT / '_site')
    parser.add_argument('--published-date')
    args = parser.parse_args()
    result = build(args.source, args.output, args.published_date)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, indent=2))
    print('Published assets:', len(result['files']) + 1)
