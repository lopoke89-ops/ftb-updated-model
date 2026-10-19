"""Read-only Tennessee prop captures. No account, betslip, or wagering operations."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BRANCH = 'nba-live-odds'
PUBLIC = 'https://raw.githubusercontent.com/lopoke89-ops/ftb-updated-model/'+BRANCH+'/odds.json'
SITE = 'https://sportsbook.fanduel.com'
API = 'https://api.sportsbook.fanduel.com/sbapi/'
TEAMS = {'ATL':1,'BOS':2,'BKN':17,'CHA':30,'CHI':4,'CLE':5,'DAL':6,'DEN':7,'DET':8,'GSW':9,'HOU':10,'IND':11,'LAC':12,'LAL':13,'MEM':29,'MIA':14,'MIL':15,'MIN':16,'NOP':3,'NYK':18,'OKC':25,'ORL':19,'PHI':20,'PHX':21,'POR':22,'SAC':23,'SAS':24,'TOR':28,'UTA':26,'WAS':27}
ALIASES = {'GS':'GSW','NY':'NYK','SA':'SAS','NO':'NOP','WSH':'WAS','UTAH':'UTA','PHO':'PHX'}
TABS = ('player-points','player-threes')

def utc():
    return datetime.now(timezone.utc)

def iso(value):
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Source time must have a timezone')
    return parsed.astimezone(timezone.utc)

def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).lower() if c.isascii() and c.isalnum())

def base_name(value):
    return normalize(re.sub(r'\s+(?:jr|sr|ii|iii|iv)\.?$', '', value.strip(), flags=re.I))

class Client:
    def __init__(self, sleeper=time.sleep):
        self.key = None
        self.sleeper = sleeper

    def raw(self, url, region=False):
        headers = {'User-Agent':'Mozilla/5.0','Accept':'application/json' if region else '*/*'}
        if region:
            headers['X-Sportsbook-Region'] = 'TN'
        for attempt in range(3):
            try:
                with urlopen(Request(url,headers=headers),timeout=15) as response:
                    return response.read()
            except HTTPError as error:
                if error.code not in (429,500,502,503,504) or attempt==2:
                    raise RuntimeError('Source HTTP '+str(error.code)) from None
                retry = error.headers.get('Retry-After','')
                delay = int(retry) if retry.isdigit() else 2**attempt
                if delay>30:
                    raise RuntimeError('Source requested a later retry; capture retained') from None
                self.sleeper(delay)
            except (URLError, TimeoutError):
                if attempt==2:
                    raise RuntimeError('Source timed out/unavailable') from None
                self.sleeper(2**attempt)

    def json(self, url):
        return json.loads(self.raw(url))

    def bootstrap(self):
        page = self.raw(SITE+'/navigation/nba').decode()
        paths = re.findall(r'<script[^>]+src=["\']([^"\']+)',page,re.I)
        main = [s for s in paths if re.search(r'/main\.[a-z0-9]+\.js$',s)]
        if len(main)!=1:
            raise ValueError('FanDuel public script layout changed')
        script = self.raw(urljoin(SITE,main[0])).decode()
        # The production FANDUEL entry references a literal in the same public bundle.
        # Never execute source scripts or use account credentials.
        candidates = []
        for match in re.finditer(r'\{\[[A-Za-z_$][\w$]*\.FANDUEL\]:([A-Za-z_$][\w$]*),',script):
            variable = re.escape(match.group(1))
            literals = list(re.finditer(r'(?:let|const|var|,)\s*'+variable+r'="([A-Za-z0-9_-]{12,80})"',script[:match.start()]))
            if literals:
                candidates.append(literals[-1].group(1))
        keys = set(candidates)
        if len(keys)!=1:
            raise ValueError('FanDuel public application configuration changed')
        self.key = keys.pop()

    def fd(self, endpoint, **params):
        if not self.key:
            self.bootstrap()
        # Public application identifier stays out of logs, snapshots and source links.
        raw = self.raw(API+endpoint+'?'+urlencode({'_ak':self.key,**params}),region=True)
        return json.loads(raw),hashlib.sha256(raw).hexdigest()

def schedule(client, now, days=3):
    date = now.astimezone(ZoneInfo('America/Chicago')).date()
    rows,errors = [],[]
    for offset in range(days+1):
        day = (date+timedelta(days=offset)).isoformat()
        try:
            payload = client.json('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+day.replace('-','')+'&limit=100')
            if not isinstance(payload.get('events'),list):
                raise ValueError('Schedule schema changed')
            for event in payload['events']:
                competition = event['competitions'][0]
                if competition['status']['type']['state']!='pre' or iso(event['date'])<=now:
                    continue
                # NBA regular-season type 2 only; the EV model has no playoff/preseason calibration.
                if event.get('season',{}).get('type')!=2:
                    continue
                teams = {r['homeAway']:ALIASES.get(r['team']['abbreviation'],r['team']['abbreviation']) for r in competition['competitors']}
                if set(teams.values()).issubset(TEAMS):
                    rows.append({'id':str(event['id']),'date':day,'home':teams['home'],'away':teams['away'],'season':str(event['season']['year']-1)+'-'+str(event['season']['year'])[-2:],
                                 'phase':'regular-season','scheduledTipoff':event['date'],'status':'pre','names':{r['homeAway']:[r['team'].get('displayName',''),r['team'].get('shortDisplayName','')] for r in competition['competitors']}})
        except Exception as error:
            errors.append(day+': '+str(error))
    if len({r['id'] for r in rows})!=len(rows):
        raise ValueError('Duplicate schedule fixtures')
    return rows,errors

def match_event(fixture, events):
    def names(side):
        values = fixture['names'][side]
        if fixture[side]=='LAC':
            values = values+['Los Angeles Clippers','LA Clippers']
        return {normalize(n) for n in values}
    matches=[]
    for event in events.values():
        split = event.get('name','').split(' @ ')
        if len(split)!=2 or normalize(split[0]) not in names('away') or normalize(split[1]) not in names('home'):
            continue
        if event.get('competitionId')!=10547864 or event.get('eventTypeId')!=7522 or event.get('inPlay') is True:
            continue
        if abs((iso(event['openDate'])-iso(fixture['scheduledTipoff'])).total_seconds())<=900:
            matches.append(event)
    if len(matches)!=1:
        raise ValueError('No unique FanDuel event matching both teams and tipoff')
    return matches[0]

def market_contract(market):
    kind = market.get('marketType','')
    if re.fullmatch(r'PLAYER_[A-Z]+_TOTAL_POINTS',kind):
        return 'points','ou',None
    if re.fullmatch(r'PLAYER_[A-Z]+_TOTAL_MADE_3_POINT_FIELD_GOALS',kind):
        return 'threes','ou',None
    match = re.fullmatch(r'TO_SCORE_(\d+)\+_POINTS',kind)
    if match:
        return 'points','at-least',int(match[1])
    match = re.fullmatch(r'(\d+)\+_MADE_THREES',kind)
    if match:
        return 'threes','at-least',int(match[1])
    return None

def parse_markets(payload, fixture, event, roster, captured_at, tab):
    identity = payload.get('attachments',{}).get('events',{}).get(str(event['eventId']))
    if not identity or identity['name']!=event['name'] or identity['openDate']!=event['openDate'] or identity.get('inPlay') is True:
        raise ValueError('FanDuel event identity/status changed')
    cards = payload.get('layout',{}).get('cards',{})
    title = {'player-points':'Player Points','player-threes':'Player Threes'}[tab]
    tabs = payload.get('layout',{}).get('tabs',{})
    if not any(t.get('title')==title for t in tabs.values()):
        return [],['Market not yet offered: '+title]
    if not any(c.get('title')==title and c.get('attachmentsFullyLoaded') is True for c in cards.values()):
        raise ValueError('Requested market tab was not fully loaded')
    quotes,issues = [],[]
    for market in payload.get('attachments',{}).get('markets',{}).values():
        contract = market_contract(market)
        if not contract or contract[0]!=('points' if tab=='player-points' else 'threes'):
            continue
        if market.get('eventId')!=event['eventId'] or market.get('eventTypeId')!=7522 or market.get('inPlay') is True:
            raise ValueError('Market fixture/sport/status mismatch')
        prop,kind,target = contract
        for runner in market.get('runners',[]):
            if runner.get('isPlayerSelection') is not True:
                continue
            try:
                name = runner['runnerName']
                if kind=='ou':
                    side = {'OVER':'over','UNDER':'under'}.get(runner.get('result',{}).get('type'))
                    if not side or not name.endswith(' '+side.title()):
                        raise ValueError('Over/under side is ambiguous')
                    name = name[:-(len(side)+1)]
                    expected = ' - Points' if prop=='points' else ' - Made Threes'
                    if market['marketName']!=name+expected:
                        raise ValueError('Market/player label mismatch')
                    line = runner['handicap']
                else:
                    side,line = 'at-least',target
                if isinstance(line,bool) or not isinstance(line,(int,float)) or line<0:
                    raise ValueError('Invalid target')
                players = [p for p in roster if normalize(p['name'])==normalize(name)]
                identity_join = 'exact-normalized-name'
                if not players:
                    players = [p for p in roster if base_name(p['name'])==base_name(name)]
                    identity_join = 'unique-name-with-optional-suffix'
                if len(players)!=1:
                    raise ValueError('Player name does not uniquely resolve to current matchup roster: '+name)
                player = players[0]
                odds = runner['winRunnerOdds']
                american = odds['americanDisplayOdds']['americanOddsInt']
                decimal = odds['trueOdds']['decimalOdds']['decimalOdds']
                if not isinstance(american,int) or abs(american)<100 or not isinstance(decimal,(int,float)) or not 1<decimal<10001:
                    raise ValueError('Invalid offered odds')
                expected_decimal = 1+american/100 if american>0 else 1+100/abs(american)
                if abs(decimal-expected_decimal)>1e-6:
                    raise ValueError('American/decimal price mismatch')
                quotes.append({'key':str(event['eventId'])+'|'+str(market['marketId'])+'|'+str(runner['selectionId'])+'|'+str(line)+'|'+side,
                               'fixtureId':fixture['id'],'fanduelEventId':str(event['eventId']),'fanduelTipoff':event['openDate'],'marketId':str(market['marketId']),'selectionId':str(runner['selectionId']),
                               'playerId':player['id'],'player':player['name'],'team':player['team'],'market':prop,'marketType':market['marketType'],'marketName':market['marketName'],
                               'identityJoin':identity_join,
                               'period':'full-game','side':side,'line':line,'american':american,'decimal':decimal,'marketStatus':market['marketStatus'],'runnerStatus':runner['runnerStatus'],
                               'region':'TN','capturedAt':captured_at,'captureState':'fresh','source':SITE+'/basketball/nba/'+re.sub(r'[^a-z0-9@]+','-',event['name'].lower()).strip('-')+'-'+str(event['eventId'])+'?tab='+tab})
            except (KeyError,ValueError,TypeError) as error:
                issues.append(str(error))
    if len({q['key'] for q in quotes})!=len(quotes):
        raise ValueError('Duplicate quote identities')
    return quotes,sorted(set(issues))

def capture(client=None, previous=None, now=None, days=3):
    client,now,previous = client or Client(),now or utc(),previous or {}
    fixtures,errors = schedule(client,now,days)
    listing,listing_hash = client.fd('competition-page',competitionId='10547864',eventTypeId='7522',tab='matches',timezone='America/Chicago')
    events = listing.get('attachments',{}).get('events',{})
    if not events:
        raise ValueError('FanDuel NBA listing unavailable')
    rosters = {}
    for team in sorted({t for f in fixtures for t in (f['home'],f['away'])}):
        try:
            payload = client.json('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+str(TEAMS[team])+'/roster')
            if str(payload.get('team',{}).get('id'))!=str(TEAMS[team]):
                raise ValueError('Roster team identity mismatch')
            athletes = [p for group in payload.get('athletes',[]) for p in group.get('items',[group])]
            rosters[team] = [{'id':str(p['id']),'name':p['displayName'],'team':team} for p in athletes if p.get('id') and p.get('displayName')]
            if len(rosters[team])<5 or len({p['id'] for p in rosters[team]})!=len(rosters[team]):
                raise ValueError('Roster identity/coverage unavailable')
        except Exception as error:
            rosters[team] = []
            errors.append(team+': '+str(error))
    def one(fixture):
        old = previous.get('fixtures',{}).get(fixture['id'],{})
        entry = {'fixture':{k:v for k,v in fixture.items() if k!='names'},'checkedAt':utc().isoformat(),'quotes':[],'issues':[],'captures':[]}
        try:
            event = match_event(fixture,events)
            roster = rosters[fixture['home']]+rosters[fixture['away']]
            if not rosters[fixture['home']] or not rosters[fixture['away']]:
                raise ValueError('Current matchup rosters unavailable')
            entry['fanduelEventId'] = str(event['eventId'])
            for tab in TABS:
                prop = 'points' if tab=='player-points' else 'threes'
                try:
                    payload,raw_hash = client.fd('event-page',eventId=str(event['eventId']),tab=tab,useCombinedTouchdownsVirtualMarket='true',useQuickBets='true')
                    captured = utc().isoformat()
                    quotes,issues = parse_markets(payload,fixture,event,roster,captured,tab)
                    entry['quotes'].extend(quotes);entry['issues'].extend(issues)
                    entry['captures'].append({'tab':tab,'capturedAt':captured,'sha256':raw_hash})
                except Exception as error:
                    entry['issues'].append(tab+': '+str(error))
                    entry['quotes'].extend({**q,'captureState':'cached'} for q in old.get('quotes',[]) if q['market']==prop and q.get('fanduelEventId')==str(event['eventId']))
        except Exception as error:
            entry['issues'].append(str(error))
            entry['quotes'] = [{**q,'captureState':'cached'} for q in old.get('quotes',[]) if q.get('fixtureId')==fixture['id']]
        return fixture['id'],entry
    with ThreadPoolExecutor(max_workers=3) as pool:
        entries = dict(pool.map(one,fixtures))
    # A failed schedule date must not wipe its earlier captures. Their age never resets.
    for fid,old in previous.get('fixtures',{}).items():
        if fid not in entries and iso(old['fixture']['scheduledTipoff'])>now and errors:
            entries[fid] = {**old,'checkedAt':utc().isoformat(),'issues':['Schedule unavailable; previous capture retained'],'quotes':[{**q,'captureState':'cached'} for q in old.get('quotes',[])]}
    return {'schemaVersion':1,'bookmaker':'fanduel','region':'TN','checkedAt':utc().isoformat(),'lookaheadDays':days,'fixtures':entries,'errors':errors,'listingHash':listing_hash,
            'meaning':'Full-game points and made-threes prices; ACTIVE means market availability, not starter confirmation. Captures are immutable as to original source capture time.'}

def git(*args,data=None,check=True):
    result = subprocess.run(['git',*args],input=data,capture_output=True)
    if check and result.returncode:
        raise RuntimeError('Git '+args[0]+' failed: '+result.stderr.decode(errors='replace').strip())
    return result

def publish(snapshot):
    blob = git('hash-object','-w','--stdin',data=(json.dumps(snapshot,separators=(',',':'))+'\n').encode()).stdout.decode().strip()
    for _ in range(3):
        git('fetch','origin','+refs/heads/'+BRANCH+':refs/remotes/origin/'+BRANCH,check=False)
        parent = git('rev-parse','--verify','origin/'+BRANCH,check=False)
        tree = git('mktree',data=('100644 blob '+blob+'\todds.json\n').encode()).stdout.decode().strip()
        args = ['commit-tree',tree,'-m','Capture Tennessee full-game prop prices']
        if parent.returncode==0:
            args += ['-p',parent.stdout.decode().strip()]
        commit = git(*args).stdout.decode().strip()
        if git('push','origin',commit+':refs/heads/'+BRANCH,check=False).returncode==0:
            return commit
    raise RuntimeError('Odds publication failed; earlier snapshot retained')

def run(watch=False,output=None,max_minutes=240):
    client = Client()
    try:
        previous = client.json(PUBLIC)
    except Exception:
        previous = {}
    deadline = time.monotonic()+max_minutes*60
    watching = False
    while True:
        cycle_start = time.monotonic()
        try:
            snapshot = capture(client,previous)
            if output:
                Path(output).parent.mkdir(parents=True,exist_ok=True)
                Path(output).write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8',newline='\n')
            else:
                publish(snapshot)
            previous = snapshot
            quotes = [q for e in snapshot['fixtures'].values() for q in e['quotes']]
            issues = snapshot['errors']+[e for f in snapshot['fixtures'].values() for e in f['issues']]
            print(json.dumps({'checkedAt':snapshot['checkedAt'],'fixtures':len(snapshot['fixtures']),'quotes':len(quotes),'issues':issues}),flush=True)
            now = utc()
            future = [iso(f['fixture']['scheduledTipoff']) for f in snapshot['fixtures'].values() if iso(f['fixture']['scheduledTipoff'])>now]
            watching = watching or bool(future)
            if not watch or output or not watching or not future or time.monotonic()+300>=deadline:
                return bool(snapshot['errors']) or any(any(not e.startswith('Market not yet offered:') for e in f['issues']) for f in snapshot['fixtures'].values())
        except Exception as error:
            print(json.dumps({'error':str(error),'checkedAt':utc().isoformat(),'retained':'previous published capture'}),flush=True)
            if not watch or not watching or time.monotonic()+300>=deadline:
                return True
        time.sleep(max(0,300-(time.monotonic()-cycle_start)))

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--max-minutes',type=int,default=240,choices=range(1,241))
    args = parser.parse_args()
    os.environ.update(GIT_AUTHOR_NAME='FTB odds collector',GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',GIT_COMMITTER_NAME='FTB odds collector',GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
    if run(args.watch,args.output,args.max_minutes):
        raise SystemExit(1)
