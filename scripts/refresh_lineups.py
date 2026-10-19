"""Capture NBA confirmations and ESPN depth charts; maintain a five-minute game window."""
import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BRANCH = 'nba-live-lineups'
NAME = 'live-lineups.json'
PROJECTIONS = 'projected-lineups.json'
TEAM_IDS = {'ATL':1,'BOS':2,'BKN':17,'CHA':30,'CHI':4,'CLE':5,'DAL':6,'DEN':7,'DET':8,'GSW':9,'HOU':10,'IND':11,'LAC':12,'LAL':13,'MEM':29,'MIA':14,'MIL':15,'MIN':16,'NOP':3,'NYK':18,'OKC':25,'ORL':19,'PHI':20,'PHX':21,'POR':22,'SAC':23,'SAS':24,'TOR':28,'UTA':26,'WAS':27}
ALIASES = {'GS':'GSW','NY':'NYK','SA':'SAS','NO':'NOP','WSH':'WAS','UTAH':'UTA','PHO':'PHX'}


def schedule_url(day):
    return 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+day.replace('-','')+'&limit=100'


def depth_url(team):
    return 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+str(TEAM_IDS[team])+'/depthcharts'


def pregame(schedule, now, max_minutes=None):
    if not isinstance(schedule.get('events'), list):
        raise ValueError('Schedule unavailable; retain last NBA capture')
    games = []
    for event in schedule['events']:
        minutes = (datetime.fromisoformat(event['date'].replace('Z','+00:00'))-now).total_seconds()/60
        if event.get('status',{}).get('type',{}).get('state')=='pre' and minutes>0 and (max_minutes is None or minutes<=max_minutes):
            games.append(event)
    return games


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0', 'Referer':'https://www.nba.com/', 'Accept':'application/json'}), timeout=25) as response:
        return json.load(response)


def capture(now=None, fetcher=fetch, schedule=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo('America/Chicago')).date().isoformat()
    schedule = schedule if schedule is not None else fetcher(schedule_url(day))
    upcoming = [str(event['id']) for event in pregame(schedule, now, 120)]
    if not upcoming:
        return None
    source = 'https://stats.nba.com/js/data/leaders/00_daily_lineups_'+day.replace('-','')+'.json'
    payload = fetcher(source)
    if not isinstance(payload.get('games'), list):
        raise ValueError('NBA lineup response unavailable; retain last capture')
    return {'schemaVersion':1, 'date':day, 'source':source, 'capturedAt':datetime.now(timezone.utc).isoformat(),
            'activeFixtures':upcoming, 'payload':payload}


def capture_projections(now=None, fetcher=fetch, lookahead_days=7):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo('America/Chicago')).date()
    def scheduled(offset):
        date = (day+timedelta(days=offset)).isoformat()
        try:
            payload = fetcher(schedule_url(date))
            return date, pregame(payload, now), None
        except Exception as error:
            return date, [], str(error)
    with ThreadPoolExecutor(max_workers=4) as pool:
        schedules = list(pool.map(scheduled, range(lookahead_days+1)))
    teams, errors = {}, []
    for date, events, error in schedules:
        if error:
            errors.append(date+': '+error)
        for event in events:
            for competitor in event.get('competitions',[{}])[0].get('competitors',[]):
                abbreviation = competitor.get('team',{}).get('abbreviation')
                team = ALIASES.get(abbreviation,abbreviation)
                if team in TEAM_IDS:
                    teams[team] = event.get('season',{}).get('year')
    def chart(item):
        team, year = item
        try:
            payload = fetcher(depth_url(team))
            if str(payload.get('team',{}).get('id'))!=str(TEAM_IDS[team]) or payload.get('season',{}).get('year')!=year:
                raise ValueError('Depth chart team or season mismatch')
            charts = payload.get('depthchart',[])
            if len(charts)!=1 or not all(p in charts[0].get('positions',{}) for p in ('pg','sg','sf','pf','c')):
                raise ValueError('Complete depth chart unavailable')
            # Keep source IDs/order, injury labels, season, and source timestamps.
            slim = {key:payload.get(key) for key in ('team','season','timestamp')}
            slim['depthchart'] = [{'positions':{pos:{'athletes':[{key:p.get(key) for key in ('id','displayName','injuries')} for p in box.get('athletes',[])]} for pos,box in charts[0]['positions'].items()}}]
            return team, {'source':depth_url(team),'capturedAt':datetime.now(timezone.utc).isoformat(),'payload':slim}, None
        except Exception as error:
            return team, None, str(error)
    with ThreadPoolExecutor(max_workers=4) as pool:
        charts = list(pool.map(chart, sorted(teams.items())))
    for team, record, error in charts:
        if error:
            errors.append(team+': '+error)
    return {'schemaVersion':1,'capturedAt':datetime.now(timezone.utc).isoformat(),'checkedFrom':day.isoformat(),'checkedThrough':(day+timedelta(days=lookahead_days)).isoformat(),
            'teams':{team:record for team,record,error in charts if record},'errors':errors,
            'meaning':'Current ESPN depth charts for browser-derived, unconfirmed projections; these are not announced game lineups.'}


def git(*args, data=None, check=True):
    result = subprocess.run(['git', *args], input=data, capture_output=True)
    if check and result.returncode:
        raise RuntimeError('git '+args[0]+' failed: '+result.stderr.decode(errors='replace').strip())
    return result


def publish(record):
    # A separate, small branch avoids racing or replacing morning PDF state.
    records = {NAME:record} if 'schemaVersion' in record else record
    if not records or not set(records).issubset({NAME,PROJECTIONS}):
        raise ValueError('Unexpected capture filename')
    blobs = {name:git('hash-object','-w','--stdin',data=(json.dumps(payload,separators=(',',':'))+'\n').encode()).stdout.decode().strip() for name,payload in records.items()}
    for attempt in range(3):
        git('fetch','origin','+refs/heads/'+BRANCH+':refs/remotes/origin/'+BRANCH,check=False)
        parent = git('rev-parse','--verify','origin/'+BRANCH,check=False)
        entries = {}
        if parent.returncode==0:
            for line in git('ls-tree',parent.stdout.decode().strip()).stdout.decode().splitlines():
                metadata,name = line.split('\t')
                if name not in {NAME,PROJECTIONS}:
                    raise ValueError('Unexpected file in capture branch')
                entries[name] = metadata.split()[2]
        entries.update(blobs)
        # A sparse/partial checkout may not have the unchanged remote cache blob.
        # Its hash comes from the fetched parent tree; the server already has it.
        tree = git('mktree','--missing',data=''.join(f'100644 blob {blob}\t{name}\n' for name,blob in sorted(entries.items())).encode()).stdout.decode().strip()
        args = ['commit-tree',tree,'-m','Refresh sourced lineup context']
        if parent.returncode==0:
            args += ['-p',parent.stdout.decode().strip()]
        commit = git(*args).stdout.decode().strip()
        result = git('push','origin',commit+':refs/heads/'+BRANCH,check=False)
        if result.returncode==0:
            return commit
    raise RuntimeError('Could not publish lineup capture after three attempts')


def run(watch=False, max_minutes=240, lookahead_days=7, fetcher=fetch, publisher=publish,
        clock=lambda:datetime.now(timezone.utc), monotonic=time.monotonic, sleeper=time.sleep):
    deadline = monotonic()+max_minutes*60
    last_projection = None
    watching = False
    while True:
        failed = False
        now = clock()
        day = now.astimezone(ZoneInfo('America/Chicago')).date().isoformat()
        records = {}
        try:
            if last_projection is None or monotonic()-last_projection>=300:
                projection = capture_projections(now,fetcher,lookahead_days)
                if projection['teams']:
                    records[PROJECTIONS] = projection
                last_projection = monotonic()
                print(json.dumps({'projectionTeams':len(projection['teams']),'errors':projection['errors']}),flush=True)
                failed = bool(projection['errors']) and not projection['teams']
        except Exception as error:
            failed = True
            print(json.dumps({'projectionError':str(error),'checkedAt':clock().isoformat()}),flush=True)
        try:
            schedule = fetcher(schedule_url(day))
            close = pregame(schedule,now,120)
            watching = watching or bool(close)
            official = capture(now,fetcher,schedule)
            if official:
                records[NAME] = official
            remaining = bool(pregame(schedule,now))
        except Exception as error:
            failed = True
            print(json.dumps({'error':str(error),'checkedAt':clock().isoformat(),'retained':'last verified captures'}),flush=True)
            remaining = watching
        if records:
            try:
                print(json.dumps({'published':list(records),'commit':publisher(records),'checkedAt':clock().isoformat()}),flush=True)
            except Exception as error:
                failed = True
                print(json.dumps({'publishError':str(error),'checkedAt':clock().isoformat(),'retained':'last verified captures'}),flush=True)
        if not watch or not watching or not remaining or monotonic()+300>=deadline:
            return failed
        sleeper(300)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--max-minutes',type=int,default=240)
    parser.add_argument('--lookahead-days',type=int,default=7,choices=range(1,8))
    args = parser.parse_args()
    if not 1<=args.max_minutes<=330:
        parser.error('--max-minutes must be between 1 and 330')
    os.environ.update(GIT_AUTHOR_NAME='FTB lineup collector',GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',
                      GIT_COMMITTER_NAME='FTB lineup collector',GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
    if run(args.watch,args.max_minutes,args.lookahead_days):
        raise SystemExit(1)
