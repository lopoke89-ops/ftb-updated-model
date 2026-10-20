"""Versioned official full-game ledger. Separate from frozen boxes/opening/models.

Run --library explicitly. SQLite contains immutable source bytes, printed pages,
interpreted actions, appearance identities, discrepancies and active pointers.
Only independently reconciled components may supply event-derived context.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import sqlite3
import time
import unicodedata
import pbp_identity
from official_gamebooks import TEAM_NAMES
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'full-game-pbp-v10'
CODE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
IDENTITY_RESOLVER_HASH = hashlib.sha256(Path(pbp_identity.__file__).read_bytes()).hexdigest()
SCHEMA = 1
CLOCK = re.compile(r'^(\d{1,2}:\d{2}(?:\.\d+)?|:\d{2}(?:\.\d+)?)\s+')
STATS = ['fgm','fga','three_pm','three_pa','ftm','fta','pts','ast','stl','blk','tov','oreb','dreb','reb']

def packed(x): return json.dumps(x, ensure_ascii=False, separators=(',', ':'), sort_keys=True, allow_nan=False)
def sha(x): return hashlib.sha256(x).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def norm(s): return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def aliases(name):
    words=name.replace('.','').split(); first=words[0]
    tails={''.join(words[1:]),words[-1]}
    if words[-1].lower() in ('jr','ii','iii','iv'): tails.update({''.join(words[1:-1]),words[-2]})
    return {norm(first[:i]+tail) for tail in tails for i in range(1,len(first)+1)}
def save(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.stage'); tmp.write_text(packed(data),encoding='utf-8'); tmp.replace(path)

def pages_from_pdf(raw, cached=None):
    import pypdfium2 as pdfium
    from pypdf import PdfReader
    indexes=[]; boxes=[]
    with pdfium.PdfDocument(raw) as doc:
        for i in range(len(doc)):
            page=doc[i]; tp=page.get_textpage(); text=tp.get_text_range(); tp.close(); page.close()
            if 'OFFICIAL PLAY-BY-PLAY' in text[:600]: indexes.append(i)
            if re.search(r'\d+(?:st|nd|rd|th) (?:QUARTER|OT|OVERTIME) ONLY',text[:300]): boxes.append({'page':i+1,'text':text,'box':True})
    if cached: return boxes+[p for p in cached if not p.get('box')]
    reader=PdfReader(__import__('io').BytesIO(raw))
    return boxes+[{'page':i+1,'text':reader.pages[i].extract_text(extraction_mode='layout')} for i in indexes]

def period_number(text):
    m=re.search(r'(\d+)(?:st|nd|rd|th) (QUARTER|OVERTIME|OT)',text,re.I)
    if m: return int(m[1])+(4 if m[2].upper() in ('OVERTIME','OT') else 0)
    if re.search(r'\bOVERTIME\b',text): return 5
    return None

def parse_pages(pages,game,record):
    alias=defaultdict(set); people={}
    for p in record['player_rows']:
        pid=str(p['espn_player_id']) if p.get('espn_player_id') else None
        if not pid or not p['played']: continue
        people[(p['team'],pid)]=p
        for key in aliases(p['nba_name']): alias[(p['team'],key)].add(pid)
    def identity(team,token):
        ids=sorted(alias.get((team,norm(token)),set()))
        return {'token':token,'id':ids[0] if len(ids)==1 else None,'candidates':ids,'method':'unique same-game team abbreviation' if len(ids)==1 else 'unresolved same-game abbreviation'}
    events=[]; issues=[]; periods={}; score=[0,0]; last_miss=None
    for page in pages:
        if page.get('box'): continue
        text=page['text']; period=period_number(text)
        if not period: issues.append({'kind':'unrecognized period','page':page['page']}); continue
        period_info=periods.setdefault(period,{'pages':[],'ended':False,'startScore':score[:]})
        period_info['pages'].append(page['page'])
        lines=text.splitlines(); header=next((s for s in lines if re.match(r'^Time\s+',s)),None)
        if not header or 'Score' not in header or 'Lead' not in header:
            issues.append({'kind':'missing column header','page':page['page']}); continue
        middle=header.index('Score'); lead_end=header.index('Lead')+4
        right_start=lead_end+re.search(r'\S',header[lead_end:]).start()
        team_labels={game['home']:header[4:middle].strip(),game['away']:header[right_start:].strip()}
        for n,line in enumerate(lines):
            if 'FIELD GOALS' in line or 'FREE THROWS' in line:
                pairs=re.findall(r'(\d+)/(\d+) FOR',line)
                if len(pairs)==2: period_info['fieldGoals' if 'FIELD GOALS' in line else 'freeThrows']=[list(map(int,pair)) for pair in pairs]

            if 'Starters:' in line:
                events.append({'sequence':len(events)+1,'period':period,'clock':None,'team':None,'type':'period_lineup','text':line.strip(),'raw':line,'page':page['page'],'line':n+1,'lineEnd':n+1,'participants':{},'points':0,'score':score[:]})
            if re.search(r'End of \d+(?:st|nd|rd|th) (?:QUARTER|OVERTIME|OT)',line):
                ending=re.search(r'\((\d+)-(\d+)\)',line)
                period_info.update(ended=True,endScore=score[:])
                if ending and [int(ending[1]),int(ending[2])]!=score:
                    issues.append({'kind':'period score mismatch','page':page['page'],'line':n+1,'observed':score[:],'expected':[int(ending[1]),int(ending[2])]})
                events.append({'sequence':len(events)+1,'period':period,'clock':':00.0','team':None,'type':'period_boundary','text':line.strip(),'raw':line,'page':page['page'],'line':n+1,'lineEnd':n+1,'participants':{},'points':0,'score':score[:]})
                last_miss=None
            m=CLOCK.match(line)
            if not m: continue
            clock=m[1]; left=line[m.end():middle].strip(); center=line[middle:right_start]; right=line[right_start:].strip(); end=n+1
            for continuation_line,cont in enumerate(lines[n+1:],n+2):
                if CLOCK.match(cont) or 'Copyright' in cont or 'End of ' in cont or 'SCORE:' in cont: break
                if re.search(r'Non-Unsportsmanlike|Technical Foul|Defensive Three Seconds',cont,re.I) and not re.search(r'Non-Unsportsmanlike|Technical Foul|Defensive Three Seconds',left+' '+right,re.I): break
                if not cont.strip(): continue
                start=len(cont)-len(cont.lstrip())
                if 8<=start<middle: left+=' '+cont[:middle].strip(); end=continuation_line
                elif start>=right_start: right+=' '+cont[right_start:].strip(); end=continuation_line
            sm=re.search(r'(?<!\d)(\d+)-(\d+)(?!\d)',center)
            new=[int(sm[1]),int(sm[2])] if sm else score[:]
            delta=[new[i]-score[i] for i in (0,1)]
            if any(d<0 or d>3 for d in delta) or all(delta):
                issues.append({'kind':'score correction or invalid progression','page':page['page'],'line':n+1,'before':score[:],'after':new})
            if 'End of ' in line:
                period_info.update(ended=True,endScore=new[:]); last_miss=None
            # Period-start possession snapshots can already include the following technical FT.
            if 'Possession:' in line and any(delta):
                technical=[]
                for future in lines[n+1:]:
                    fm_clock=CLOCK.match(future)
                    if fm_clock and fm_clock[1]!=clock: break
                    if fm_clock and 'Technical Free Throw' in future and 'MISS ' not in future:
                        for side in (0,1):
                            segment=future[fm_clock.end():middle] if side==0 else future[right_start:]
                            if 'Technical Free Throw' in segment and delta[side]==1 and delta[1-side]==0: technical.append(side)
                if len(technical)==1:
                    events.append({'sequence':len(events)+1,'period':period,'clock':clock,'team':None,'type':'period_score_snapshot','text':line[m.end():].strip(),'raw':line,'page':page['page'],'line':n+1,'lineEnd':end,'participants':{},'points':0,'score':new[:],'effectiveScore':score[:],'interpretation':'printed period-start snapshot precredits a subsequent same-clock technical free throw'})
                    continue
            if 'Double Technical' in line:
                tokens=re.search(r'Double Technical\s*-\s*(.*?)\s*\(',line)
                participants={}
                if tokens:
                    for i,token in enumerate(tokens[1].split(',')):
                        matches=[(t,identity(t,token.strip())) for t in (game['home'],game['away']) if alias.get((t,norm(token.strip())))]
                        if len(matches)==1: participants['fouler' if i==0 else 'otherFouler']={**matches[0][1],'team':matches[0][0]}
                events.append({'sequence':len(events)+1,'period':period,'clock':clock,'team':None,'type':'foul','text':line[m.end():].strip(),'raw':line,'page':page['page'],'line':n+1,'lineEnd':end,'participants':participants,'points':0,'score':new[:],'foulMapping':'double technical; separate recipients; no pooled personal-foul credit'})
                score=new;continue
            # Reviews often cross the score/lead columns. Preserve one whole row with no invented player.
            if re.search(r"Coach's Challenge|Instant Replay|REPLAY|Replay|Overturned|overturned|Call Confirmed|Ruling",line):
                events.append({'sequence':len(events)+1,'period':period,'clock':clock,'team':None,'type':'review_correction','text':line[m.end():].strip(),'raw':line,'page':page['page'],'line':n+1,'lineEnd':end,'participants':{},'points':0,'score':new[:]})
                if any(delta): issues.append({'kind':'review score adjustment','page':page['page'],'line':n+1,'before':score[:],'after':new})
                score=new; continue
            # Centered administrative rows must remain whole, rather than becoming fake team actions.
            if re.search(r'Start of Period|End of |JUMP BALL',line):
                events.append({'sequence':len(events)+1,'period':period,'clock':clock,'team':None,'type':'jump_ball' if 'JUMP BALL' in line else 'period_boundary','text':line[m.end():].strip(),'raw':line,'page':page['page'],'line':n+1,'lineEnd':end,'participants':{},'points':0,'score':new[:]})
                score=new; continue
            for side,description in enumerate((left,right)):
                description=re.sub(r'-\s+', '-', description.strip())
                if not description: continue
                team=(game['home'],game['away'])[side]
                e={'sequence':len(events)+1,'rowId':f"{period}:{page['page']}:{n+1}",'period':period,'clock':clock,'team':team,'text':description,'raw':line,'page':page['page'],'line':n+1,'lineEnd':end,'score':new[:],'printedScore':bool(sm),'points':delta[side],'participants':{},'type':'administrative','result':None,'shotValue':None,'distanceFeet':None}
                token=re.match(r'^(?:MISS\s+)?(\S+)',description)[1]
                actor=identity(team,token)
                ft='Free Throw' in description
                shot=ft or bool(re.search(r'\b(Shot|Layup|Dunk|Hook|Tip|Finger Roll|Alley Oop|Putback)\b',description,re.I))
                if re.search(r'JUMP BALL|REBOUND|TURNOVER|BLOCK|STEAL|Violation|^TIP TO|FOUL',description,re.I): shot=False
                if shot:
                    e.update(type='free_throw' if ft else 'shot',result='missed' if description.startswith('MISS ') else 'made',shotValue=1 if ft else 3 if '3PT' in description else 2)
                    e['participants']['shooter']=actor
                    dm=re.search(r"(\d+)'",description); e['distanceFeet']=int(dm[1]) if dm else None
                    fm=re.search(r'Free Throw(?: [A-Za-z]+)* (\d+) of (\d+)',description)
                    e['freeThrowAttempt']=int(fm[1]) if fm else None; e['freeThrowAwarded']=int(fm[2]) if fm else None
                    if not ft and e['result']=='made':
                        am=re.search(r'\(([^()]+)\)\s*$',description)
                        if am: e['participants']['assister']=identity(team,am[1])
                    if e['result']=='missed': last_miss=(team,period,e['sequence'])
                    elif not ft: last_miss=None
                    expected=e['shotValue'] if e['result']=='made' else 0
                    if delta[side]!=expected: issues.append({'kind':'shot score delta','sequence':e['sequence'],'page':e['page'],'observed':delta[side],'expected':expected})
                elif re.search(r'^MISS .+ HEAVE$',description,re.I):
                    e.update(type='team_attempt',result='missed',teamAttempt=True,interpretation='printed team heave; rebound context only, no individual FGA credit')
                    last_miss=(team,period,e['sequence'])
                elif 'REBOUND' in description:
                    e['type']='rebound'; e['participants']['rebounder']=actor
                    # The source's team/dead-ball records never become player credits.
                    printed_team=[t for t,label in team_labels.items() if norm(description.split(' REBOUND')[0])==norm(label)]
                    if not actor['id'] and len(printed_team)==1 and printed_team[0]!=team:
                        e.update(sourceColumnTeam=team,team=printed_team[0],interpretation='explicit printed team rebound name overrides inconsistent source column; no player credit');team=e['team']
                    e['teamRebound']=not actor['id'] and (bool(printed_team) or norm(description.split(' REBOUND')[0]) in ('team','deadball'))
                    e['reboundKind']=('offensive' if team==last_miss[0] else 'defensive') if last_miss and last_miss[1]==period else None
                    e['reboundBasis']='preceding missed attempt in this period' if e['reboundKind'] else None
                    e['linkedAttemptSequence']=last_miss[2] if last_miss else None
                    if not e['teamRebound']: last_miss=None
                elif 'BLOCK' in description: e['type']='block'; e['participants']['blocker']=actor
                elif 'STEAL' in description: e['type']='steal'; e['participants']['stealer']=actor
                elif 'TURNOVER' in description: e['type']='turnover'; e['teamTurnover']=not actor['id'] and (description.lower().startswith(team_labels[team].lower()+' ') or norm(token)=='team'); e['participants']['committer']=actor
                elif description.startswith('SUB:'):
                    e['type']='substitution'; sub=re.match(r'SUB: (\S+) FOR (\S+)',description)
                    if sub: e['participants']={'incoming':identity(team,sub[1]),'outgoing':identity(team,sub[2])}
                elif re.search(r'FOUL|Offensive \(P|Loose Ball|Technical',description,re.I):
                    e['type']='foul'
                    named=re.search(r'Foul:\s*(\S+)',description) or re.search(r'Technical Foul\s+(?!-)(\S+)',description)
                    e['participants']['fouler']=identity(team,named[1]) if named else actor
                    person=e['participants']['fouler']
                    if not person['id'] and not person['candidates'] and 'Technical' in description:
                        roster_ids=[str(p['espn_player_id']) for p in record['player_rows'] if p['team']==team and p.get('espn_player_id') and norm(person['token']) in aliases(p['nba_name'])]
                        if len(roster_ids)==1: person.update(id=roster_ids[0],method='unique same-game full roster technical recipient, including nonparticipants')
                        elif person['token']=='Non-Unsportsmanlike' and re.search(r'Too Many Players Foul|Delay Foul|Bench Foul|Excess Timeout Foul',description):
                            person.update(nonPlayer=True,entityType='team technical foul',sourceName=description,team=team,method='explicit printed team technical subtype; no individual player credit')
                        elif '.' in person['token'] and person['token'] not in ('Technical','Defensive','Double'):
                            person.update(nonPlayer=True,entityType='named non-player technical recipient',sourceName=person['token'],method='printed technical recipient absent from full same-game player roster; retained as named non-player, no player ID inferred')
                    e['foulMapping']='raw subtype retained; personal/technical/team not pooled'
                elif re.search(r'REPLAY|REVIEW|Overturn|Correction',description,re.I): e['type']='review_correction'
                if delta[side] and not shot: issues.append({'kind':'uninterpreted score adjustment','sequence':e['sequence'],'page':e['page']})
                events.append(e)
            score=new
    # Quarter-only official boxes supply period totals even where PBP footers omit them.
    quarter_players={}
    columns=['fgm','fga','three_pm','three_pa','ftm','fta','oreb','dreb','reb','ast','pf','stl','tov','blk','plus_minus','pts']
    for page in pages:
        if not page.get('box'): continue
        period=period_number(page['text']); team=None; totals={}
        for line in page['text'].splitlines():
            if line.startswith('VISITOR:'): team=game['away']
            elif line.startswith('HOME:'): team=game['home']
            else:
                for side in (game['home'],game['away']):
                    if norm(line.strip()) in {norm(name) for name in TEAM_NAMES[side]}: team=side
            player_match=re.fullmatch(r'\s*(\d{1,2})\s+(.+?)\s+(?:(?:PG|SG|SF|PF|F|G|C)\s+)?(\d{1,2}:\d{2})\s+((?:-?\d+\s+){15}-?\d+)\s*',line)
            if player_match and team:
                candidates=[pid for (t,pid),person in people.items() if t==team and person['jersey']==player_match[1] and norm(person['nba_name'])==norm(player_match[2])]
                if len(candidates)==1: quarter_players[(period,team,candidates[0])]=dict(zip(columns,map(int,player_match[4].split())))
            dnp=re.fullmatch(r'\s*(\d{1,2})\s+(.+?)\s+(?:DNP|DND|NWT)\b.*',line)
            if dnp and team:
                candidates=[pid for (t,pid),person in people.items() if t==team and person['jersey']==dnp[1] and norm(person['nba_name'])==norm(dnp[2])]
                if len(candidates)==1: quarter_players[(period,team,candidates[0])]={k:0 for k in columns}
            match=re.fullmatch(r'\s*\d{2,3}:\d{2}\s+((?:-?\d+\s+){15}-?\d+)\s*',line)
            if match and team: totals[team]=dict(zip(columns,map(int,match[1].split())))
        if set(totals)=={game['home'],game['away']} and period in periods:
            info=periods[period];info['boxPage']=page['page'];info['officialTotals']=totals
            info['fieldGoals']=[[totals[t]['fgm'],totals[t]['fga']] for t in (game['home'],game['away'])]
            info['freeThrows']=[[totals[t]['ftm'],totals[t]['fta']] for t in (game['home'],game['away'])]
    # A period box may prove that only one candidate could receive this credit.
    # Never allocate ambiguous events merely to fill the expected final totals.
    for e in events:
        for role,person in e['participants'].items():
            if person['id'] or len(person['candidates'])<2: continue
            eligible=[]
            for pid in person['candidates']:
                q=quarter_players.get((e['period'],e['team'],pid))
                if q is None: eligible.append(pid);continue
                if role=='shooter':
                    if e['type']=='free_throw': possible=q['ftm'] if e['result']=='made' else q['fta']-q['ftm']
                    elif e['shotValue']==3: possible=q['three_pm'] if e['result']=='made' else q['three_pa']-q['three_pm']
                    else: possible=q['fgm']-q['three_pm'] if e['result']=='made' else (q['fga']-q['fgm'])-(q['three_pa']-q['three_pm'])
                else:
                    stat={'assister':'ast','blocker':'blk','stealer':'stl','committer':'tov','rebounder':'oreb' if e.get('reboundKind')=='offensive' else 'dreb' if e.get('reboundKind')=='defensive' else 'reb'}.get(role)
                    possible=q[stat] if stat else 1
                if possible>0: eligible.append(pid)
            person['periodBoxEligibleCandidates']=eligible
            if len(eligible)==1 and (e['period'],e['team'],eligible[0]) in quarter_players:
                person.update(id=eligible[0],method='unique possible credited actor in official period box',periodBoxPage=periods[e['period']].get('boxPage'))
    # Opposite-column credits link by printed row, not by a merely shared clock.
    by_row=defaultdict(list)
    for e in events:
        if e.get('rowId'): by_row[e['rowId']].append(e)
    for row in by_row.values():
        for e in row:
            if e['type']=='block':
                shots=[s for s in row if s['type']=='shot' and s['result']=='missed' and s['team']!=e['team']]
                e['linkedAttemptSequence']=shots[0]['sequence'] if len(shots)==1 else None
    for e in events:
        if e['type']!='free_throw': continue
        earlier=[s for s in events if s['period']==e['period'] and s['clock']==e['clock'] and s['sequence']<e['sequence']]
        baskets=[s for s in earlier if s['type']=='shot' and s['result']=='made' and s['team']==e['team'] and s['participants']['shooter']['id'] and s['participants']['shooter']['id']==e['participants']['shooter']['id']]
        fouls=[s for s in earlier if s['type']=='foul' and s['team']!=e['team'] and 'S.FOUL' in s['text']]
        special=bool(re.search(r'technical|flagrant|clear path|take foul|transition',e['text'],re.I))
        e['andOne']=bool(e.get('freeThrowAwarded')==1 and baskets and fouls and not special)
        e['linkedBasketSequence']=baskets[-1]['sequence'] if e['andOne'] else None
        e['linkedFoulSequence']=fouls[-1]['sequence'] if e['andOne'] else None
    nba_people={(r['team'],str(r['playerId'])):str(r['nbaPlayerId']) for r in game.get('identityCrosswalk',[]) if r.get('gamebookSourceHash')==record['sha256'] and r.get('nbaPlayerId')}
    logical_counts=Counter()
    for e in events:
        logical=(e['period'],e['clock'],e['team'],e['type']); logical_counts[logical]+=1
        for person in e['participants'].values(): person['sourceIds']={'espnPlayerId':person['id'],'nbaPlayerId':nba_people.get((person.get('team',e['team']),person['id']))}
        e['logicalId']=sha(packed([game['id'],*logical,logical_counts[logical]]).encode())
        e.update(sourceHash=record['sha256'],sourceUrl=record['source_url'],capturedAt=record.get('captured_at'),parserVersion=VERSION,parserHash=CODE_HASH,schemaVersion=SCHEMA,espnGameId=game['id'],nbaGameId=game.get('nbaGameId') or record.get('nba_game_id'),verification='interpreted; component acceptance in revision result')
    return events,periods,issues

def reconcile(events,periods,issues,game,record):
    counts=defaultdict(Counter); unresolved=Counter(); discrepancies=list(issues)
    role_stats={'shooter':['fgm','fga','three_pm','three_pa','ftm','fta','pts'],'assister':['ast'],'blocker':['blk'],'stealer':['stl'],'committer':['tov'],'rebounder':['oreb','dreb','reb']}
    for e in events:
        for role,p in e['participants'].items():
            if role not in role_stats: continue
            if role=='rebounder' and e.get('teamRebound') or role=='committer' and e.get('teamTurnover'): continue
            if not p['id']:
                unresolved.update(role_stats[role]); discrepancies.append({'kind':'unresolved participant','role':role,'sequence':e['sequence'],'page':e['page'],'token':p['token'],'candidates':p['candidates']}); continue
            c=counts[(e['team'],p['id'])]
            if role=='shooter':
                made=e['result']=='made'; ft=e['type']=='free_throw'
                c['fta' if ft else 'fga']+=1; c['ftm' if ft else 'fgm']+=int(made); c['pts']+=e['shotValue']*int(made)
                if not ft and e['shotValue']==3: c['three_pa']+=1; c['three_pm']+=int(made)
            elif role=='rebounder':
                c['reb']+=1
                if e.get('reboundKind'): c['oreb' if e['reboundKind']=='offensive' else 'dreb']+=1
                else: unresolved.update(['oreb','dreb'])
            else: c[{'assister':'ast','blocker':'blk','stealer':'stl','committer':'tov'}[role]]+=1
    for p in record['player_rows']:
        if not p['played']: continue
        pid=str(p['espn_player_id']); c=counts[(p['team'],pid)]
        for stat in STATS:
            if c[stat]!=p[stat]: discrepancies.append({'kind':'player box mismatch','team':p['team'],'playerId':pid,'player':p['nba_name'],'stat':stat,'observed':c[stat],'expected':p[stat],'sourcePage':1})
    for period,info in periods.items():
        for key,kind in [('fieldGoals','shot'),('freeThrows','free_throw')]:
            expected_period=info.get(key)
            if expected_period is None:
                discrepancies.append({'kind':'period shooting summary unavailable','period':period,'component':key,'pages':info['pages']})
                continue
            for side,team in enumerate((game['home'],game['away'])):
                shots=[e for e in events if e['period']==period and e['team']==team and e['type']==kind]
                observed=[sum(e['result']=='made' for e in shots),len(shots)]
                if observed!=expected_period[side]: discrepancies.append({'kind':'period shooting mismatch','period':period,'team':team,'component':key,'observed':observed,'expected':expected_period[side],'pages':info['pages']})
    max_period=max(periods,default=0)
    coverage=bool(max_period>=4 and set(periods)==set(range(1,max_period+1)) and all(p['ended'] for p in periods.values()))
    expected=[record['home_score'],record['away_score']]; actual=events[-1]['score'] if events else None
    if not coverage: discrepancies.append({'kind':'incomplete period coverage','observed':periods,'expected':'1..4 and all printed overtime periods, with end markers'})
    if actual!=expected: discrepancies.append({'kind':'final score mismatch','observed':actual,'expected':expected})
    # Require box minutes to support the number of periods. This detects a missing final OT.
    for team in (game['home'],game['away']):
        seconds=sum(p['minutes_seconds'] for p in record['player_rows'] if p['played'] and p['team']==team)
        if abs(seconds-(48+max(0,max_period-4)*5)*300)>5:
            coverage=False; discrepancies.append({'kind':'period count vs official minutes','team':team,'observedSeconds':seconds,'expectedSeconds':(48+max(0,max_period-4)*5)*300})
    for key,kind in [('firstScores','first score'),('firstFieldGoals','first field goal')]:
        for team in (game['home'],game['away']):
            first=next((e for e in events if e['team']==team and e['type'] in (('shot','free_throw') if key=='firstScores' else ('shot',)) and e['result']=='made'),None)
            old=game.get(key,{}).get(team)
            if old is None: discrepancies.append({'kind':'opening reference unavailable','team':team,'target':key})
            elif not first or first['participants']['shooter']['id']!=str(old['id']) or first['clock'].lstrip('0')!=old['clock'].lstrip('0'):
                discrepancies.append({'kind':kind+' mismatch','team':team,'observed':first,'expected':old})
    bad={d.get('stat') for d in discrepancies if d['kind']=='player box mismatch'}
    score_ok=coverage and not any(d['kind'] in ('shot score delta','final score mismatch','score correction or invalid progression','review score adjustment','uninterpreted score adjustment','missing column header','unrecognized period','period score mismatch','period shooting summary unavailable','period shooting mismatch') for d in discrepancies)
    components={s:bool(score_ok and s not in bad and not unresolved[s]) for s in STATS}
    required_context=[(e,r,p) for e in events for r,p in e['participants'].items() if not p['id'] and not p.get('nonPlayer') and not(e.get('teamRebound') and r=='rebounder' or e.get('teamTurnover') and r=='committer')]
    for e,r,p in required_context:
        if r not in role_stats: discrepancies.append({'kind':'unresolved context participant','sequence':e['sequence'],'page':e['page'],'role':r,'token':p['token'],'candidates':p['candidates']})
    status='verified' if all(components.values()) and not discrepancies and not required_context else 'partial' if coverage else 'quarantined'
    return {'status':status,'periodCoverage':coverage,'periods':periods,'finalScore':actual,'components':components,'discrepancies':discrepancies,'unresolvedContext':len(required_context),'playerCounts':{f'{t}:{p}':dict(c) for (t,p),c in counts.items()}}

def parse_job(job):
    library,game,record,*cached=job; pdf=Path(library)/record['pdf_path']
    try:
        raw=pdf.read_bytes(); digest=sha(raw)
        if digest!=record['sha256']: raise ValueError('PDF hash differs from verified box source; reverify boxes before using revision')
        pages=pages_from_pdf(raw,cached[0] if cached and cached[0] else None); events,periods,issues=parse_pages(pages,game,record)
        identity_path=game.get('identityEvidencePath') or str(Path(library)/'identity_sources'/(game['id']+'.json'))
        identity_evidence=pbp_identity.resolve(events,game,record,identity_path)
        result=reconcile(events,periods,issues,game,record)
        result['identityEvidence']=identity_evidence
        return game,record,pages,events,result,None
    except Exception as exc: return game,record,[],[],{'status':'quarantined','components':{},'discrepancies':[{'kind':'extraction failure','error':str(exc)}]},str(exc)

def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True); db=sqlite3.connect(path)
    db.executescript('''PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS identity_sources(hash TEXT PRIMARY KEY,metadata TEXT,data BLOB);
    CREATE TABLE IF NOT EXISTS parsers(hash TEXT PRIMARY KEY,version TEXT,source TEXT);
    CREATE TABLE IF NOT EXISTS sources(hash TEXT PRIMARY KEY,pdf BLOB NOT NULL,metadata TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,game_id TEXT NOT NULL,source_hash TEXT REFERENCES sources(hash),parser TEXT NOT NULL,schema_version INTEGER NOT NULL,game TEXT NOT NULL,appearances TEXT NOT NULL,pages TEXT NOT NULL,result TEXT NOT NULL,extracted_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events(revision TEXT REFERENCES revisions(id),sequence INTEGER,period INTEGER,clock TEXT,team TEXT,type TEXT,event TEXT NOT NULL,PRIMARY KEY(revision,sequence));
    CREATE INDEX IF NOT EXISTS event_period ON events(revision,period,sequence);
    CREATE TABLE IF NOT EXISTS active(game_id TEXT PRIMARY KEY,revision TEXT REFERENCES revisions(id));
    CREATE TABLE IF NOT EXISTS attempts(game_id TEXT PRIMARY KEY,checked_at TEXT,status TEXT,error TEXT);
    ''')
    with db:
        db.execute('INSERT OR IGNORE INTO parsers VALUES(?,?,?)',(CODE_HASH,VERSION,Path(__file__).read_text(encoding='utf-8')))
        db.execute('INSERT OR IGNORE INTO parsers VALUES(?,?,?)',(IDENTITY_RESOLVER_HASH,'identity-resolver-v1',Path(pbp_identity.__file__).read_text(encoding='utf-8')))
    return db

def revision_id(game,record): return sha(packed([game['id'],record['sha256'],VERSION,CODE_HASH,IDENTITY_RESOLVER_HASH,SCHEMA,record.get('pbpIdentitySource',{}).get('sha256'),sha(packed(record['player_rows']).encode())]).encode())
def store_result(db,library,parsed):
    game,record,pages,events,result,error=parsed; gid=game['id']; rid=revision_id(game,record)
    with db:
        db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?,?)',(gid,now(),result['status'],error))
        raw=(Path(library)/record['pdf_path']).read_bytes() if (Path(library)/record['pdf_path']).exists() else b''
        if sha(raw)!=record['sha256']: return
        db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?)',(record['sha256'],raw,packed({k:v for k,v in record.items() if k!='player_rows'})))
        if error: return
        evidence=result.get('identityEvidence')
        if evidence: db.execute('INSERT OR IGNORE INTO identity_sources VALUES(?,?,?)',(evidence['sha256'],packed(evidence),Path(evidence['path']).read_bytes()))
        db.execute('INSERT OR IGNORE INTO revisions VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,gid,record['sha256'],VERSION+'+'+CODE_HASH,SCHEMA,packed(game),packed(record['player_rows']),packed(pages),packed(result),now()))
        db.executemany('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?)',[(rid,e['sequence'],e['period'],e['clock'],e['team'],e['type'],packed(e)) for e in events])
        db.execute('INSERT OR REPLACE INTO active VALUES(?,?)',(gid,rid))


def event_context(db,rid,game,result):
    """Only publish reconciled event context; exact eligible games remain visible."""
    rows={(team,str(p['id'])):p for team,box in game.get('teams',{}).items() for p in box['players'] if p['played']}
    def position(team,pid,basis):
        p=rows.get((team,pid),{}); raw=(p.get('officialPosition') or p.get('rawPosition') or '').upper()
        if basis=='strict': return raw if raw in ('PG','SG','SF','PF','C') else 'unknown'
        return 'G' if raw in ('G','PG','SG') else 'F' if raw in ('F','SF','PF') else 'C' if raw=='C' else 'unknown'
    events=[json.loads(x[0]) for x in db.execute('SELECT event FROM events WHERE revision=? ORDER BY sequence',(rid,))]
    by_seq={e['sequence']:e for e in events}; result_context={}
    components=result['components']
    for team in (game['home'],game['away']):
        context={};player_credits=defaultdict(Counter)
        for basis in ('broad','strict'):
            groups=defaultdict(lambda:dict(assistedMakes=0,blockedAttempts=0,distancedAttempts=0,distanceFeetTotal=0))
            if components.get('ast') and components.get('fgm'):
                for e in events:
                    if e['team']==team and e['type']=='shot' and e['result']=='made' and e['participants'].get('assister',{}).get('id'):
                        groups[position(team,e['participants']['assister']['id'],basis)]['assistedMakes']+=1
                        if basis=='broad': player_credits[e['participants']['assister']['id']]['assistedMakes']+=1
            if components.get('blk') and components.get('fga'):
                for e in events:
                    if e['type']=='block' and e.get('linkedAttemptSequence'):
                        shot=by_seq[e['linkedAttemptSequence']]
                        if shot['team']==team and shot['participants']['shooter']['id']:
                            groups[position(team,shot['participants']['shooter']['id'],basis)]['blockedAttempts']+=1
                            if basis=='broad': player_credits[shot['participants']['shooter']['id']]['blockedAttempts']+=1
            if components.get('fga'):
                for e in events:
                    if e['team']==team and e['type']=='shot' and e.get('distanceFeet') is not None and e['participants']['shooter']['id']:
                        g=groups[position(team,e['participants']['shooter']['id'],basis)];g['distancedAttempts']+=1;g['distanceFeetTotal']+=e['distanceFeet']
                        if basis=='broad': player_credits[e['participants']['shooter']['id']]['distancedAttempts']+=1
            context[basis]=dict(groups)
        context['playerCredits']={pid:dict(c) for pid,c in player_credits.items()}
        context['available']={'assistedMakes':bool(components.get('ast') and components.get('fgm')),'blockedAttempts':bool(components.get('blk') and components.get('fga')),'distancedAttempts':bool(components.get('fga'))}
        opening={}
        for key,kinds in [('firstScore',('shot','free_throw')),('firstFieldGoal',('shot',))]:
            first=next((e for e in events if e['team']==team and e['type'] in kinds and e['result']=='made'),None)
            attempt=next((e for e in events if e['team']==team and e['type'] in kinds),None)
            if first and components.get('pts') and components.get('fga') and components.get('fta'):
                extra=[e for e in events if e.get('linkedBasketSequence')==first['sequence']]
                opening[key]={'scorer':first['participants']['shooter']['id'],'firstAttempt':attempt['participants']['shooter']['id'] if attempt else None,'firstAttemptMade':attempt['result']=='made' if attempt else None,'freeThrow':first['type']=='free_throw','andOneAwarded':bool(extra),'andOneAttempted':len(extra),'andOneMade':sum(e['result']=='made' for e in extra),'page':first['page'],'clock':first['clock']}
        context['opening']=opening;result_context[team]=context
    return result_context

def summary(db,expected,parent_hash=None):
    games={}; discrepancies=[]
    for gid,rid,source,game,result,extracted in db.execute('SELECT a.game_id,r.id,r.source_hash,r.game,r.result,r.extracted_at FROM active a JOIN revisions r ON r.id=a.revision'):
        g=json.loads(game); r=json.loads(result)
        games[gid]={'revision':rid,'sourceHash':source,'nbaGameId':g.get('nbaGameId'),'source':g.get('source'),'date':g['date'],'season':g.get('season'),'phase':g['phase'],'home':g['home'],'away':g['away'],'status':r['status'],'periods':len(r.get('periods',{})),'components':r['components'],'discrepancies':len(r['discrepancies']),'unresolvedContext':r.get('unresolvedContext'),'lastSuccessfulExtraction':extracted if r.get('periodCoverage') else None}
        games[gid]['eventContext']=event_context(db,rid,g,r)
        discrepancies.extend({'gameId':gid,'sourceHash':source,'sourceUrl':g.get('source'),'parser':VERSION,'resolution':'unresolved; affected component withheld',**d} for d in r['discrepancies'])
    expected_ids={g['id'] for g in expected}
    games={gid:g for gid,g in games.items() if gid in expected_ids}
    discrepancies=[d for d in discrepancies if d['gameId'] in expected_ids]
    for g in expected:
        if g['id'] not in games:
            games[g['id']]={'date':g['date'],'status':'pending','components':{},'reason':(db.execute('SELECT error FROM attempts WHERE game_id=?',(g['id'],)).fetchone() or ['No active extraction'])[0]}
    body={'schemaVersion':SCHEMA,'parserVersion':VERSION,'parserHash':CODE_HASH,'identityResolverHash':IDENTITY_RESOLVER_HASH,'parentEvidenceContentHash':parent_hash,'expected':len(expected),'statusCounts':dict(Counter(g['status'] for g in games.values())),'games':games}
    body['componentVerifiedGames']={k:sum(bool(g['components'].get(k)) for g in games.values()) for k in STATS}
    body['contentHash']=sha(packed(body).encode())
    return body,discrepancies

def run(library,database,evidence,output,workers=4,limit=None,force=False,game_id=None):
    start=time.monotonic(); data=json.loads(Path(evidence).read_text(encoding='utf-8')); games=data['games']
    if game_id: games=[g for g in games if g['id']==game_id]
    if limit: games=games[:limit]
    db=connect(database); jobs=[]; crosswalk=defaultdict(list)
    supplement=Path(evidence).with_name('parlay_data.json')
    if supplement.exists():
        linked=json.loads(supplement.read_text(encoding='utf-8'))
        if linked.get('meta',{}).get('parentEvidenceContentHash')==data['meta'].get('evidenceContentHash'):
            for role in linked.get('datedRoleEvidence',[]): crosswalk[role.get('gameId')].append(role)
    for g in games:
        try: r=json.loads((Path(library)/'records'/(g['id']+'.json')).read_text(encoding='utf-8'))
        except Exception as exc:
            with db: db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?,?)',(g['id'],now(),'pending',str(exc)))
            continue
        identity_meta=ROOT/'.pbp/identity_sources'/(g['id']+'.source.json')
        if identity_meta.exists(): r={**r,'pbpIdentitySource':json.loads(identity_meta.read_text(encoding='utf-8'))}
        rid=revision_id(g,r)
        if not force and db.execute('SELECT 1 FROM active WHERE game_id=? AND revision=?',(g['id'],rid)).fetchone(): continue
        cached=db.execute('SELECT pages FROM revisions WHERE source_hash=? AND pages!=? LIMIT 1',(r['sha256'],'[]')).fetchone()
        identities=[role for role in crosswalk[g['id']] if role.get('gamebookSourceHash')==r['sha256'] and role.get('effectiveGameDate')==g['date']]
        nba_ids={role.get('nbaGameId') for role in identities if role.get('nbaGameId')}
        jobs.append((str(library),{**g,'nbaGameId':next(iter(nba_ids)) if len(nba_ids)==1 else None,'identityCrosswalk':identities,'identityEvidencePath':str(ROOT/'.pbp/identity_sources'/(g['id']+'.json')),'season':data['meta']['season'],'source':r['source_url']},r,json.loads(cached[0]) if cached else None))
    with (concurrent.futures.ProcessPoolExecutor(max_workers=workers) if workers>1 else concurrent.futures.ThreadPoolExecutor(max_workers=1)) as pool:
        for i,parsed in enumerate(pool.map(parse_job,jobs),1):
            store_result(db,library,parsed)
            if i%25==0 or i==len(jobs): print(packed({'processed':i,'scheduled':len(jobs),'game':parsed[0]['id'],'status':parsed[4]['status'],'elapsedSeconds':round(time.monotonic()-start,2)}),flush=True)
    manifest,discrepancies=summary(db,games,data['meta'].get('evidenceContentHash'))
    save(output,manifest)
    if Path(output).name=='play_by_play_manifest.json':
        Path(output).with_suffix('.js').write_text('window.__FTB_PLAY_BY_PLAY__ = '+packed(manifest)+';\n',encoding='utf-8')
    save(Path(output).with_name('play_by_play_discrepancies.json'),discrepancies)
    print(packed({'statusCounts':manifest['statusCounts'],'runtimeSeconds':round(time.monotonic()-start,2),'databaseBytes':Path(database).stat().st_size,'manifestBytes':Path(output).stat().st_size,'discrepancies':len(discrepancies),'integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}),flush=True)
    db.close(); return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--library',required=True,type=Path); p.add_argument('--database',required=True,type=Path); p.add_argument('--evidence',type=Path,default=ROOT/'nba ftb shi/analyst_data.json'); p.add_argument('--output',type=Path,default=ROOT/'nba ftb shi/play_by_play_manifest.json'); p.add_argument('--workers',type=int,default=4); p.add_argument('--limit',type=int); p.add_argument('--game-id'); p.add_argument('--force',action='store_true'); a=p.parse_args(); run(a.library,a.database,a.evidence,a.output,a.workers,a.limit,a.force,a.game_id)

