"""Download a schedule-scoped NBA official gamebook archive and build a local index.

Uses only standard-library modules plus pypdf. Does not modify application data.
Run with the Codex bundled Python, or install pypdf in your own environment.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import shutil
import sqlite3
import time
import unicodedata
from collections import Counter,defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from pypdf import PdfReader
import gamebook_text

ROOT=Path(__file__).resolve().parent.parent
STAT_COLUMNS=['fgm','fga','three_pm','three_pa','ftm','fta','oreb','dreb','reb','ast','pf','stl','tov','blk','plus_minus','pts']
# Official final box omits II in this one game. ESPN's same-game box confirms
# jersey 30 and the identical 0 PTS, 0-1 FG, 1 REB, -4 line for athlete 4397450.
IDENTITY_OVERRIDES={('401810690','CLE','Darius Brown','30'):'4397450'}
TEAM_NAMES={
 'ATL':['Atlanta Hawks'],'BOS':['Boston Celtics'],'BKN':['Brooklyn Nets'],'CHA':['Charlotte Hornets'],
 'CHI':['Chicago Bulls'],'CLE':['Cleveland Cavaliers'],'DAL':['Dallas Mavericks'],'DEN':['Denver Nuggets'],
 'DET':['Detroit Pistons'],'GSW':['Golden State Warriors'],'HOU':['Houston Rockets'],'IND':['Indiana Pacers'],
 'LAC':['LA Clippers','Los Angeles Clippers'],'LAL':['Los Angeles Lakers','LA Lakers'],'MEM':['Memphis Grizzlies'],
 'MIA':['Miami Heat'],'MIL':['Milwaukee Bucks'],'MIN':['Minnesota Timberwolves'],'NOP':['New Orleans Pelicans'],
 'NYK':['New York Knicks'],'OKC':['Oklahoma City Thunder'],'ORL':['Orlando Magic'],'PHI':['Philadelphia 76ers'],
 'PHX':['Phoenix Suns'],'POR':['Portland Trail Blazers'],'SAC':['Sacramento Kings'],'SAS':['San Antonio Spurs'],
 'TOR':['Toronto Raptors'],'UTA':['Utah Jazz'],'WAS':['Washington Wizards']}

def now():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,data):
    tmp=path.with_suffix(path.suffix+'.part')
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    tmp.replace(path)
def norm(value):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().lower())

def printed_totals(text,g):
    """Read each printed NBA team total, independently of ESPN's final score."""
    totals={};team=None
    for line in text.splitlines():
        clean=line.strip()
        if clean.startswith('VISITOR:'):team=g['away']
        elif clean.startswith('HOME:'):team=g['home']
        else:
            for side in (g['away'],g['home']):
                if '(' in clean and any(norm(clean).startswith(norm(n)) for n in TEAM_NAMES[side]):team=side
        match=re.fullmatch(r'\s*(\d{3}:\d{2})\s+((?:-?\d+\s+){15}-?\d+)\s*',line)
        if match and team:
            totals[team]=dict(zip(STAT_COLUMNS,map(int,match[2].split())))
    if set(totals)!={g['home'],g['away']}:raise ValueError('Both printed NBA final team totals are required')
    return totals

def parse_final_box(text,g,identities):
    rows=[];issues=[];team=None;headers={};played_by_team=Counter()
    for line in text.splitlines():
        clean=line.strip()
        if clean.startswith('VISITOR:'):
            team=g['away'];headers[team]=clean
        elif clean.startswith('HOME:'):
            team=g['home'];headers[team]=clean
        else:
            # Neutral-site Cup reports print team names without VISITOR/HOME prefixes.
            for side in [g['away'],g['home']]:
                if '(' in clean and any(norm(clean).startswith(norm(name)) for name in TEAM_NAMES[side]):
                    team=side;headers[side]=clean;break
        if team is None:continue
        match=re.match(r'^\s*(\d{1,2})\s+(.+?)\s{2,}(.+?)\s*$',line)
        if not match:continue
        jersey,name,rest=match.groups()
        # NBA final-box player rows have a jersey, name, optional role, then minutes or DNP designation.
        minute=re.search(r'\b(\d{1,2}):(\d{2})\b',rest)
        if minute:
            try:values=[int(v) for v in rest[minute.end():].split()]
            except ValueError:
                issues.append(dict(kind='Unparsed stat row',team=team,line=clean));continue
            if len(values)!=16:
                issues.append(dict(kind='Unexpected stat column count',team=team,line=clean));continue
            stats=dict(zip(STAT_COLUMNS,values))
            before=rest[:minute.start()].strip()
            if before not in ['','F','G','C','PG','SG','SF','PF']:
                issues.append(dict(kind='Unexpected position column',team=team,line=clean));continue
            seconds=60*int(minute[1])+int(minute[2])
            status='played';played_by_team[team]+=1
            # The official scorer's report lists the five starters with position labels.
            starter=bool(before)
        elif re.search(r'\b(DNP|DND|NWT)\b',rest):
            stats={k:None for k in STAT_COLUMNS};seconds=None;before='';starter=False;status=rest
        else:continue
        candidates=[p for p in g['teams'][team]['players'] if norm(p['name'])==norm(name)]
        if len(candidates)==1:pid=candidates[0]['id'];identity_method='exact normalized name in same-game team roster'
        elif (g['id'],team,name,jersey) in IDENTITY_OVERRIDES:
            pid=IDENTITY_OVERRIDES[g['id'],team,name,jersey]
            assert any(str(p['id'])==pid and p['name']=='Darius Brown II' for p in g['teams'][team]['players'])
            assert stats['pts']==0 and stats['fgm']==0 and stats['fga']==1 and stats['reb']==1 and stats['plus_minus']==-4
            identity_method='verified same-game suffix crosswalk: jersey and full box agree; https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401810690'
        elif len(identities.get(norm(name),[]))==1:pid=next(iter(identities[norm(name)]));identity_method='unique exact normalized name in stored season identity map'
        else:pid=None;identity_method='unresolved; NBA official name retained'
        row=dict(team=team,nba_name=name,jersey=jersey,position=before or None,starter=starter,status=status,
                 played=status=='played',minutes_seconds=seconds,espn_player_id=pid,identity_method=identity_method,**stats)
        if row['played']:
            if not (0<=stats['three_pm']<=stats['fgm']<=stats['fga'] and stats['three_pm']<=stats['three_pa']<=stats['fga'] and 0<=stats['ftm']<=stats['fta']):issues.append(dict(kind='Shooting inequality',team=team,name=name))
            if 2*stats['fgm']+stats['three_pm']+stats['ftm']!=stats['pts']:issues.append(dict(kind='Points equation',team=team,name=name))
            if stats['oreb']+stats['dreb']!=stats['reb']:issues.append(dict(kind='Rebound equation',team=team,name=name))
        rows.append(row)
    for team in [g['away'],g['home']]:
        header=headers.get(team,'')
        if not any(norm(name) in norm(header) for name in TEAM_NAMES[team]):issues.append(dict(kind='Team header mismatch',team=team,header=header))
        rs=[r for r in rows if r['team']==team and r['played']]
        if not 5<=len(rs)<=18:issues.append(dict(kind='Unexpected played roster size',team=team,rows=len(rs)))
        if sum(r['pts'] for r in rs)!=g['teams'][team]['points']:issues.append(dict(kind='Final score mismatch',team=team,officialPlayerSum=sum(r['pts'] for r in rs),storedScore=g['teams'][team]['points']))
        if sum(r['starter'] for r in rs)!=5:issues.append(dict(kind='Starter count mismatch',team=team,count=sum(r['starter'] for r in rs)))
    if len({(r['team'],r['jersey']) for r in rows})!=len(rows):issues.append(dict(kind='Duplicate jersey rows'))
    return rows,issues

def collect_one(g,out,seed,identities,force=False):
    ymd=g['date'].replace('-','');filename=f"{ymd}_{g['away']}{g['home']}_book.pdf"
    url=f'https://statsdmz.nba.com/pdfs/{ymd}/{filename}'
    pdf=out/'pdf'/g['date']/filename;meta=out/'records'/(g['id']+'.json')
    base=dict(espn_game_id=g['id'],season=g.get('season',out.name),phase=g['phase'],game_date=g['date'],away=g['away'],home=g['home'],
              away_score=g['teams'][g['away']]['points'],home_score=g['teams'][g['home']]['points'],source_url=url,pdf_path=str(pdf.relative_to(out)).replace('\\','/'))
    existing={}
    if meta.exists() and pdf.exists():
        existing=read(meta)
        if existing.get('sha256')==hashlib.sha256(pdf.read_bytes()).hexdigest():
            versions=out/'source_versions';versions.mkdir(exist_ok=True)
            archived=versions/(existing['sha256']+'.pdf')
            if not archived.exists():shutil.copyfile(pdf,archived)
            if not (versions/(existing['sha256']+'.json')).exists():save(versions/(existing['sha256']+'.json'),existing)
        if not force and existing.get('team_totals') and existing.get('status')=='downloaded' and existing.get('verification_status')=='verified' and all(r.get('espn_player_id') for r in existing.get('player_rows',[]) if r['played']) and hashlib.sha256(pdf.read_bytes()).hexdigest()==existing['sha256']:return existing
    try:
        pdf.parent.mkdir(parents=True,exist_ok=True)
        origin='existing library'
        if force or not pdf.exists():
            cached=seed/filename
            if cached.exists():
                shutil.copyfile(cached,pdf);origin='reused prior NBA audit capture'
            else:
                origin='downloaded from NBA'
                for attempt in range(3):
                    try:
                        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/pdf'}),timeout=25) as response:
                            payload=response.read()
                        if not payload.startswith(b'%PDF'):raise ValueError('Response is not PDF')
                        temp=pdf.with_suffix('.pdf.part');temp.write_bytes(payload);temp.replace(pdf);break
                    except HTTPError as e:
                        if e.code in [403,404] or attempt==2:raise
                        time.sleep(1+attempt*2)
                    except Exception:
                        if attempt==2:raise
                        time.sleep(1+attempt*2)
                time.sleep(.1)
        payload=pdf.read_bytes()
        if not payload.startswith(b'%PDF'):raise ValueError('Saved response is not PDF')
        versions=out/'source_versions';versions.mkdir(exist_ok=True)
        archived=versions/(hashlib.sha256(payload).hexdigest()+'.pdf')
        if not archived.exists():archived.write_bytes(payload)
        reader=PdfReader(pdf)
        extraction=gamebook_text.extract(payload,0,reader.pages[0].extract_text(extraction_mode='layout'),kind='final-box')
        text=extraction['text']
        if 'FINAL BOX' not in text:raise ValueError('First page is not a final box score')
        expected=date.fromisoformat(g['date']).strftime('%B %d, %Y').replace(' 0',' ')
        if expected not in text:raise ValueError('Official report date does not match fixture')
        totals=printed_totals(text,g)
        authoritative={**g,'teams':{t:{**b,'points':totals[t]['pts']} for t,b in g['teams'].items()}}
        box,issues=parse_final_box(text,authoritative,identities)
        for team,total in totals.items():
            rows=[r for r in box if r['team']==team and r['played']]
            for key in STAT_COLUMNS:
                if key!='plus_minus' and sum(r[key] for r in rows)!=total[key]:
                    issues.append(dict(kind='Printed NBA team total mismatch',team=team,field=key))
            ids=[r['espn_player_id'] for r in rows]
            if any(not pid for pid in ids) or len(set(ids))!=len(ids):issues.append(dict(kind='Unresolved or duplicate played identity',team=team))
        textpath=out/'text'/'final_boxes'/(filename[:-4]+'.txt');textpath.parent.mkdir(parents=True,exist_ok=True);textpath.write_text(text,encoding='utf-8')
        result=dict(**base,status='downloaded',verification_status='verified' if not issues else 'needs-review',captured_at=existing.get('captured_at') if existing.get('sha256')==hashlib.sha256(payload).hexdigest() and existing.get('captured_at') else now(),checked_at=now(),capture_origin=origin,
                    sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload),pages=len(reader.pages),final_box_text_path=str(textpath.relative_to(out)).replace('\\','/'),issues=issues,player_rows=box,
                    team_totals=totals,text_extraction={k:v for k,v in extraction.items() if k!='text'},score_differences=[dict(team=t,espn=g['teams'][t]['points'],nba=totals[t]['pts']) for t in totals if g['teams'][t]['points']!=totals[t]['pts']])
        result.update(away_score=totals[g['away']]['pts'],home_score=totals[g['home']]['pts'])
    except Exception as e:result=dict(**base,status='unavailable',verification_status='unavailable',checked_at=now(),error=type(e).__name__+': '+str(e))
    save(meta,result);return result

def build_database(out,results):
    db=sqlite3.connect(out/'gamebooks.sqlite')
    db.executescript('''
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS games(espn_game_id TEXT PRIMARY KEY,season TEXT NOT NULL,phase TEXT NOT NULL,game_date TEXT NOT NULL,away TEXT NOT NULL,home TEXT NOT NULL,away_score INTEGER,home_score INTEGER);
        CREATE TABLE IF NOT EXISTS documents(espn_game_id TEXT PRIMARY KEY REFERENCES games(espn_game_id),source_url TEXT NOT NULL,pdf_path TEXT NOT NULL,sha256 TEXT,bytes INTEGER,pages INTEGER,captured_at TEXT,status TEXT NOT NULL,verification_status TEXT NOT NULL,issues_json TEXT NOT NULL,final_box_text_path TEXT);
        CREATE TABLE IF NOT EXISTS player_game_stats(espn_game_id TEXT NOT NULL REFERENCES games(espn_game_id),team TEXT NOT NULL,nba_name TEXT NOT NULL,jersey TEXT NOT NULL,espn_player_id TEXT,identity_method TEXT NOT NULL,position TEXT,starter INTEGER NOT NULL,played INTEGER NOT NULL,status TEXT NOT NULL,minutes_seconds INTEGER,fgm INTEGER,fga INTEGER,three_pm INTEGER,three_pa INTEGER,ftm INTEGER,fta INTEGER,oreb INTEGER,dreb INTEGER,reb INTEGER,ast INTEGER,pf INTEGER,stl INTEGER,tov INTEGER,blk INTEGER,plus_minus INTEGER,pts INTEGER,PRIMARY KEY(espn_game_id,team,jersey));
        CREATE INDEX IF NOT EXISTS games_phase_date ON games(phase,game_date);
        CREATE INDEX IF NOT EXISTS player_games_identity ON player_game_stats(espn_player_id,espn_game_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS gamebook_search USING fts5(espn_game_id UNINDEXED,game_date,teams,final_box);
        CREATE VIEW IF NOT EXISTS season_player_totals AS SELECT g.season,g.phase,CASE WHEN p.espn_player_id IS NOT NULL THEN 'espn:'||p.espn_player_id ELSE 'unresolved:'||p.team||':'||p.nba_name END AS player_key,p.espn_player_id,MAX(p.nba_name) AS nba_name,COUNT(*) AS gp,SUM(p.starter) AS starts,SUM(p.minutes_seconds) AS minutes_seconds,SUM(p.pts) AS pts,SUM(p.fgm) AS fgm,SUM(p.fga) AS fga,SUM(p.three_pm) AS three_pm,SUM(p.three_pa) AS three_pa,SUM(p.ftm) AS ftm,SUM(p.fta) AS fta,SUM(p.oreb) AS oreb,SUM(p.dreb) AS dreb,SUM(p.reb) AS reb,SUM(p.ast) AS ast,SUM(p.stl) AS stl,SUM(p.blk) AS blk,SUM(p.tov) AS tov,SUM(p.pf) AS pf,SUM(p.plus_minus) AS plus_minus,1.0*SUM(p.pts)/COUNT(*) AS ppg,1.0*SUM(p.minutes_seconds)/60/COUNT(*) AS mpg,1.0*SUM(p.fgm)/NULLIF(SUM(p.fga),0) AS fg_pct,1.0*SUM(p.three_pm)/NULLIF(SUM(p.three_pa),0) AS three_pct,1.0*SUM(p.ftm)/NULLIF(SUM(p.fta),0) AS ft_pct,1.0*SUM(p.pts)/NULLIF(2*(SUM(p.fga)+0.44*SUM(p.fta)),0) AS ts_pct FROM player_game_stats p JOIN games g USING(espn_game_id) JOIN documents d USING(espn_game_id) WHERE p.played=1 AND d.verification_status='verified' GROUP BY g.season,g.phase,player_key;
    ''')
    columns=['espn_game_id','team','nba_name','jersey','espn_player_id','identity_method','position','starter','played','status','minutes_seconds']+STAT_COLUMNS
    with db:
        db.execute('DELETE FROM gamebook_search')
        for r in results:
            db.execute('INSERT OR REPLACE INTO games VALUES(?,?,?,?,?,?,?,?)',tuple(r[k] for k in ['espn_game_id','season','phase','game_date','away','home','away_score','home_score']))
            db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r['espn_game_id'],r['source_url'],r['pdf_path'],r.get('sha256'),r.get('bytes'),r.get('pages'),r.get('captured_at'),r['status'],r['verification_status'],json.dumps(r.get('issues',[])),r.get('final_box_text_path')))
            db.execute('DELETE FROM player_game_stats WHERE espn_game_id=?',(r['espn_game_id'],))
            for row in r.get('player_rows',[]):
                values=dict(row,espn_game_id=r['espn_game_id'])
                db.execute('INSERT INTO player_game_stats ('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',tuple(values[k] for k in columns))
            if r.get('final_box_text_path'):
                db.execute('INSERT INTO gamebook_search VALUES(?,?,?,?)',(r['espn_game_id'],r['game_date'],r['away']+' '+r['home'],(out/r['final_box_text_path']).read_text(encoding='utf-8')))
    checks=dict(integrity_check=db.execute('PRAGMA integrity_check').fetchone()[0],foreign_key_issues=db.execute('PRAGMA foreign_key_check').fetchall(),games=db.execute('SELECT COUNT(*) FROM games').fetchone()[0],documents=db.execute("SELECT COUNT(*) FROM documents WHERE status='downloaded'").fetchone()[0],player_rows=db.execute('SELECT COUNT(*) FROM player_game_stats').fetchone()[0],played_rows=db.execute('SELECT COUNT(*) FROM player_game_stats WHERE played=1').fetchone()[0],unresolved_played_identities=db.execute('SELECT COUNT(*) FROM player_game_stats WHERE played=1 AND espn_player_id IS NULL').fetchone()[0],fts_documents=db.execute('SELECT COUNT(*) FROM gamebook_search').fetchone()[0])
    db.close();return checks

