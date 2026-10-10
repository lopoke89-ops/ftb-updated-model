"""Workbook event/role model with authoritative NBA gamebook season statistics."""
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,math,re,unicodedata
import pandas as pd
BASE=Path(__file__).resolve().parent
DATA=BASE.parent/'first team basket dataset'
CANONICAL_DATA=DATA/'NBA_2025-26_Canonical.xlsx'
DATASET_ID='nba-2025-26-canonical'
EXPECTED_PHASE_COUNTS={'regular-season':1230,'playoffs':85,'play-in':6,'nba-cup-final':1}
SHOTS=('layup','dunk','mid','threeP','ft','tip','hook')
POSITIONS=('PG','SG','SF','PF','C')
SCORING_DEFINITION='first-team-score-including-free-throws'
def text(v):return '' if v is None or pd.isna(v) else str(v).strip()
def key(v):return ''.join(c for c in unicodedata.normalize('NFD',text(v)).lower() if c.isalnum() and not unicodedata.combining(c))
def initial_key(name):
    p=text(name).replace('.','').split()
    return key(p[0][0]+' '+' '.join(p[1:])) if len(p)>1 else ''
def number(v):
    try:
        n=float(v)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None
def classify_shot(desc,points=None):
    s=text(desc).lower()
    if not s:return None
    if 'free throw' in s:return 'ft'
    if '3pt' in s or '3-point' in s or number(points)==3:return 'threeP'
    for kind in ['dunk','tip','hook','layup']:
        if kind in s:return kind
    return 'mid'
class Identities:
    def __init__(self,roster,ppg,line):
        self.names={};self.aliases=defaultdict(set);self.teams=defaultdict(set);self.positions={};self.starters=defaultdict(set);self.issues=[]
        override_path=BASE/'identity_overrides.json'
        self.overrides=json.loads(override_path.read_text(encoding='utf-8')) if override_path.exists() else {}
        for r in ppg.to_dict('records'):self.add(text(r['FULL_NAME']),text(r['TEAM']))
        for r in line.to_dict('records'):
            for i in range(1,6):
                n=text(r.get(f'STARTER_{i}'))
                if not n:continue
                k=self.add(n,text(r['TEAM']));self.starters[(r['GAME_DATE'],text(r['TEAM']))].add(k)
                if text(r.get(f'POS_{i}')) in POSITIONS:self.positions[k]=text(r[f'POS_{i}'])
        for r in roster:
            n,a=text(r.get('full_name')),text(r.get('abbreviated'));k=key(n)
            if not k:continue
            candidates=self.aliases.get(key(a),set())
            if candidates and k not in candidates:
                self.issues.append({'kind':'ignored_roster_alias','alias':a,'rosterName':n,'sourceNames':[self.names[c] for c in sorted(candidates)]});continue
            if k not in self.names:self.add(n,text(r.get('primary_team')))
            self.aliases[key(a)].add(k)
            if text(r.get('position')) in POSITIONS:self.positions.setdefault(k,r['position'])
    def add(self,n,team=''):
        k=key(n)
        if not k:return ''
        self.names.setdefault(k,n);self.aliases[k].add(k)
        if initial_key(n):self.aliases[initial_key(n)].add(k)
        if team:self.teams[k].add(team)
        return k
    def resolve(self,n,team='',date=''):
        k=key(n);candidates={k} if k in self.names else self.aliases.get(k,set())
        override=self.overrides.get(date+'|'+team+'|'+k)
        if override:
            chosen=key(override['name'])
            if chosen not in candidates:raise ValueError('Identity override is not a source candidate')
            candidates={chosen}
        if len(candidates)>1:
            starters=candidates & self.starters.get((date,team),set())
            matches={c for c in candidates if team in self.teams[c]}
            if len(starters)==1:candidates=starters
            elif len(matches)==1:candidates=matches
        if len(candidates)==1:
            k=next(iter(candidates));return k,self.names[k],self.positions.get(k,''),True
        self.issues.append({'kind':'ambiguous_name' if candidates else 'unresolved_name','name':n,'team':team,'date':date,'candidates':[self.names[c] for c in sorted(candidates)]})
        return key(team+' '+n),n,'',False
def build_dataset(ftb_path=CANONICAL_DATA,lineup_path=None,ppg_path=None,roster_path=BASE/'player_roster.json'):
    if not Path(roster_path).exists():raise ValueError(f'Roster file is missing: {roster_path}')
    lineup_path=Path(lineup_path) if lineup_path else Path(ftb_path)
    ppg_path=Path(ppg_path) if ppg_path else Path(ftb_path)
    roster=json.loads(Path(roster_path).read_text(encoding='utf-8'))['players']
    ftb=pd.read_excel(ftb_path,sheet_name='First Baskets',dtype={'GAME_ID':str,'ESPN_EVENT_ID':str,'HOME_PLAYER_ID':str,'AWAY_PLAYER_ID':str}).dropna(how='all')
    line=pd.read_excel(lineup_path,sheet_name='Lineups',dtype={'GAME_ID':str,'ESPN_EVENT_ID':str}).dropna(how='all')
    ppg=pd.read_excel(ppg_path,sheet_name='PPG',dtype={'PLAYER_ID':str}).dropna(how='all')
    if ppg.PLAYER_ID.duplicated().any() or ppg.FULL_NAME.map(key).duplicated().any():raise ValueError('Duplicate source player identity')
    if any(text(v)!='all-included-games' for v in ppg.STAT_SCOPE):raise ValueError('Player averages use a different season scope')
    phase_gp=[f"GP_{phase.upper().replace('-','_')}" for phase in EXPECTED_PHASE_COUNTS]
    if any(ppg[phase_gp].sum(axis=1)!=ppg.GP):raise ValueError('Player appearances do not reconcile across season phases')
    if ppg.FIRST_BASKET_COUNT.sum()!=len(ftb)*2:raise ValueError('Player first-score counts disagree with game rows')
    for df in [ftb,line]:
        df['GAME_DATE']=pd.to_datetime(df['GAME_DATE'],errors='raise').dt.strftime('%Y-%m-%d')
        df['GAME_ID']=df['GAME_ID'].astype(str)
    if 'GAME_TYPE' not in ftb or 'GAME_TYPE' not in line:raise ValueError('Canonical source must label every season phase')
    phase_counts=ftb.GAME_TYPE.value_counts().to_dict()
    if phase_counts!=EXPECTED_PHASE_COUNTS:raise ValueError('Canonical season coverage is incomplete: '+json.dumps(phase_counts))
    if 'ESPN_EVENT_ID' not in ftb or ftb.ESPN_EVENT_ID.astype(str).duplicated().any():raise ValueError('Missing/duplicate source event identity')
    if any(r.GAME_ID!='ESPN:'+r.ESPN_EVENT_ID for r in ftb.itertuples()):raise ValueError('Canonical games require consistent ESPN source IDs')
    if ftb.duplicated(['GAME_DATE','HOME_TEAM','AWAY_TEAM']).any() or ftb.GAME_ID.duplicated().any():raise ValueError('Duplicate first-basket game')
    if line.duplicated(['GAME_DATE','TEAM','OPPONENT']).any():raise ValueError('Duplicate lineup game')
    fixtures={(r.GAME_DATE,r.HOME_TEAM,r.AWAY_TEAM) for r in ftb.itertuples()}
    home=line[line.HOME_AWAY=='HOME']
    if fixtures!={(r.GAME_DATE,r.TEAM,r.OPPONENT) for r in home.itertuples()}:raise ValueError('First-basket and lineup fixture coverage disagree')
    away=line[line.HOME_AWAY=='AWAY']
    if len(line)!=2*len(ftb) or fixtures!={(r.GAME_DATE,r.OPPONENT,r.TEAM) for r in away.itertuples()}:raise ValueError('Away lineup fixture coverage disagrees')
    fixture_identity={(r.GAME_DATE,r.HOME_TEAM,r.AWAY_TEAM):(r.GAME_ID,r.GAME_TYPE) for r in ftb.itertuples()}
    for r in line.itertuples():
        f=(r.GAME_DATE,r.TEAM,r.OPPONENT) if r.HOME_AWAY=='HOME' else (r.GAME_DATE,r.OPPONENT,r.TEAM)
        if fixture_identity[f]!=(r.GAME_ID,r.GAME_TYPE):raise ValueError('Lineup game ID or season phase disagrees')
    regular_team_games=defaultdict(int)
    for r in ftb[ftb.GAME_TYPE=='regular-season'].itertuples():
        regular_team_games[r.HOME_TEAM]+=1;regular_team_games[r.AWAY_TEAM]+=1
    if len(regular_team_games)!=30 or any(n!=82 for n in regular_team_games.values()):raise ValueError('Regular-season team coverage must be 82 games per team')
    for side in ['HOME','AWAY']:
        if any(number(v) not in [1,2,3] for v in ftb[f'{side}_POINTS']):raise ValueError('First-score source contains invalid or missing points')
        for r in ftb.to_dict('records'):
            points=number(r[f'{side}_POINTS']);desc=text(r[f'{side}_SHOT_DESC']).lower()
            if 'misses' in desc or (points==1 and 'free throw' not in desc) or (points>1 and 'free throw' in desc):raise ValueError('Scoring points and shot description disagree')
    source_names={text(r.PLAYER_ID):key(r.FULL_NAME) for r in ppg.itertuples()}
    for r in ftb.to_dict('records'):
        for side in ['HOME','AWAY']:
            if source_names.get(text(r[side+'_PLAYER_ID']))!=key(r[side+'_FIRST_SCORER']):raise ValueError('Scoring athlete identity disagrees with player statistics')
    for df,cols in [(ftb,['HOME_FIRST_SCORER','AWAY_FIRST_SCORER']),(line,[f'STARTER_{i}' for i in range(1,6)])]:
        if any(not text(v) for c in cols for v in df[c]):raise ValueError('Incomplete source scorer/lineup records')
    ftb=ftb.sort_values(['GAME_DATE','GAME_ID']);line=line.sort_values(['GAME_DATE','GAME_ID'])
    ids=Identities(roster,ppg,line);players={};events=[];team_fixtures=defaultdict(set);phase_fixtures=defaultdict(lambda:defaultdict(set));teams=defaultdict(lambda:{'games':0,'firstPointWins':0,'ties':0})
    def ensure(k,name,pos=''):
        if k not in players:players[k]={'name':name,'team':'','position':pos,'ftbMade':0,'teamGames':None,'firstBasketRate':None,'denominatorType':'team-games-union','shots':{s:0 for s in SHOTS},'unknownShots':0,'ftbByTeam':{},'ftbByPhase':{},'ppg':None,'gp':None,'threePm':None,'threePa':None,'starterCount':0,'starterRank':None,'lineupDate':'','identityResolved':k in ids.names,'provenance':{}}
        if pos:players[k]['position']=pos
        return players[k]
    def elapsed(clock,period):
        p=text(clock).split(':')
        return ((number(period) or 1)-1)*720+720-(float(p[0])*60+float(p[1])) if len(p)==2 else None
    for r in ftb.to_dict('records'):
        fixture=f"{r['GAME_DATE']}:{r['AWAY_TEAM']}:{r['HOME_TEAM']}";times=[]
        for side,other in [('HOME','AWAY'),('AWAY','HOME')]:
            team,opp=text(r[f'{side}_TEAM']),text(r[f'{other}_TEAM']);team_fixtures[team].add(fixture);phase_fixtures[r['GAME_TYPE']][team].add(fixture);teams[team]['games']+=1
            k,n,pos,resolved=ids.resolve(text(r[f'{side}_FIRST_SCORER']),team,r['GAME_DATE']);p=ensure(k,n,pos)
            p['ftbMade']+=1;p['team']=team;p['historicalTeamDate']=r['GAME_DATE']
            detail=p['ftbByTeam'].setdefault(team,{'ftbMade':0,'teamGames':None,'firstBasketRate':None,'shots':{s:0 for s in SHOTS},'positions':{s:0 for s in (*POSITIONS,'unknown')}});detail['ftbMade']+=1
            phase=p['ftbByPhase'].setdefault(r['GAME_TYPE'],{'ftbMade':0,'teamGames':None,'firstBasketRate':None,'historicalTeams':[]});phase['ftbMade']+=1
            if team not in phase['historicalTeams']:phase['historicalTeams'].append(team)
            detail['positions'][pos if pos in POSITIONS else 'unknown']+=1
            shot=classify_shot(r.get(f'{side}_SHOT_DESC'),r.get(f'{side}_POINTS'))
            if shot:p['shots'][shot]+=1;detail['shots'][shot]+=1
            else:p['unknownShots']+=1
            times.append(elapsed(r.get(f'{side}_TIME'),r.get(f'{side}_PERIOD')))
            events.append({'gameId':text(r['GAME_ID']),'eventId':text(r['ESPN_EVENT_ID']),'gameDate':r['GAME_DATE'],'gameType':r['GAME_TYPE'],'scoringTeam':team,'defendingTeam':opp,'scoringPlayer':n,'sourcePlayerId':text(r.get(f'{side}_PLAYER_ID')),'playerKey':k,'pos':pos,'shotType':shot,'points':int(r[f'{side}_POINTS']),'clock':text(r[f'{side}_TIME']),'period':int(r[f'{side}_PERIOD']),'sequence':int(r[f'{side}_SEQUENCE']),'identityResolved':resolved})
        if None not in times and times[0]!=times[1]:teams[text(r['HOME_TEAM'] if times[0]<times[1] else r['AWAY_TEAM'])]['firstPointWins']+=1
        elif None not in times:
            for side in ['HOME','AWAY']:teams[text(r[f'{side}_TEAM'])]['ties']+=1
    for p in players.values():
        games=set()
        for team,d in p['ftbByTeam'].items():
            games.update(team_fixtures[team]);d['teamGames']=len(team_fixtures[team]);d['firstBasketRate']=round(d['ftbMade']/d['teamGames'],6)
        p['teamGames']=len(games);p['firstBasketRate']=round(p['ftbMade']/p['teamGames'],6);p['historicalTeams']=sorted(p['ftbByTeam']);p['provenance']['ftb']='first-basket-workbook'
        for phase,d in p['ftbByPhase'].items():
            phase_games=set().union(*(phase_fixtures[phase][t] for t in d['historicalTeams']))
            d['teamGames']=len(phase_games);d['firstBasketRate']=round(d['ftbMade']/d['teamGames'],6)
    for r in ppg.to_dict('records'):
        k,n,pos,_=ids.resolve(text(r['FULL_NAME']),text(r['TEAM']));p=ensure(k,n,pos)
        for field,column in [('ppg','PPG'),('gp','GP'),('threePm','FG3M'),('threePa','FG3A')]:p[field]=number(r.get(column))
        p['sourcePlayerId']=text(r.get('PLAYER_ID'));p['ppgScope']=text(r.get('STAT_SCOPE'))
        p['ppgAsOfDate']=str(pd.to_datetime(r['AS_OF_DATE']).date());p['minutesSampleGames']=number(r.get('MIN_GP'));p['plusMinusSampleGames']=number(r.get('PLUS_MINUS_GP'))
        p['ppgByPhase']={phase:{'gp':number(r.get('GP_'+phase.upper().replace('-','_'))),'ppg':number(r.get('PPG_'+phase.upper().replace('-','_')))} for phase in EXPECTED_PHASE_COUNTS}
        p['ppgTeam']=text(r['TEAM']);p['provenance']['ppg']='ppg-workbook'
        p['team']=p['ppgTeam'];p['teamAssignmentDate']=p['ppgAsOfDate'];p['provenance']['team']='latest-observed-box-score'
    latest_keys={(r['GAME_DATE'],text(r['TEAM'])) for r in line.groupby('TEAM',sort=False).tail(1).to_dict('records')}
    for r in line.to_dict('records'):
        team,date=text(r['TEAM']),r['GAME_DATE']
        for rank in range(1,6):
            k,n,pos,_=ids.resolve(text(r[f'STARTER_{rank}']),team,date);p=ensure(k,n,pos);p['starterCount']+=1
            if date>=p.get('teamAssignmentDate',''):p['team']=team;p['teamAssignmentDate']=date;p['provenance']['team']='latest-observed-lineup'
            if (date,team) in latest_keys and date>=p['lineupDate']:
                p['starterRank']=rank;p['lineupDate']=date;p['lastLineupTeam']=team;p['starterConfirmed']=False;p['provenance']['lineup']='lineups-workbook'
    counts=defaultdict(lambda:{s:0 for s in (*POSITIONS,'unknown')})
    for e in events:counts[e['defendingTeam']][e['pos'] if e['pos'] in POSITIONS else 'unknown']+=1
    positions={t:{**{s:round(c[s]/sum(c.values())*100,2) for s in POSITIONS},'unknownPct':round(c['unknown']/sum(c.values())*100,2),'totalGames':sum(c.values())} for t,c in counts.items()}
    team_stats={t:{**s,'firstFGPct':None,'firstPointPctFromDistinctClocks':round(s['firstPointWins']/s['games']*100,2),'firstPointSource':'clock-only-with-unresolved-ties','firstPointPct':None,'tipPct':None,'tipSource':'unavailable','source':'first-basket-workbook'} for t,s in teams.items()}
    total=sum(p['ftbMade'] for p in players.values())
    if total!=len(ftb)*2 or any(sum(p['shots'].values())+p['unknownShots']!=p['ftbMade'] for p in players.values()):raise ValueError('First-basket reconciliation failed')
    issues=list({json.dumps(i,sort_keys=True):i for i in ids.issues}.values())
    meta={'schemaVersion':4,'datasetId':DATASET_ID,'scoringDefinition':SCORING_DEFINITION,'generatedAt':datetime.now(timezone.utc).isoformat(),'season':'2025-26','asOfDate':str(ftb.GAME_DATE.max()),'startDate':str(ftb.GAME_DATE.min()),'totalGames':len(ftb),'totalEvents':total,'phaseCounts':phase_counts,'coverageComplete':True,'gameIdProvider':'ESPN','ppgScope':'all-included-games','denominatorType':'team-games-union','counts':{'players':len(players),'ftbPlayers':sum(p['ftbMade']>0 for p in players.values()),'ppg':len(ppg),'lineupRows':len(line)},'validation':{'reconciled':True,'freeThrowEvents':sum(e['shotType']=='ft' for e in events),'identityIssues':sum(i['kind'] in ['unresolved_name','ambiguous_name'] for i in issues),'ignoredRosterAliases':sum(i['kind']=='ignored_roster_alias' for i in issues),'unknownPositionEvents':sum(not e['pos'] for e in events)},'sources':{label:{'file':Path(path).name,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()} for label,path in [('ftb',ftb_path),('lineups',lineup_path),('ppg',ppg_path),('roster',roster_path)]}}
    for p in players.values():p['asOfDate']=meta['asOfDate'];p['schemaVersion']=4;p['datasetId']=DATASET_ID;p['scoringDefinition']=SCORING_DEFINITION
    from official_stats import load,apply_canonical
    apply_canonical(players,meta,load())
    merged={'meta':meta,'players':players,'source':'canonical-season-workbook-and-NBA-gamebooks','schemaVersion':4}
    pipeline={'meta':meta,'schemaVersion':4,'playerFtb':{p['name']:p for p in players.values() if p['ftbMade']>0},'teamStats':team_stats,'positionData':positions,'savedAt':meta['generatedAt'],'source':'canonical-season-workbook','gamesProcessed':len(ftb)}
    return merged,pipeline,{'meta':meta,'issues':issues,'events':events}
def write_json(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(payload,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8');temp.replace(path)
