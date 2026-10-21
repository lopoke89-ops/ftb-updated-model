import pathlib,json,collections,math,random
O=pathlib.Path(__file__).resolve().parent;R=O.parents[1];S=R/'nba ftb shi';read=lambda p:json.loads(p.read_text(encoding='utf-8'));data=read(S/'analyst_data.json');model=read(S/'ev_first_team_model.json');opening=read(S/'opening_data.json')['games'];roles={'PG':'G','SG':'G','SF':'F','PF':'F','C':'C','G':'G','F':'F'}
players=collections.defaultdict(list);teams=collections.defaultdict(lambda:{'games':0,'other':0,'own':collections.defaultdict(lambda:[0,0]),'allowed':collections.defaultdict(lambda:[0,0])});league={'games':0,'other':0,'starts':0,'wins':0,'roles':collections.defaultdict(lambda:[0,0])};rows=[];sets=collections.Counter();fail=[]
games=sorted([g for g in data['games'] if g['phase']=='regular-season'],key=lambda g:(g['date'],g['id']));start=0
def dist(feature,c):
 if c=='uniform':return {p['id']:(1-feature['other'])/5 for p in feature['players']},feature['other']
 weights=[]
 for p in feature['players']:
  r=(p['wins']+c['prior']*p['prior'])/(p['n']+c['prior']);recent=p['history'][-20:];rr=(sum(x[0] for x in recent)+c['prior']*p['prior'])/(len(recent)+c['prior']);weight=((1-c['recentWeight'])*r+c['recentWeight']*rr)*p['offense']**c['offensePower']*p['defense']**c['defensePower'];weights.append(weight**(1/c['temperature']))
 total=sum(weights);other=max(1e-6,min(.2,feature['other']));return {p['id']:(1-other)*w/total for p,w in zip(feature['players'],weights)},other
while start<len(games):
 end=start+1
 while end<len(games) and games[end]['date']==games[start]['date']:end+=1
 for g in games[start:end]:
  for team in [g['home'],g['away']]:
   opp=g['away'] if team==g['home'] else g['home'];five=[p for p in g['teams'][team]['players'] if p['played'] and p['starter']]
   if teams[team]['games']<10 or teams[opp]['games']<10 or any(len(players[(team,str(p['id']))])<20 for p in five):continue
   feature={'players':[],'other':(teams[team]['other']+20*(league['other']+1)/(league['games']+200))/(teams[team]['games']+20)};valid=True
   for p in five:
    pid=str(p['id']);hist=players[(team,pid)];role=hist[-1][1]
    if not role:valid=False;break
    n=len(hist);wins=sum(x[0] for x in hist);prior=(league['wins']+1)/(league['starts']+5);l=league['roles'][role];pr=(l[1]+1)/(l[0]+5) if l[0] else prior
    def ratio(b):return math.exp(max(-.7,min(.7,math.log(max(.01,((b[1]+20*pr)/(b[0]+20))/pr))))) if b[0] else 1
    feature['players'].append({'id':pid,'n':n,'wins':wins,'prior':prior,'history':list(hist),'offense':ratio(teams[team]['own'][role]),'defense':ratio(teams[opp]['allowed'][role])})
   if not valid:continue
   window='development' if g['date']<=model['protocol']['developmentEnd'] else 'calibration' if g['date']<=model['protocol']['calibrationEnd'] else 'diagnostic'
   if g['date']>model['protocol']['diagnosticEnd']:continue
   sets[window]+=1
   if window!='diagnostic':continue
   winner=str(opening[g['id']]['firstScores'][team]['id']);selected=[p for p in feature['players'] if p['wins']>=3 and p['n']-p['wins']>=5];forecasts={name:dist(feature,c) for name,c in [('model',model['config']),('history',model['baselineConfig']),('uniform','uniform')]}
   for p in selected:
    obs={'fixture':g['id'],'team':team,'id':p['id'],'weight':1/len(selected),'y':int(p['id']==winner)}
    for name,(ps,other) in forecasts.items():
     if abs(sum(ps.values())+other-1)>1e-12:fail.append('normalization')
     obs[name]=ps[p['id']]
    if not rows:obs['firstFeature']=feature
    rows.append(obs)
 for g in games[start:end]:
  for t in [g['home'],g['away']]:
   opp=g['away'] if t==g['home'] else g['home'];five=[p for p in g['teams'][t]['players'] if p['played'] and p['starter']];winner=str(opening[g['id']]['firstScores'][t]['id']);other=not any(str(p['id'])==winner for p in five);teams[t]['games']+=1;teams[t]['other']+=other;league['games']+=1;league['other']+=other
   for p in five:
    pid=str(p['id']);role=roles.get(p.get('officialPosition') or p.get('rawPosition'));win=int(pid==winner);players[(t,pid)].append((win,role));league['starts']+=1;league['wins']+=win
    if role:
     for b in [teams[t]['own'][role],teams[opp]['allowed'][role],league['roles'][role]]:b[0]+=1;b[1]+=win
 start=end
total=sum(r['weight'] for r in rows);metrics={}
for name in ['model','history','uniform']:
 metrics[name]={'brier':sum(r['weight']*(r[name]-r['y'])**2 for r in rows)/total,'logLoss':sum(-r['weight']*(r['y']*math.log(r[name])+(1-r['y'])*math.log(1-r[name])) for r in rows)/total}
 expected=model['diagnostic'] if name=='model' else model['diagnostic'][name+'Baseline']
 for metric in ['brier','logLoss']:
  if abs(metrics[name][metric]-expected[metric])>1e-10:fail.append({'name':name,'metric':metric,'actual':metrics[name][metric],'stored':expected[metric]})
production=read(O/'production-diagnostic-cases.json');actual={(r['fixtureId'],r['team'],r['id']):r for r in production['cases']};reference={(r['fixture'],r['team'],r['id']):r for r in rows}
if production['modelHash']!=model['modelHash']:fail.append('production-case model hash differs')
if actual.keys()!=reference.keys():fail.append('production/reference case identities differ')
maximum_probability_error=0
for key,r in reference.items():
 if key not in actual:continue
 a=actual[key];error=abs(a['p']-r['model']);maximum_probability_error=max(maximum_probability_error,error)
 if error>1e-12 or a['y']!=r['y'] or abs(a['w']-r['weight'])>1e-12:fail.append({'case':key,'probabilityError':error,'production':a,'reference':r})
clusters=collections.defaultdict(lambda:[0,0])
for r in rows:clusters[r['fixture']][0]+=r['weight']*((r['model']-r['y'])**2-(r['history']-r['y'])**2);clusters[r['fixture']][1]+=r['weight']
rr=random.Random(20261021);cs=list(clusters.values());boot=[]
for _ in range(2000):
 selected=rr.choices(cs,k=len(cs));boot.append(sum(x[0] for x in selected)/sum(x[1] for x in selected))
boot.sort();report={'modelHash':model['modelHash'],'sets':dict(sets),'fixtures':len(clusters),'supportedPlayerDecisions':len(rows),'maximumIndividualProbabilityError':maximum_probability_error,'metrics':metrics,'pairedBrierDifferenceFixtureInterval95':[boot[49],boot[1949]],'failures':fail,'observations':rows,'method':'Independent Python reconstruction from strictly earlier-date official starter and first-score records. Repaired frozen configurations only; this does not independently refit the grid or temperature. Compares all 984 individual probabilities/outcomes/weights and aggregate baseline losses. Shares IDs, source-extracted opening ledger and historical role labels with production. Final-box five defines retrospective conditioning, not available-before-tip evidence. The archive has already been inspected; no untouched evaluation is claimed.'};(O/'FIRSTTEAM_INDEPENDENT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in report.items() if k!='observations'}));raise SystemExit(bool(fail))
