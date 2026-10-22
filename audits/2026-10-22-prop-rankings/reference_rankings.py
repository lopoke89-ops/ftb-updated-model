"""Direct-record reference: no production aggregation, ranking or forecasting helper."""
import collections,json,pathlib,subprocess,re,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2];S=ROOT/'nba ftb shi';OUT=pathlib.Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
a=read(S/'analyst_data.json');supp=read(S/'parlay_data.json');teams='ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS'.split();positions=['PG','SG','SF','PF','C'];markets=['points','threes','assists','rebounds'];roles=collections.defaultdict(list)
for r in supp['datedRoleEvidence']:roles[(r['gameId'],r['team'])].append(r)
expected=collections.Counter();obs=collections.defaultdict(list);opens=collections.defaultdict(list)
for g in a['games']:
 if g['phase']!='regular-season' or g['date']>='2026-10-22':continue
 for defender,offense in [(g['home'],g['away']),(g['away'],g['home'])]:
  expected[defender]+=1
  ps=[p for p in g['teams'][offense]['players'] if p['played'] and p['starter']];rs=roles[g['id'],offense]
  valid=len(ps)==len(rs)==5 and {str(p['id']) for p in ps}=={str(r['playerId']) for r in rs} and {r['position'] for r in rs}==set(positions) and all(r['effectiveGameDate']==g['date'] and r['gamebookSourceHash']==g['sourceHash'] and re.fullmatch('[a-f0-9]{64}',r['sourceHash']) and r['source']=='https://stats.nba.com/js/data/leaders/00_daily_lineups_'+g['date'].replace('-','')+'.json' for r in rs)
  if not valid:continue
  role={str(r['playerId']):r['position'] for r in rs}
  def authority(p):return p.get('statsSourceHash')==g['sourceHash'] and re.fullmatch('[a-f0-9]{64}',g['sourceHash']) and re.match(r'https://(?:[a-z0-9-]+\.)*nba\.com/.+\.pdf(?:\?.*)?$',p.get('statsSource',''),re.I)
  for p in ps:
   if not authority(p) or not isinstance(p.get('minutesSeconds'),(int,float)) or p['minutesSeconds']<=0:continue
   for m in markets:
    field='threeMade' if m=='threes' else m;v=p.get(field)
    if not isinstance(v,int) or v<0:continue
    if m=='rebounds' and (not isinstance(p.get('offensiveRebounds'),int) or not isinstance(p.get('defensiveRebounds'),int) or p['offensiveRebounds']<0 or p['defensiveRebounds']<0 or p['offensiveRebounds']+p['defensiveRebounds']!=v):continue
    obs[defender,role[str(p['id'])],m].append((g['id'],v,p['minutesSeconds']))
  o=supp['openingEvidence']['games'].get(g['id'],{});e=o.get('firstScores',{}).get(offense,{});scorer=next((p for p in g['teams'][offense]['players'] if p['played'] and str(p['id'])==str(e.get('id'))),None)
  if re.match(r'https://(?:statsdmz|stats)\.nba\.com/pdfs/',g.get('source','')) and o.get('source')==g['source'] and o.get('sourceHash')==g['sourceHash'] and e.get('team')==offense and e.get('period')==1 and e.get('points') in [1,2,3] and isinstance(e.get('sequence'),int) and e.get('page',0)>1 and scorer and authority(scorer) and str(g['firstScores'].get(offense,{}).get('id'))==str(e.get('id')):
   opens[defender].append(role.get(str(scorer['id']),'other'))
js="""const C=require('./nba ftb shi/ev_context.js'),a=require('./nba ftb shi/analyst_data.json'),s=require('./nba ftb shi/parlay_data.json'),x=C.create({archive:a,supplement:s,trusted:true});const cases=[],opening=[];for(const team of C.TEAMS){const away=team==='NYK'?'BOS':'NYK',f={home:team,away,date:'2026-10-22',season:'2026-27'};for(const position of C.POSITIONS)for(const market of C.MARKETS){const c=x.describe({quote:{team:away,playerId:'reference',market},features:{}},f,{record:{position}}),p=c.profile,r=p.ranking;cases.push({team,position,market,total:p.opposing.total,seconds:p.opposing.seconds,games:p.opposing.games,expected:p.opposing.expectedGames,baselineTotal:p.baseline.total,baselineSeconds:p.baseline.seconds,rank:{status:r.status,most:r.mostRank,fewest:r.fewestRank,ties:r.tiedTeams,eligible:r.eligibleTeams}});}const o=x.opening(f,team).profile;opening.push({team,games:o.games,expected:o.expectedGames,other:o.other,positions:o.positions.map(p=>({position:p.position,count:p.count,frequency:p.frequency,rank:{status:p.ranking.status,most:p.ranking.mostRank,fewest:p.ranking.fewestRank,ties:p.ranking.tiedTeams,eligible:p.ranking.eligibleTeams}}))});}console.log(JSON.stringify({cases,opening}));"""
actual=json.loads(subprocess.check_output(['node','-e',js],cwd=ROOT,text=True))
def ranking(entries,team):
 qualified={t:(n,d) for t,(n,d,g) in entries.items() if g>=20 and g/expected[t]>=.9 and d>0}
 out={'status':'unavailable','most':None,'fewest':None,'ties':None,'eligible':len(qualified)}
 if team not in qualified or len(qualified)<20:return out
 n,d=qualified[team];values=[v*d-n*w for v,w in qualified.values()]
 return dict(status='ranked',most=1+sum(v>0 for v in values),fewest=1+sum(v<0 for v in values),ties=sum(v==0 for v in values),eligible=len(qualified))
for c in actual['cases']:
 rows=obs[c['team'],c['position'],c['market']];total=sum(r[1] for r in rows);seconds=sum(r[2] for r in rows)
 assert (c['total'],c['seconds'],c['games'],c['expected'])==(total,seconds,len({r[0] for r in rows}),expected[c['team']]),c
 others=[r for t in teams if t!=c['team'] for r in obs[t,c['position'],c['market']]]
 assert (c['baselineTotal'],c['baselineSeconds'])==(sum(r[1] for r in others),sum(r[2] for r in others)),c
 entries={t:(sum(r[1] for r in obs[t,c['position'],c['market']]),sum(r[2] for r in obs[t,c['position'],c['market']]),len({r[0] for r in obs[t,c['position'],c['market']]})) for t in teams}
 assert c['rank']==ranking(entries,c['team']),c
for c in actual['opening']:
 assert (c['games'],c['expected'],c['other'])==(len(opens[c['team']]),expected[c['team']],opens[c['team']].count('other')),c
 for p in c['positions']:
  assert p['count']==opens[c['team']].count(p['position']),p
  assert abs(p['frequency']-p['count']/c['games'])<1e-12,p
  entries={t:(opens[t].count(p['position']),len(opens[t]),len(opens[t])) for t in teams}
  assert p['rank']==ranking(entries,c['team']),p
unchanged=read(ROOT/'audits/2026-10-22-ev-context/INDEPENDENT_CONTEXT.json')['unchangedSourceHashes']
for n,h in unchanged.items():assert hashlib.sha256((S/n).read_bytes()).hexdigest()==h,n
report={'countRankCases':len(actual['cases']),'countOpponentAndReferenceSums':2*len(actual['cases']),'openingRankCases':sum(len(c['positions']) for c in actual['opening']),'allPassed':True,'rankedCountCases':sum(c['rank']['status']=='ranked' for c in actual['cases']),'openingTeamCoverage':{c['team']:{'accepted':c['games'],'expected':c['expected'],'other':c['other']} for c in actual['opening']},'unchangedSourceHashes':unchanged,'sharedEvidence':'Retained official box rows, identity IDs, dated five-position records and independently verified opening-event records. Reference uses direct Python sums/comparisons and imports no production feature/rank/model helper. Both use retrospective source records; not proof of pregame capture, causal defense or predictive improvement.'}
(OUT/'INDEPENDENT_RANKINGS.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
