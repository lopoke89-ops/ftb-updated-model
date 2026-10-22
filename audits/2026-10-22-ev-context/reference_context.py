"""Independent sums over official box/dated starter-role records; no JS aggregates imported."""
import collections, hashlib, json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(__file__).resolve().parent
S=ROOT/'nba ftb shi'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
data=read(S/'analyst_data.json');supplement=read(S/'parlay_data.json')
groups=collections.defaultdict(list)
for r in supplement['datedRoleEvidence']:groups[(r['gameId'],r['team'])].append(r)
observations=[]
for g in data['games']:
 if g['date']>='2026-10-22' or g['phase']!='regular-season':continue
 for defending in [g['home'],g['away']]:
  offensive=g['away'] if defending==g['home'] else g['home']
  ps=[p for p in g['teams'][offensive]['players'] if p['played'] and p['starter']];rs=groups[g['id'],offensive]
  if not(len(ps)==len(rs)==5 and {str(p['id']) for p in ps}=={r['playerId'] for r in rs} and {r['position'] for r in rs}=={'PG','SG','SF','PF','C'} and all(r['gamebookSourceHash']==g['sourceHash'] and r['effectiveGameDate']==g['date'] for r in rs)):continue
  for p in ps:
   if p.get('statsSourceHash')!=g['sourceHash'] or p.get('minutesSeconds') is None:continue
   role=next(r['position'] for r in rs if r['playerId']==str(p['id']))
   observations.append((defending,role,p))
js=r"""const fs=require('fs'),C=require('./nba ftb shi/ev_context.js'),archive=require('./nba ftb shi/analyst_data.json'),supplement=require('./nba ftb shi/parlay_data.json');const index=C.create({archive,supplement,trusted:true}),cases=[];for(const defender of ['BOS','LAL','DET'])for(const position of C.POSITIONS)for(const market of ['points','threes','assists','rebounds']){const c=index.describe({quote:{playerId:'reference',team:'NYK',market,side:'over',line:10.5},features:{}},{date:'2026-10-22',away:'NYK',home:defender,season:'2026-27'},{record:{position},label:'Synthetic role for arithmetic audit',teamStatus:'projected'},{});cases.push({defender,position,market,opposing:c.profile.opposing,baseline:c.profile.baseline});}console.log(JSON.stringify(cases));"""
cases=json.loads(subprocess.check_output(['node','-e',js],cwd=ROOT,text=True))
maximum=0
for c in cases:
 for label in ['opposing','baseline']:
  rows=[p for t,r,p in observations if r==c['position'] and ((t!=c['defender']) if label=='baseline' else (t==c['defender']))]
  field='threeMade' if c['market']=='threes' else c['market']
  rows=[p for p in rows if p.get(field) is not None and (c['market']!='rebounds' or p['offensiveRebounds']+p['defensiveRebounds']==p[field])]
  total=sum(p[field] for p in rows);seconds=sum(p['minutesSeconds'] for p in rows);actual=c[label]
  assert total==actual['total'] and seconds==actual['seconds'],(c['defender'],c['position'],c['market'],label)
  reference=total*2880/seconds;error=abs(reference-actual['per48']);maximum=max(maximum,error);assert error<1e-12
unchanged=['ev_probability.js','ev_model.json','ev_model.js','ev_additional.js','ev_additional_model.json','ev_additional_model.js','ev_first_team.js','ev_first_team_model.json','ev_first_team_model.js','parlay.js','parlay_additional.js','matchup.js']
hashes={}
expected=read(OUT/'INDEPENDENT_CONTEXT.json')['unchangedSourceHashes']
for n in unchanged:
 hashes[n]=hashlib.sha256((S/n).read_bytes()).hexdigest()
 assert hashes[n]==expected[n],n
report={'cases':len(cases),'componentComparisons':2*len(cases),'maximumPer48Error':maximum,'observations':len(observations),'unchangedSourceHashes':hashes,'method':'Independent Python source-record sums for all five positions, four markets and three defending teams, comparing both opponent and excluded-team league reference. Shares retained identities, extracted official boxes and dated role captures; does not establish causal defense or forecasting improvement. No source forecasts/Parlay/matchup helpers used in reference sums.'}
(OUT/'INDEPENDENT_CONTEXT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
