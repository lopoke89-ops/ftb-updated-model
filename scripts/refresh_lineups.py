"""Publish an unchanged NBA lineup response with its real server capture time."""
import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BRANCH = 'nba-live-lineups'
NAME = 'live-lineups.json'


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0', 'Referer':'https://www.nba.com/', 'Accept':'application/json'}), timeout=25) as response:
        return json.load(response)


def capture(now=None, fetcher=fetch):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo('America/Chicago')).date().isoformat()
    schedule = fetcher('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+day.replace('-','')+'&limit=100')
    if not isinstance(schedule.get('events'), list):
        raise ValueError('Schedule unavailable; retain last NBA capture')
    upcoming = []
    for event in schedule['events']:
        tip = datetime.fromisoformat(event['date'].replace('Z','+00:00'))
        minutes = (tip-now).total_seconds()/60
        if event.get('status',{}).get('type',{}).get('state') == 'pre' and 0 < minutes <= 120:
            upcoming.append(str(event['id']))
    if not upcoming:
        return None
    source = 'https://stats.nba.com/js/data/leaders/00_daily_lineups_'+day.replace('-','')+'.json'
    payload = fetcher(source)
    if not isinstance(payload.get('games'), list):
        raise ValueError('NBA lineup response unavailable; retain last capture')
    return {'schemaVersion':1, 'date':day, 'source':source, 'capturedAt':datetime.now(timezone.utc).isoformat(),
            'activeFixtures':upcoming, 'payload':payload}


def git(*args, data=None, check=True):
    return subprocess.run(['git', *args], input=data, capture_output=True, check=check)


def publish(record):
    # A separate, small branch avoids racing or replacing morning PDF state.
    git('fetch','origin','+refs/heads/'+BRANCH+':refs/remotes/origin/'+BRANCH,check=False)
    parent = git('rev-parse','--verify','origin/'+BRANCH,check=False)
    blob = git('hash-object','-w','--stdin',data=(json.dumps(record,separators=(',',':'))+'\n').encode()).stdout.decode().strip()
    tree = git('mktree',data=f'100644 blob {blob}\t{NAME}\n'.encode()).stdout.decode().strip()
    args = ['commit-tree',tree]
    if parent.returncode == 0:
        args += ['-p',parent.stdout.decode().strip()]
    commit = git(*args,'-m','Capture official NBA daily lineups').stdout.decode().strip()
    git('push','origin',commit+':refs/heads/'+BRANCH)
    return commit


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    record = capture()
    if record is None:
        print('Skipped: no pregame fixture within two hours of tipoff')
    else:
        os.environ.update(GIT_AUTHOR_NAME='FTB lineup collector',GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',
                          GIT_COMMITTER_NAME='FTB lineup collector',GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
        commit = publish(record)
        print(json.dumps({'capturedAt':record['capturedAt'],'date':record['date'],'fixtures':record['activeFixtures'],'commit':commit}))
