"""Export audited FTB Scout assets to a strict static GitHub Pages artifact."""
import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nba ftb shi'
ASSETS = ('analyst.js', 'scouting_history.js', 'analyst_ui.js',
          'analyst_data.js', 'analyst_evaluation.js', 'scout-theme.css')
PHASES = {'regular-season': 1230, 'playoffs': 85, 'play-in': 6, 'nba-cup-final': 1}
TARGET = 'first-team-score-including-free-throws'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    attempt = folder / 'last_attempt.json'
    if attempt.exists():
        failed = read(attempt)
        if failed['checkedAt'] > health['checkedAt']:
            health = {**health, 'lastFailedAttempt': failed}
    return {'canonical': canonical, 'analysis': analysis, 'evaluation': evaluation}, {**current, 'health': health}, html


def build(source=SOURCE, output=ROOT / '_site', published_date=None):
    config = read(ROOT / 'site-config.json')
    published_date = published_date or config['publishedDate']
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
    hosting = {'mode': 'github-pages', 'publishedDate': published_date}
    marker = '<script src="analyst_ui.js"></script>'
    require(html.count(marker) == 1 and '__FTB_HOSTING__' not in html, 'Hosting insertion marker changed')
    html = html.replace(marker, '<script>window.__FTB_HOSTING__ = ' + json.dumps(hosting) + ';</script>\n' + marker)
    for name in ('index.html', 'ftb-scout.html'):
        (output / name).write_text(html, encoding='utf-8', newline='\n')
    for name, payload in [('history.json', history), ('seasons/2026-27.json', current)]:
        target = output / 'data' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False, allow_nan=False), encoding='utf-8')
    (output / '.nojekyll').write_text('', encoding='utf-8')
    manifest = {'publishedDate': published_date, 'archiveThrough': history['analysis']['meta']['asOfDate'],
                'archiveGames': 1322, 'firstScores': 2644, 'firstFreeThrows': 249,
                'phaseCounts': PHASES, 'currentSeasonGames': len(current['games']),
                'canonicalWorkbookHash': history['analysis']['meta']['canonicalWorkbookHash'],
                'modelCodeHash': history['evaluation']['modelCodeHash'],
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
