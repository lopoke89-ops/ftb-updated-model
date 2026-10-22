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
ASSETS = ('opening_paths.js', 'opening_paths_data.js', 'play_by_play_manifest.js', 'analyst.js', 'readiness_policy.js', 'readiness_evaluation.js', 'lineups.js', 'lineup_projections.js', 'scouting_history.js', 'matchup.js', 'matchup_ui.js', 'analyst_ui.js', 'parlay.js', 'parlay_transition.js', 'parlay_research_config.js', 'parlay_research.js', 'parlay_ui.js', 'parlay_additional.js', 'parlay_additional_ui.js', 'parlay_data.js',
          'analyst_data.js', 'analyst_evaluation.js', 'ev_probability.js', 'ev_model.js', 'ev_additional.js', 'ev_additional_model.js', 'ev_first_team.js', 'ev_first_team_model.js', 'ev_service.js', 'ev_archive.js', 'ev_grading.js', 'ev_scorecard.js', 'ev_context.js', 'prop_sheet.js', 'ev_ui.js', 'scout-theme.css', 'scout_music.js', 'roundball-rock-8bit.mp3', 'may-brendan-rse.mp3',
          'gym-leader-rse.mp3', 'mt-pyre-peak-rse.mp3', 'surfing-rse.mp3', 'diving-rse.mp3')
PHASES = {'regular-season': 1230, 'playoffs': 85, 'play-in': 6, 'nba-cup-final': 1}
TARGET = 'first-team-score-including-free-throws'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_play_by_play(manifest,analysis):
    require(manifest['schemaVersion']==1,'Unsupported PBP schema')
    require(manifest['parserHash']==digest(ROOT/'scripts/full_game_pbp.py'),'PBP parser/hash mismatch; rebuild summaries')
    require(manifest.get('identityResolverHash')==digest(ROOT/'scripts/pbp_identity.py'),'PBP identity resolver/hash mismatch; rebuild summaries')
    require(manifest.get('textExtractorHash')==digest(ROOT/'scripts/gamebook_text.py'),'PBP text extractor/hash mismatch; rebuild summaries')
    body={k:v for k,v in manifest.items() if k not in ('contentHash','attempts','lastRestoreError')}
    require(hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()==manifest['contentHash'],'PBP summary content hash mismatch')
    require(manifest['parentEvidenceContentHash']==analysis['meta']['evidenceContentHash'],'PBP parent mismatch')
    require(manifest['expected']==len(analysis['games']) and set(manifest['games'])=={g['id'] for g in analysis['games']},'PBP expected-game accounting mismatch')
    for g in analysis['games']:
        r=manifest['games'][g['id']]
        require(r['status'] in ('verified','partial','quarantined','pending'),'Invalid PBP status')
        if r.get('sourceHash'):
            expected=g.get('sourceHash') or next(p['statsSourceHash'] for b in g['teams'].values() for p in b['players'] if p['played'])
            require(r['sourceHash']==expected,'PBP PDF/box source mismatch')
        require(all(isinstance(v,bool) for v in r['components'].values()),'Invalid component acceptance')
        if r['status']=='verified': require(bool(r['components']) and all(r['components'].values()) and r['discrepancies']==0,'Unverified game labeled verified')


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
    research = read(source / 'parlay_research_config.json')
    require(javascript_payload(source / 'parlay_research_config.js', '__FTB_PARLAY_RESEARCH_CONFIG__') == research, 'Research browser configuration differs')
    literal = (source / 'parlay_research_config.js').read_text(encoding='utf-8').split(' = ', 1)[1].strip().removesuffix(';')
    fitted_body = literal.rsplit(',"configurationHash":', 1)[0] + '}'
    require(hashlib.sha256(fitted_body.encode()).hexdigest() == research['configurationHash'], 'Research configuration hash mismatch')
    require(research['fitScriptHash'] == digest(ROOT / 'scripts/fit_parlay_transition.cjs'), 'Research fitting script changed; refit required')
    require(research['defaultEnabled'] is False and research['developmentEnd'] == '2025-12-15', 'Research scope/default changed')
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
    roles = parlay.get('datedRoleEvidence', [])
    role_meta = parlay.get('roleEvidenceMeta', {})
    if roles:
        require(role_meta.get('parentEvidenceContentHash') == a['evidenceContentHash'], 'NBA role parent evidence mismatch')
        require(hashlib.sha256(json.dumps(roles, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest() == role_meta.get('contentHash'), 'NBA role content hash mismatch')
        require(role_meta.get('roleRecords') == len(roles), 'NBA role count mismatch')
        games_by_id = {g['id']: g for g in games}
        grouped_roles = {}
        for r in roles:
            g = games_by_id.get(r['gameId'])
            require(g and r['effectiveGameDate'] == g['date'] and r['gamebookSourceHash'] == g['sourceHash'], 'NBA role fixture/PDF mismatch')
            require(r['position'] in {'PG', 'SG', 'SF', 'PF', 'C'} and r['source'] == 'https://stats.nba.com/js/data/leaders/00_daily_lineups_' + g['date'].replace('-', '') + '.json', 'NBA role source mismatch')
            require(re.fullmatch('[0-9a-f]{64}', r['sourceHash']) and r['nbaPlayerId'].isdigit(), 'Invalid NBA role identity or hash')
            starters = {p['id'] for p in g['teams'][r['team']]['players'] if p['starter'] and p['played']}
            require(r['playerId'] in starters, 'NBA role does not match a PDF starter')
            grouped_roles.setdefault((g['id'], r['team']), []).append(r)
        require(all(len(rows) == 5 and len({r['playerId'] for r in rows}) == 5 and len({r['position'] for r in rows}) == 5 for rows in grouped_roles.values()), 'NBA role five-player join incomplete')
        require(len(grouped_roles) == role_meta['matchedTeamGames'], 'NBA role matched-team count mismatch')
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
            require(g.get('boxScoreSource') == 'NBA official final box' and (g.get('archivedSource') or '').startswith('https://github.com/'), 'Current game lacks archived NBA authority')
            if g.get('fixtureReview'):
                review=g['fixtureReview'];require(review in read(ROOT/'FIXTURE_IDENTITY_REVIEWS.json')['reviews'],'Unrecognized fixture identity review')
                require(review['gamebookSourceHash']==g['sourceHash'] and all(review[k]==g[k] for k in ('home','away','date','phase')) and review['finalFeedTipoff']==g['scheduledTipoff'],'Stale fixture identity review')
                evidence=review['evidence'];require(digest(ROOT/evidence['savedSnapshotFixturePath'])==evidence['savedSnapshotFixtureHash'],'Fixture review saved evidence changed')
                frozen=read(ROOT/evidence['savedSnapshotFixturePath']);require(frozen['id']==evidence['savedSnapshotId'] and any(f['id']==g['id'] and f['scheduledTipoff']==review['originalScheduledTipoff'] for f in frozen['fixtures']),'Fixture review original contract mismatch')
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
    ev = read(source / 'ev_model.json')
    first = read(source / 'ev_first_team_model.json')
    require(first.get('version') == 'ev-first-team-v1.2' and first.get('enabled') is False and first.get('withheldReason'), 'First Team Basket probabilities must remain withheld pending a separately reviewed release')
    require(first.get('featureSnapshotChecks') == {'strictlyEarlierDates':True,'immutable':True,'retainedLineups':424,'unchangedAfterArchiveReplay':True}, 'First Team Basket immutable chronological feature checks missing')
    require(first['engineHash'] == digest(source / 'ev_first_team.js'), 'First Team Basket engine changed; regenerate its separate diagnostics')
    require(first['trainerHash'] == digest(ROOT / 'scripts/train_first_team_ev.cjs'), 'First Team Basket trainer changed; regenerate diagnostics')
    for field, filename in [('protocolHash','FIRST_TEAM_EV_PROTOCOL.json'),('forwardProtocolHash','FIRST_TEAM_EV_FORWARD_PROTOCOL.json'),('rulesProfileHash','FIRST_TEAM_EV_RULES.json')]:
        require(first[field] == digest(ROOT / filename), 'First Team Basket research/rules profile changed: ' + filename)
    require(first['archiveEvidenceHash'] == history['analysis']['meta']['evidenceContentHash'] and first['openingEvidenceHash'] == history['parlay']['meta']['openingContentHash'], 'First Team Basket source evidence mismatch')
    require(json.loads((source / 'ev_first_team_model.js').read_text(encoding='utf-8').removeprefix('window.__FTB_EV_FIRST_TEAM_MODEL__=').strip().removesuffix(';')) == first, 'First Team Basket browser model mismatch')
    require(ev['engineHash'] == digest(source / 'ev_probability.js'), 'EV probability engine changed; regenerate its separate diagnostics')
    require(ev['protocolHash'] == digest(ROOT / 'EV_PROTOCOL.json'), 'EV protocol changed; regenerate its separate diagnostics')
    require(ev['forwardProtocolHash'] == digest(ROOT / 'EV_FORWARD_PROTOCOL.json'), 'EV forward protocol changed; version and regenerate the research model')
    require(ev['rulesProfileHash'] == digest(ROOT / 'EV_RULES_PROFILE.json'), 'EV rules profile changed; version and regenerate the research model')
    require(ev['trainerHash'] == digest(ROOT / 'scripts/train_ev.cjs'), 'EV trainer changed; regenerate its separate diagnostics')
    require(ev['archiveEvidenceHash'] == history['analysis']['meta']['evidenceContentHash'], 'EV archive provenance mismatch')
    require(json.loads((source / 'ev_model.js').read_text(encoding='utf-8').removeprefix('window.__FTB_EV_MODEL__=').strip().removesuffix(';')) == ev, 'EV browser model/configuration mismatch')
    opening_paths=read(source/'opening_paths_data.json')
    require(opening_paths['version']=='opening-paths-v1' and opening_paths['builderHash']==digest(ROOT/'scripts/opening_paths.py'),'Opening paths builder changed; rebuild source paths')
    require(opening_paths['parentEvidenceContentHash']==history['analysis']['meta']['evidenceContentHash'],'Opening paths parent evidence mismatch')
    require(set(opening_paths['games'])=={g['id'] for g in history['analysis']['games']},'Opening paths game coverage mismatch')
    require(hashlib.sha256(json.dumps({k:v for k,v in opening_paths.items() if k!='contentHash'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==opening_paths['contentHash'],'Opening paths content mismatch')
    require(javascript_payload(source/'opening_paths_data.js','__FTB_OPENING_PATHS__')==opening_paths,'Opening paths browser data mismatch')
    additional = read(source / 'ev_additional_model.json')
    require(additional['version']=='ev-assists-rebounds-v1' and set(additional['markets'])=={'assists','rebounds'}, 'Additional count model/version mismatch')
    require(additional['engineHash']==digest(source/'ev_additional.js') and additional['trainerHash']==digest(ROOT/'scripts/train_ev_additional.cjs'), 'Additional count engine/trainer changed; regenerate separate diagnostics')
    for field,filename in [('protocolHash','ASSISTS_REBOUNDS_PROTOCOL.json'),('forwardProtocolHash','ASSISTS_REBOUNDS_FORWARD_PROTOCOL.json'),('rulesProfileHash','ASSISTS_REBOUNDS_RULES.json')]:
        require(additional[field]==digest(ROOT/filename), 'Additional count protocol/rules changed')
    require(additional['archiveEvidenceHash']==history['analysis']['meta']['evidenceContentHash'], 'Additional count archive evidence mismatch')
    require(json.loads((source/'ev_additional_model.js').read_text(encoding='utf-8').removeprefix('window.__FTB_EV_ADDITIONAL_MODEL__=').strip().removesuffix(';'))==additional, 'Additional count browser model mismatch')
    raw=(source/'ev_additional_model.js').read_text(encoding='utf-8').removeprefix('window.__FTB_EV_ADDITIONAL_MODEL__=').strip().removesuffix(';')
    require(hashlib.sha256((raw.rsplit(',"modelHash":',1)[0]+'}').encode()).hexdigest()==additional['modelHash'], 'Additional count model content hash mismatch')
    additional_validation=read(ROOT/'audits/2026-10-21-assists-rebounds/validation.json')
    require(additional_validation['modelHash']==additional['modelHash'] and additional_validation['status']=='passed-experimental-validation', 'Separate assists/rebounds validation unavailable or stale')
    require(additional_validation['engineHash']==additional['engineHash'] and additional_validation['trainerHash']==additional['trainerHash'] and additional_validation['protocolHash']==additional['protocolHash'] and additional_validation['auditorHash']==digest(ROOT/'scripts/audit_ev_additional.cjs'), 'Additional count independent audit changed; rerun validation')
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
    pbp_manifest=read(source/'play_by_play_manifest.json')
    validate_play_by_play(pbp_manifest,history['analysis'])
    require(javascript_payload(source/'play_by_play_manifest.js','__FTB_PLAY_BY_PLAY__')==pbp_manifest,'PBP browser manifest mismatch')
    current_manifest=read(source/'seasons/2026-27/manifest.json')
    pbp_pointer=current_manifest.get('playByPlay',{}).get('contentHash')
    if pbp_pointer:
        require(bool(re.fullmatch('[a-f0-9]{64}',pbp_pointer)),'Invalid PBP manifest pointer')
        current_pbp=read(source/'seasons/2026-27/play_by_play/versions'/(pbp_pointer+'.json'))
        if current_pbp.get('parserHash')==digest(ROOT/'scripts/full_game_pbp.py') and current_pbp.get('identityResolverHash')==digest(ROOT/'scripts/pbp_identity.py') and current_pbp.get('parentEvidenceContentHash')==current['meta']['evidenceContentHash']:
            validate_play_by_play(current_pbp,current)
            current={**current,'playByPlay':current_pbp}
        else:
            current={**current,'playByPlayUnavailable':'Event summary rebuild pending for this parser/box revision; verified boxes remain available'}
    published_at = datetime.now(timezone.utc).isoformat()
    hosting = {'mode': 'github-pages', 'publishedDate': published_date, 'publishedAt': published_at,
               'dataVersion':current['meta']['evidenceContentHash'],
               'parlayCodeHashes': {name: digest(source / name) for name in ('parlay.js', 'scouting_history.js', 'lineups.js', 'lineup_projections.js', 'parlay_transition.js', 'parlay_research.js', 'parlay_research_config.js', 'parlay_ui.js', 'parlay_additional.js', 'parlay_additional_ui.js', 'opening_paths.js', 'analyst_ui.js')},
               'researchProtocolHash':digest(ROOT/'PARLAY_RESEARCH_PROTOCOL.json'),
               'additionalEVModelHash':additional['modelHash'],'additionalEVEngineHash':additional['engineHash'],'additionalEVProtocolHash':additional['protocolHash'],
               'evModelHash':ev['modelHash'],'evEngineHash':ev['engineHash'],'evProtocolHash':ev['protocolHash'],'firstTeamEVModelHash':first['modelHash'],'evServiceVersion':'ev-service-v1','evServiceCodeHash':digest(source / 'ev_service.js')}
    hosting['evContextCodeHash'] = digest(source / 'ev_context.js')
    hosting['propSheetCodeHash'] = digest(source / 'prop_sheet.js')
    current = {**current, 'publication': hosting}
    marker = '<script src="analyst_ui.js"></script>'
    require(html.count(marker) == 1 and '__FTB_HOSTING__' not in html, 'Hosting insertion marker changed')
    html = html.replace(marker, '<script>window.__FTB_HOSTING__ = ' + json.dumps(hosting) + ';</script>\n' + marker)
    html = version_asset_references(html, output)
    for name in ('index.html', 'ftb-scout.html'):
        (output / name).write_text(html, encoding='utf-8', newline='\n')
    for name, payload in [('history.json', history), ('seasons/2026-27.json', current), ('ev-model.json', ev), ('ev-additional-model.json', additional), ('ev-additional-protocol.json',read(ROOT/'ASSISTS_REBOUNDS_PROTOCOL.json')), ('ev-additional-forward-protocol.json',read(ROOT/'ASSISTS_REBOUNDS_FORWARD_PROTOCOL.json')), ('ev-additional-rules.json',read(ROOT/'ASSISTS_REBOUNDS_RULES.json')), ('ev-additional-validation.json',additional_validation), ('ev-first-team-model.json',first), ('first-team-ev-protocol.json',read(ROOT/'FIRST_TEAM_EV_PROTOCOL.json')), ('first-team-ev-forward-protocol.json',read(ROOT/'FIRST_TEAM_EV_FORWARD_PROTOCOL.json')), ('first-team-ev-rules.json',read(ROOT/'FIRST_TEAM_EV_RULES.json')), ('ev-forward-protocol.json',read(ROOT/'EV_FORWARD_PROTOCOL.json')), ('ev-rules-profile.json',read(ROOT/'EV_RULES_PROFILE.json'))]:
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
