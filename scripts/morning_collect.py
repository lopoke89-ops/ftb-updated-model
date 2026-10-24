"""Collect yesterday's official NBA finals, retain pending games, publish coherent evidence."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from archive_store import ROOT, ReleaseArchive, read, save, overlay
import official_gamebooks as boxes
import pbp_collect
import pbp_identity
import opening_paths

SOURCE = ROOT / 'nba ftb shi'
SPEC = importlib.util.spec_from_file_location('nba_opening_parser', SOURCE / 'build_opening_gamebook_data.py')
opening = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(opening)
SEASON = '2026-27'
TEAMS = set(boxes.TEAM_NAMES)
TARGET = 'first-team-score-including-free-throws'
FIELDS = dict(points='pts', fgm='fgm', fga='fga', threeMade='three_pm', threeAttempted='three_pa',
              ftm='ftm', fta='fta', rebounds='reb', assists='ast', steals='stl', blocks='blk',
              turnovers='tov', fouls='pf', offensiveRebounds='oreb', defensiveRebounds='dreb',
              plusMinus='plus_minus', minutesSeconds='minutes_seconds')


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value, sorted_keys=False):
    return hashlib.sha256(json.dumps(value, sort_keys=sorted_keys, separators=(',', ':'), ensure_ascii=sorted_keys,
                                     allow_nan=False).encode()).hexdigest()


def fetch_json(url):
    with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}), timeout=30) as response:
        return json.load(response)


def normalize(team):
    return {'GS':'GSW','NY':'NYK','SA':'SAS','NO':'NOP','WSH':'WAS','UTAH':'UTA','PHO':'PHX'}.get(team, team)


def fixture(event, season=SEASON):
    if event.get('season', {}).get('year') != int(season[:4]) + 1:
        return None
    competition = event['competitions'][0]
    sides = {c['homeAway']: c for c in competition['competitors']}
    home, away = (normalize(sides[k]['team']['abbreviation']) for k in ('home','away'))
    notes = ' '.join(n.get('headline','') for n in competition.get('notes',[])).lower()
    kind = event['season']['type']
    phase = 'nba-cup-final' if 'nba cup championship' in notes else 'play-in' if 'play-in' in notes else {1:'preseason',2:'regular-season',3:'playoffs',5:'play-in'}.get(kind)
    # Preseason exhibitions against one non-NBA club (Portland v London Lions) are listed as excluded
    # preseason fixtures; an unknown team in any other phase still fails the schedule check.
    outside = {home,away} - TEAMS
    if home == away or outside and (phase != 'preseason' or len(outside) > 1):
        raise ValueError('Unknown or duplicate fixture teams')
    if not phase:
        raise ValueError('Unknown competition phase')
    status = event.get('status', competition.get('status',{})).get('type',{})
    detail = ' '.join(str(status.get(k,'')) for k in ('name','description','detail','shortDetail')).lower()
    canceled = 'cancel' in detail or 'postpon' in detail
    tipoff = event['date']
    day = datetime.fromisoformat(tipoff.replace('Z','+00:00')).astimezone(ZoneInfo('America/Chicago')).date().isoformat()
    return dict(id=str(event['id']), date=day, home=home, away=away, phase=phase, season=season,
                scheduledTipoff=tipoff, completed=bool(status.get('completed')) and not canceled,
                canceledOrPostponed=canceled, status=detail,
                expectedPoints={normalize(v['team']['abbreviation']):int(v.get('score',0)) for v in sides.values()},
                **({'nonNbaOpponent':outside.pop()} if outside else {}))


def identity_game(f, summary):
    header = summary.get('header',{})
    competition = header.get('competitions',[{}])[0]
    sides = {p['homeAway']:normalize(p['team']['abbreviation']) for p in competition.get('competitors',[])}
    if str(header.get('id')) != f['id'] or sides != {'home':f['home'],'away':f['away']}:
        raise ValueError('Summary identity does not match fixture')
    teams = {}
    for box in summary.get('boxscore',{}).get('players',[]):
        team = normalize(box['team']['abbreviation'])
        players = {}
        for group in box.get('statistics',[]):
            for row in group.get('athletes',[]):
                athlete = row.get('athlete',{})
                pid = str(athlete.get('id',''))
                if not pid or not athlete.get('displayName'):
                    raise ValueError('Summary player identity missing')
                players[pid] = dict(id=pid, name=athlete['displayName'], jersey=str(athlete.get('jersey') or ''),
                                    rawPosition=athlete.get('position',{}).get('abbreviation',''))
        teams[team] = dict(players=list(players.values()), points=f['expectedPoints'][team])
    if set(teams) != {f['home'],f['away']}:
        raise ValueError('Both same-game identity rosters are required')
    return {**f, 'teams':teams}


def official_game(g, record, events):
    if record['verification_status'] != 'verified':
        raise ValueError('NBA final box has unresolved verification issues')
    teams = {}
    for team in (g['home'],g['away']):
        identities = {p['id']:p for p in g['teams'][team]['players']}
        players = []
        for row in record['player_rows']:
            if row['team'] != team or not row['espn_player_id']:
                continue
            pid = str(row['espn_player_id'])
            stats = {k:row[v] for k,v in FIELDS.items()}
            players.append({**stats, 'id':pid, 'name':row['nba_name'],
                            'rawPosition':identities.get(pid,{}).get('rawPosition') or row['position'] or '',
                            'officialPosition':row['position'], 'starter':row['starter'], 'played':row['played'],
                            'status':row['status'], 'minutes':row['minutes_seconds']/60 if row['played'] else None,
                            'statsSource':record['source_url'], 'statsSourceHash':record['sha256']})
        teams[team] = dict(players=players, starters=[p['id'] for p in players if p['starter']],
                           points=record['team_totals'][team]['pts'])
    known = lambda entries: {t:e for t,e in entries.items() if len(e['athleteIds'])==1 and not e.get('identityUnresolved')}
    scorers = {}
    for key in ('firstScores','firstFieldGoals'):
        scorers[key] = {}
        for team,e in events[key].items():
            player = next(p for p in teams[team]['players'] if p['id']==e['id'] and p['played'])
            scorers[key][team] = {**e,'position':player['rawPosition'] if player['rawPosition'] in ('PG','SG','SF','PF','C') else 'unknown'}
    result = {k:g[k] for k in ('id','date','home','away','phase','scheduledTipoff')}
    result.update(teams=teams, **scorers, source=record['source_url'], sourceHash=record['sha256'],
                  archivedSource=record.get('archiveUrl'), capturedAt=record['captured_at'],
                  boxScoreSource='NBA official final box', lineupSource='postgame NBA box; not a pregame announcement',
                  availabilityHistory='unavailable', opening={
                      'eventId':g['id'],'firstAttempts':known(events['firstAttempts']),
                      'firstFieldGoalAttempts':known(events['firstFieldGoalAttempts']),
                      'orderedEvents':events['orderedEvents'],'source':'NBA official first-quarter play-by-play',
                      'sourceUrl':record['source_url'],'sourceHash':record['sha256']})
    return apply_fixture_review(result)


def apply_fixture_review(game):
    """Explicit, source-bound identity reviews; never overwrite the observed feed time."""
    reviews_path=ROOT/'FIXTURE_IDENTITY_REVIEWS.json'
    result={k:v for k,v in game.items() if k!='fixtureReview'}
    if reviews_path.exists():
        for review in read(reviews_path).get('reviews',[]):
            if review['fixtureId']==game['id'] and review['gamebookSourceHash']==game.get('sourceHash') and all(review[k]==game[k] for k in ('date','home','away','phase')) and review['finalFeedTipoff']==game['scheduledTipoff']:
                result['fixtureReview']=review
    return result


def dated_lineup_roles(game, payload, url, captured_at):
    """Postgame role observations, never evidence of a pregame announcement."""
    matches = [g for g in payload.get('games', []) if g.get('homeTeam', {}).get('teamAbbreviation') == game['home']
               and g.get('awayTeam', {}).get('teamAbbreviation') == game['away'] and g.get('gameStatus') == 3]
    if len(matches) != 1:
        return []
    roles = []
    for side, team in (('homeTeam', game['home']), ('awayTeam', game['away'])):
        starters = {p['id']: p for p in game['teams'][team]['players'] if p['starter']}
        listed = [p for p in matches[0][side].get('players', []) if p.get('position') in ('PG', 'SG', 'SF', 'PF', 'C')]
        if len(starters) != 5 or len(listed) != 5 or len({p['position'] for p in listed}) != 5:
            continue
        mapped = []
        for p in listed:
            ids = [pid for pid, row in starters.items() if boxes.norm(row['name']) == boxes.norm(p.get('playerName', ''))]
            if len(ids) != 1 or p.get('lineupStatus') != 'Confirmed' or p.get('rosterStatus') != 'Active':
                break
            mapped.append(dict(playerId=ids[0], position=p['position'], team=team, effectiveGameDate=game['date'],
                               source=url, sourceHash=digest(payload, True), capturedAt=captured_at,
                               nbaPlayerId=str(p['personId']), status='Postgame NBA lineup role; not pregame confirmation'))
        if len(mapped) == 5 and len({p['playerId'] for p in mapped}) == 5:
            roles.extend(mapped)
    return roles


def ingest(f, state, fetcher, store, force=False):
    summary_url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=' + f['id']
    summary = fetcher(summary_url)
    g = identity_game(f, summary)
    library = state / 'library'
    for directory in ('records','pdf','text/final_boxes'):
        (library / directory).mkdir(parents=True, exist_ok=True)
    identities = defaultdict(set)
    for box in g['teams'].values():
        for p in box['players']:
            identities[boxes.norm(p['name'])].add(p['id'])
    record = boxes.collect_one(g, library, state / '_runtime/no-seed', identities, force=force)
    if record.get('sha256'):
        record['archiveUrl'] = store.content_file(library / record['pdf_path'], state / '_runtime/uploads', SEASON, f['date'])
    record['identitySource'] = {'url':summary_url,'sha256':digest(summary,True),'capturedAt':stamp()}
    identity_path=library/'identity_sources'/(f['id']+'.json')
    save(identity_path,summary)
    identity_meta={'url':summary_url,'sha256':hashlib.sha256(identity_path.read_bytes()).hexdigest(),'capturedAt':record['identitySource']['capturedAt'],'purpose':'identity crosswalk only; NBA PDF remains statistics authority'}
    save(identity_path.with_suffix('.source.json'),identity_meta)
    try: identity_meta['archiveUrl']=store.content_file(identity_path,state/'_runtime/uploads',SEASON,f['date'])
    except Exception as exc: identity_meta['archiveError']=str(exc)
    record['pbpIdentitySource']=identity_meta
    save(library / 'records' / (f['id'] + '.json'), record)
    if record['verification_status'] != 'verified':
        raise ValueError(record.get('error') or json.dumps(record.get('issues')))
    gid, events, error = opening.one_job((library, library / 'text/opening_quarter', g, record))
    if error:
        raise ValueError('NBA opening events: ' + error)
    record['opening'] = events
    save(library / 'records' / (gid + '.json'), record)
    result = official_game(g, record, events)
    lineup_url = 'https://stats.nba.com/js/data/leaders/00_daily_lineups_' + f['date'].replace('-', '') + '.json'
    try:
        lineup = fetcher(lineup_url)
        captured_at = stamp()
        roles = dated_lineup_roles(result, lineup, lineup_url, captured_at)
        save(library / 'lineups' / (digest(lineup, True) + '.json'), lineup)
        result.update(roleEvidence=roles, roleSourceStatus='Matched NBA/PDF starters' if roles else 'Specific roles unavailable or unmatched')
    except Exception as exc:
        result.update(roleEvidence=[], roleSourceStatus='NBA role source unavailable: ' + str(exc))
    return result


def payload_for(games, health):
    games = sorted(games, key=lambda g:(g['date'],g['id']))
    content = digest(games, True)
    meta = dict(schemaVersion=1, datasetId='nba-'+SEASON+'-canonical', parentDatasetId='nba-'+SEASON+'-canonical',
                season=SEASON, viewType='in-progress-season', coverageComplete=False,
                totalGames=len(games), asOfDate=max((g['date'] for g in games),default=None),
                phaseCounts=dict(Counter(g['phase'] for g in games)), openingCoverage=len(games),
                evidenceContentHash=content, scoringDefinition=TARGET, ingestionStatus='NBA-PDF-verified-in-progress',
                historicalInjuries='unavailable', pregameLineupAnnouncements='unavailable',
                sourceCaptureMeaning='Final NBA gamebooks captured after games; not pregame lineup evidence',
                fixtureReviewPolicyHash=hashlib.sha256((ROOT/'FIXTURE_IDENTITY_REVIEWS.json').read_bytes()).hexdigest())
    shooting = {g['id']:{t:{p['id']:p for p in b['players'] if p['played']} for t,b in g['teams'].items()} for g in games}
    openings = {g['id']:{**g['opening'], 'firstScores':g['firstScores'], 'firstFieldGoals':g['firstFieldGoals'],
                         'source':g['source'], 'sourceHash':g['sourceHash'],'date':g['date'],'phase':g['phase']} for g in games}
    ohash = digest(openings)
    parlay = {'meta':{'season':SEASON,'parentEvidenceContentHash':content,'contentHash':digest(shooting),
                      'openingContentHash':ohash,'verification':'Final statistics and opening events verified against archived NBA official gamebook PDFs.'},
              'games':shooting, 'openingEvidence':{'meta':{'season':SEASON,'parentEvidenceContentHash':content,
                  'contentHash':ohash,'games':len(games),'source':'NBA official first-quarter play-by-play'},'games':openings}}
    roles = [role for g in games for role in g.get('roleEvidence', [])]
    return {'meta':meta,'games':games,'datedRoleEvidence':roles, 'parlay':parlay}, {**meta,**health,'activeVersion':content+'.json'}


def collect(state, source=SOURCE, target_day=None, force=False, fetcher=fetch_json, store=None, ingester=ingest):
    state, source = Path(state), Path(source)
    state.mkdir(parents=True, exist_ok=True)
    target_day = target_day or (datetime.now(ZoneInfo('America/Chicago')).date()-timedelta(days=1)).isoformat()
    day = date.fromisoformat(target_day)
    if not date(2026,7,1) <= day <= date(2027,7,31):
        raise ValueError('Collection date is outside the enabled 2026-27 season')
    status = read(state/'state.json') if (state/'state.json').exists() else {'schemaVersion':1,'batches':{},'publishedKey':None}
    overlay(state, source)
    manifest = read(source/'seasons'/SEASON/'manifest.json')
    previous = read(source/'seasons'/SEASON/'versions'/manifest['activeVersion'])
    games = {g['id']:apply_fixture_review(g) for g in previous['games']}
    paths_pending=bool(games) and previous.get('openingPaths',{}).get('builderHash')!=opening_paths.CODE_HASH
    store = store or ReleaseArchive()
    requested = status['batches'].get(target_day)
    work = {d:b for d,b in status['batches'].items() if not b.get('complete')}
    if not requested or not requested.get('complete') or force:
        work[target_day] = requested or {}
    if not work and not games:
        return {'publish_needed':status.get('publishedKey')!=status.get('readyKey'),
                'pending':0,'skipped':True,'target_day':target_day}
    errors = []
    before = digest(list(games.values()), True)
    for workday, prior in sorted(work.items()):
        fixtures = {f['id']:f for f in prior.get('fixtures',[])}
        schedule_ok = True
        for lookup_day in (date.fromisoformat(workday), date.fromisoformat(workday)+timedelta(days=1)):
            url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=' + lookup_day.strftime('%Y%m%d') + '&limit=100'
            try:
                response = fetcher(url)
                if not isinstance(response.get('events'),list):
                    raise ValueError('Schedule events missing')
                captured = {'url':url,'capturedAt':stamp(),'payload':response}
                save(state/'schedule_captures'/(digest(response,True)+'.json'), captured)
                for event in response['events']:
                    f = fixture(event)
                    if f and f['date']==workday:
                        fixtures[f['id']] = f
            except Exception as exc:
                schedule_ok = False
                errors.append({'date':workday,'source':url,'error':str(exc)})
        pending = []
        for f in fixtures.values():
            if f['phase']=='preseason' or f['canceledOrPostponed']:
                continue
            if not f['completed']:
                pending.append({'id':f['id'],'reason':'Fixture not confirmed final'})
                continue
            if f['id'] in games and games[f['id']].get('boxScoreSource')=='NBA official final box' and not force:
                continue
            try:
                games[f['id']] = ingester(f,state,fetcher,store,force=force)
            except Exception as exc:
                pending.append({'id':f['id'],'reason':str(exc)})
                errors.append({'date':workday,'fixtureId':f['id'],'error':str(exc)})
        status['batches'][workday] = {'fixtures':list(fixtures.values()),'pending':pending,
                                     'scheduleVerified':schedule_ok,'complete':schedule_ok and not pending,'checkedAt':stamp()}
    pbp_manifest,pbp_changed = pbp_collect.update(state,list(games.values()),digest(sorted(games.values(),key=lambda g:(g['date'],g['id'])),True),force=force)
    if not work and not pbp_changed and not paths_pending:
        return {'publish_needed':status.get('publishedKey')!=status.get('readyKey'),'pending':0,'skipped':True,'target_day':target_day}
    pending = [p for batch in status['batches'].values() for p in batch.get('pending',[])]
    records = [read(state/'library/records'/(gid+'.json')) for gid in games]
    if digest(list(games.values()),True) != before and records:
        checks = boxes.build_database(state/'library',records)
        if checks['integrity_check']!='ok' or checks['foreign_key_issues'] or checks['unresolved_played_identities']:
            raise ValueError('Database verification failed')
        status['databaseUrl'] = store.content_file(state/'library/gamebooks.sqlite',state/'_runtime/uploads',SEASON,target_day)
        status['databaseChecks'] = checks
    health = {'checkedAt':stamp(), 'checkedFrom':min(status['batches']),'checkedThrough':max(status['batches']),
              'successfullyCheckedDates':[d for d,b in status['batches'].items() if b['complete']],
              'expectedCompletedInWindow':sum(f['completed'] and f['phase']!='preseason' for b in status['batches'].values() for f in b['fixtures']),
              'missingCompletedFixtures':[p['id'] for p in pending], 'sourceErrors':errors,
              'preseasonExcluded':[f for b in status['batches'].values() for f in b['fixtures'] if f['phase']=='preseason'],
              'seasonComplete':False,'monitoring':'GitHub Actions: morning NBA PDF collection; complete batches skip further collection',
              'collection':{'timezone':'America/Chicago','window':'08:00-11:00','intervalMinutes':30,
                  'targetDate':target_day,'targetComplete':status['batches'].get(target_day,{}).get('complete',False),
                  'pending':pending,'unresolvedScheduleDates':[d for d,b in status['batches'].items() if not b.get('scheduleVerified')],
                  'databaseUrl':status.get('databaseUrl'), 'databaseChecks':status.get('databaseChecks'),
                  'archive':'Original PDFs retained as hash-named GitHub release assets' if getattr(store,'public_archive',True) else 'Original PDFs retained locally; no archive upload performed', 'lastAttempt':stamp()}}
    try:
        health['playByPlayArchive']=pbp_collect.archive(state,store,SEASON,target_day)
    except Exception as exc:
        health['playByPlayArchiveError']=str(exc)
    payload, manifest = payload_for(list(games.values()),health)
    # Opening paths can remain verified when a later full-game event is incomplete.
    try:
        refs={gid:read(state/'library/records'/(gid+'.json')).get('opening',{}) for gid in games}
        paths=opening_paths.build(state/'library/play_by_play.sqlite',list(games.values()),refs,payload['meta']['evidenceContentHash'])
        payload['openingPaths']=paths
    except Exception as exc:
        payload['openingPaths']={'version':opening_paths.VERSION,'games':{},'reason':'Opening paths unavailable: '+str(exc)}
    folder = state/'seasons'/SEASON
    save(folder/'play_by_play/versions'/(pbp_manifest['contentHash']+'.json'),pbp_manifest)
    manifest['playByPlay']={'contentHash':pbp_manifest['contentHash'],'statusCounts':pbp_manifest['statusCounts']}
    save(folder/'versions'/manifest['activeVersion'],payload)
    save(folder/'manifest.json',manifest)
    status['readyKey'] = digest({'version':manifest['activeVersion'],'health':health},True)
    save(state/'state.json',status)
    overlay(state,source)
    return {'publish_needed':status.get('publishedKey')!=status['readyKey'],'pending':len(pending),
            'schedule_errors':len(health['collection']['unresolvedScheduleDates']),
            'skipped':False,'target_day':target_day,'verified_games':len(games)}


def probe(path, state):
    """Exercise a real NBA download and both parsers without changing season history."""
    g = read(path)
    identities = defaultdict(set)
    for team in g['teams'].values():
        for p in team['players']:
            identities[boxes.norm(p['name'])].add(p['id'])
    for directory in ('records','pdf'):
        (state/directory).mkdir(parents=True,exist_ok=True)
    record = boxes.collect_one(g,state,state/'no-seed',identities,force=True)
    if record['verification_status']!='verified':
        raise ValueError('Cloud NBA PDF probe failed: '+json.dumps(record.get('issues') or record.get('error')))
    gid, result, error = opening.one_job((state,state/'text/opening_quarter',g,record))
    if error:
        raise ValueError(error)
    print(json.dumps({'probe':'passed','game':gid,'pdfSha256':record['sha256'],'playedRows':sum(p['played'] for p in record['player_rows']),
                      'firstScorers':{t:e['id'] for t,e in result['firstScores'].items()}}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,default=ROOT/'.collection-state')
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--date')
    parser.add_argument('--force',action='store_true')
    parser.add_argument('--probe',type=Path)
    args=parser.parse_args()
    if args.probe:
        probe(args.probe,args.state)
    else:
        result=collect(args.state,args.source,args.date,args.force)
        print(json.dumps(result))
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as output:
                output.write('publish_needed='+str(result['publish_needed']).lower()+'\n')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as output:
                output.write('### NBA morning collection\n\n```json\n'+json.dumps(result,indent=2)+'\n```\n')
