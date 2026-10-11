const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const L=require('../lineups.js');
const A=require('../analyst.js'),H=require('../scouting_history.js'),P=require('../parlay.js'),base=path.join(__dirname,'..');
const read=name=>JSON.parse(fs.readFileSync(path.join(base,name)));
const data=read('analyst_data.json'),extra=read('parlay_data.json'),canonical=read('merged_dataset.json');
const refs=Object.fromEntries(Object.values(canonical.players).map(p=>[p.sourcePlayerId,{position:p.position,source:'canonical'}]));
const regular=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',positionReferences:refs});
const playoffs=P.build(A,H,data,extra,{mode:'review',phase:'playoffs',positionReferences:refs});
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
const rank=(model,team='SAS',opponent='NYK',overrides={})=>P.rankTeam({team,opponent,roster:model.snapshot.rosters[team],snapshot:model.snapshot,sample:model.scope,...overrides});
test('official evidence matches released game hashes and totals',()=>{assert.equal(extra.meta.games,1322);assert.equal(extra.meta.parentEvidenceContentHash,data.meta.evidenceContentHash);assert.equal(extra.meta.totals.points,304328);assert.equal(2*extra.meta.totals.fgm+extra.meta.totals.threeMade+extra.meta.totals.ftm,304328);assert(regular.scope.supplementValid);});

test('NBA corrected participation governs averages and paired correlations',()=>{
  const v=P.summarize(regular.scope.byPlayer['6478'].all),o=P.summarize(regular.scope.byPlayer['5107156'].all);
  assert.equal(v.gp,64);assert.equal(v.total.points,965);assert.equal(v.ppg,965/64);assert.equal(v.fgCorrelation.n,64);
  assert.equal(o.gp,37);assert.equal(o.total.fga,77);assert.equal(o.total.threeAttempted,19);assert.equal(o.total.rebounds,112);assert.equal(o.total.assists,42);
  assert.equal(o.mpg,20654/60/37);assert(!data.games.find(g=>g.id==='401810583').teams.BOS.players.find(p=>p.id==='6478').played);
  assert(data.games.find(g=>g.date==='2025-12-01'&&g.away==='CHI'&&g.home==='ORL').teams.CHI.players.find(p=>p.id==='5107156').played);
});

test('all released box stats equal the authoritative NBA ledger',()=>{
  const official=read('official_boxscores.json'),keys=['points','fgm','fga','threeMade','threeAttempted','ftm','fta','rebounds','assists','steals','blocks','turnovers','fouls','offensiveRebounds','defensiveRebounds','plusMinus','minutesSeconds'];let appearances=0;
  assert.equal(data.meta.officialBoxscoreContentHash,official.meta.contentHash);assert.equal(extra.meta.officialBoxscoreContentHash,official.meta.contentHash);
  for(const g of data.games){assert.equal(g.source,official.games[g.id].source);assert.equal(g.sourceHash,official.games[g.id].sha256);
    for(const [team,box] of Object.entries(g.teams)){
      const rows=official.games[g.id].teams[team];assert.deepEqual(box.players.filter(p=>p.played).map(p=>p.id).sort(),Object.keys(rows).sort());
      for(const p of box.players.filter(p=>p.played)){appearances++;const r=extra.games[g.id][team][p.id];for(const key of keys){assert.equal(p[key],rows[p.id][key]);assert.equal(r[key],rows[p.id][key]);}assert.equal(p.minutes,p.minutesSeconds/60);assert.equal(p.starter,rows[p.id].starter);}
    }
  }assert.equal(appearances,28716);
});

test('full stat percentages derive from totals and missing fields remain unavailable',()=>{
  const s=P.summarize(regular.scope.byPlayer['5107156'].all),t=s.total;
  assert.equal(s.rpg,112/37);assert.equal(s.apg,42/37);assert.equal(s.fgPct,t.fgm/t.fga);assert.equal(s.tsPct,t.points/(2*(t.fga+.44*t.fta)));
  assert.equal(P.summarize([{points:0,fga:0,fgm:0,threeMade:0,threeAttempted:0,ftm:0,fta:0,minutes:0}]).rpg,null);
});
test('regular season and postseason never pool',()=>{assert.equal(regular.snapshot.games.length,1230);assert.equal(playoffs.snapshot.games.length,85);assert.throws(()=>P.build(A,H,data,extra,{phase:'all'}));assert.throws(()=>P.build(A,H,data,extra,{phase:'regular-and-playoffs'}));});
test('every player phase average matches canonical phase averages',()=>{for(const phase of ['regular-season','playoffs']){const model=phase==='playoffs'?playoffs:regular;for(const p of Object.values(canonical.players)){const s=P.summarize(model.scope.byPlayer[p.sourcePlayerId]?.all||[]),c=p.ppgByPhase[phase];assert.equal(s.gp,c.gp,p.name+' '+phase);if(s.gp)assert(Math.abs(s.ppg-c.ppg)<1e-10,p.name+' '+phase);}}});
test('every played shooting row reconciles makes attempts and points',()=>{for(const g of data.games)for(const [t,box] of Object.entries(g.teams)){let points=0;for(const p of box.players){if(!p.played)continue;const r=P.shootingRow(g,t,p,extra,true);assert(r);points+=r.points;assert.equal(2*r.fgm+r.threeMade+r.ftm,r.points);}assert.equal(points,box.points);}});
test('two teams receive exactly six distinct market slots',()=>{const slots=[...rank(regular,'SAS','NYK'),...rank(regular,'NYK','SAS')];assert.equal(slots.length,6);for(const team of ['SAS','NYK'])assert.deepEqual(slots.filter(s=>s.team===team).map(s=>s.market),P.MARKETS);assert(slots.every(s=>s.pick));});
test('all markets use identical documented component weights',()=>{assert.deepEqual(P.WEIGHTS,{offense:1/3,defense:1/3,opportunity:1/3});for(const {pick:p} of rank(regular)){assert(Math.abs(p.score-100*(p.components.offense+p.components.defense+p.components.opportunity)/3*p.qualityFactor)<1e-10);assert(p.score>=0&&p.score<=100);}});
test('points and threes use their own positive paired correlation',()=>{for(const team of Object.keys(regular.snapshot.rosters))for(const slot of rank(regular,team,team==='SAS'?'NYK':'SAS'))if(slot.pick&&slot.market!=='first-team-basket'){const p=slot.pick,three=slot.market==='threes',corr=P.correlation(p.rows,three?'threeAttempted':'fga',three?'threeMade':'fgm');assert(corr.r>0);assert.equal(p.correlation.r,corr.r);assert.equal(p.correlation.n,p.stats.gp);}});
test('constant negative and sparse correlations do not qualify',()=>{const positive=[1,2,3,4,5].map(n=>({a:n,b:n})),negative=positive.map(p=>({...p,b:6-p.a}));assert.equal(P.correlation(positive,'a','b').r,1);assert.equal(P.correlation(negative,'a','b').r,-1);assert.equal(P.correlation(positive.slice(0,4),'a','b').r,null);assert.equal(P.correlation(positive.map(p=>({...p,b:1})),'a','b').r,null);});
test('three-only opportunity is based on 3PA and 3PM',()=>{const p=rank(regular).find(s=>s.market==='threes').pick;assert.equal(p.stats.threePa,p.rows.reduce((n,r)=>n+r.threeAttempted,0)/p.rows.length);assert.equal(p.stats.threePct,p.stats.total.threeMade/p.stats.total.threeAttempted);});
test('trade stints are separate for team picks and pooled once for season totals',()=>{const traded=Object.values(regular.scope.byPlayer).find(p=>Object.keys(p.teams).length>1);assert(traded);assert.equal(traded.all.length,Object.values(traded.teams).reduce((n,r)=>n+r.length,0));assert.equal(new Set(traded.all.map(p=>p.gameId)).size,traded.all.length);const id=Object.entries(regular.scope.byPlayer).find(([,p])=>p===traded)[0];for(const [team,rows] of Object.entries(traded.teams))assert.equal(rows.length,regular.snapshot.players[id].ftbByTeam[team].gp);});
test('pregame filtering cannot include current or later games',()=>{const model=P.build(A,H,data,extra,{mode:'pregame',date:'2026-01-01',phase:'regular-season',positionReferences:refs});assert(model.snapshot.games.every(g=>g.date<'2026-01-01'));assert(Object.values(model.scope.byPlayer).every(p=>p.all.every(r=>r.date<'2026-01-01')));});
test('last-five windows respect individual team inclusion',()=>{const model=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',window:5,positionReferences:refs});assert(Object.values(model.scope.byTeam).every(t=>t.games===5));for(const p of Object.values(model.scope.byPlayer))for(const rows of Object.values(p.teams))assert(rows.length<=5);});
test('head-to-head excludes unrelated games and old-team appearances',()=>{const model=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',historyMatchups:[{home:'SAS',away:'NYK'}],positionReferences:refs});assert(model.snapshot.games.every(g=>[g.home,g.away].sort().join('|')==='NYK|SAS'));assert(Object.keys(model.scope.byTeam).every(t=>['SAS','NYK'].includes(t)));for(const p of Object.values(model.scope.byPlayer))for(const r of p.all)assert(['SAS','NYK'].includes(r.team));});
test('no matchup no trusted data and empty roster preserve three explicit slots',()=>{for(const overrides of [{opponent:null},{trusted:false},{roster:[]}]){const slots=rank(regular,'SAS','NYK',overrides);assert.equal(slots.length,3);assert(slots.every(s=>!s.pick&&s.reason));}});
test('missing or mismatched shooting evidence cannot manufacture selections',()=>{for(const supplement of [null,{...extra,meta:{...extra.meta,parentEvidenceContentHash:'wrong'}}]){const model=P.build(A,H,data,supplement,{mode:'review',phase:'regular-season',positionReferences:refs});assert(rank(model).every(s=>!s.pick));}});
test('excluded players never appear in any market',()=>{const before=rank(regular),ids=before.map(s=>s.pick.id),after=rank(regular,'SAS','NYK',{excludedIds:ids});assert(after.every(s=>!s.pick||!ids.includes(s.pick.id)));});
test('missing lines do not invent prop sides or prices',()=>{for(const s of rank(regular))if(s.market!=='first-team-basket'){assert.equal(s.pick.decision.line,null);assert.equal(s.pick.decision.side,null);assert.equal(s.pick.decision.status,'Market line unavailable');}});
test('manual lines yield reproducible observed over under and push counts',()=>{const rows=[{points:10},{points:20},{points:30}],d=P.lineDecision(rows,'points',20);assert.equal(d.side,null);assert.deepEqual([d.over,d.under,d.push,d.n],[1,1,1,3]);assert.equal(P.lineDecision(rows,'points',19.5).side,'Over');assert.equal(P.lineDecision(rows,'points',20.5).side,'Under');assert.equal(P.lineDecision(rows,'points',-1).line,null);});
test('official opening evidence covers every fixture and retains source hashes',()=>{
  const o=extra.openingEvidence;assert.equal(o.meta.games,1322);assert.equal(o.meta.parentEvidenceContentHash,data.meta.evidenceContentHash);assert(regular.scope.openingVerified);
  for(const g of data.games){const x=o.games[g.id];assert.equal(x.sourceHash,g.sourceHash);assert.equal(x.source,g.source);for(const team of [g.home,g.away]){for(const key of ['firstScores','firstFieldGoals']){const e=x[key][team];assert(g.teams[team].players.some(p=>p.played&&p.id===e.id));assert.equal(e.period,1);assert(e.page>1);for(const field of ['id','clock','period','sequence','points','shot'])assert.equal(g[key][team][field],e[field]);}assert(!x.firstFieldGoals[team].isFreeThrow);}}
});
test('basket definition changes actual counts while points and threes stay independent',()=>{
  const fg=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',positionReferences:refs,firstBasketTarget:P.FIRST_TARGETS[1]});
  assert.equal(regular.snapshot.meta.target,P.FIRST_TARGETS[0]);assert.equal(fg.snapshot.meta.target,P.FIRST_TARGETS[1]);
  const a=regular.snapshot.games.find(g=>g.id==='401809235'),b=fg.snapshot.games.find(g=>g.id===a.id);assert(a.firstScores.SAS.isFreeThrow);assert(!b.firstFieldGoals.SAS.isFreeThrow);
  assert.notDeepEqual(regular.scope.byTeam.SAS.first,fg.scope.byTeam.SAS.first);
  const first=rank(regular),second=rank(fg);for(let i=1;i<3;i++){assert.equal(first[i].pick.id,second[i].pick.id);assert.equal(first[i].pick.score,second[i].pick.score);}
  assert(second[0].label.includes('Field Goal'));assert.throws(()=>P.build(A,H,data,extra,{firstBasketTarget:'other'}));
});
test('and-one awards retain made and missed free throws with supporting events',()=>{
  const o=extra.openingEvidence.games;
  const made=o['401809243'].firstFieldGoals.OKC,missed=o['401809949'].firstFieldGoals.NOP;
  assert(made.andOneAwarded&&missed.andOneAwarded);assert.equal(made.andOneMade,1);assert.equal(missed.andOneMade,0);assert.equal(missed.andOneAttempts,1);
  let count=0;for(const g of Object.values(o))for(const e of Object.values(g.firstFieldGoals))for(const ft of e.andOneFreeThrows){count++;assert.equal(ft.clock,e.clock);assert.equal(ft.athleteIds[0],e.id);assert.equal(ft.linkedBasketSequence,e.sequence);const foul=g.orderedEvents.find(x=>x.sequence===ft.linkedFoulSequence);assert(foul&&foul.team!==e.team&&foul.text.includes('S.FOUL'));assert(!/technical|flagrant|clear path|take foul|transition/i.test(ft.text));}
  assert(count>0);
});
test('missing opening evidence withholds only the first-basket slot',()=>{
  const model=P.build(A,H,data,{...extra,openingEvidence:null},{mode:'review',phase:'regular-season',positionReferences:refs});const slots=rank(model);assert(!slots[0].pick);assert(slots[0].reason.includes('opening play-by-play'));assert(slots[1].pick&&slots[2].pick);
});
test('season target uses the full competition average despite a rolling sample',()=>{
  const five=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',window:5,positionReferences:refs});
  for(const s of rank(five,'SAS','NYK',{seasonScope:regular.scope}).filter(s=>s.market!=='first-team-basket'&&s.pick)){const p=s.pick,target=p.seasonTarget;assert.equal(target.n,p.stats.gp);assert(p.seasonStats.gp>p.stats.gp);assert.equal(target.threshold,Math.ceil(target.average-1e-10));assert.equal(target.hits,p.rows.filter(r=>r[s.market==='points'?'points':'threeMade']>=target.threshold).length);}
  assert.equal(P.seasonDecision([{points:22},{points:23}],'points',{ppg:22.4}).hits,1);
  assert.equal(P.seasonDecision([{threeMade:2},{threeMade:3}],'threes',{threePm:2.3}).hits,1);
});
test('five specific positions remain distinct and broad labels are never guessed',()=>{assert.equal(P.positionGroup({rawPosition:'G'}),'unknown');assert.equal(P.positionGroup({position:'SG'}),'SG');assert.equal(P.positionGroup({position:'PF'}),'PF');assert.equal(P.positionGroup({rawPosition:'F-C'}),'unknown');});
test('Parlay UI renders six slots and separate season comparison tables',()=>{
  const states=['regular-season',{}];let i=0;const w={FTBParlay:P,__FTB_PARLAY_DATA__:extra};
  const context=vm.createContext({window:w,React:{createElement:(type,props,...children)=>({type,props,children}),useState:initial=>[states[i++]??initial,()=>{}],useMemo:fn=>fn(),useEffect:()=>{}}});
  vm.runInContext(fs.readFileSync(path.join(base,'parlay_ui.js'),'utf8'),context);
  const tree=w.FTBParlayPanel({A,H,data,supplement:extra,options:{mode:'review',positionReferences:refs},phase:'all',period:0,teams:['SAS','NYK'],fixtures:[{home:'SAS',away:'NYK'}],rosters:regular.snapshot.rosters,acrossStints:false,excludedIds:[],trusted:true});
  const nodes=[];function walk(n){if(!n||typeof n!=='object')return;nodes.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(tree);
  assert.equal(nodes.filter(n=>n.props?.['data-market']).length,6);assert.equal(nodes.filter(n=>n.type==='table').length,6);assert.equal(nodes.filter(n=>n.type==='input').length,4);
  assert.equal(nodes.find(n=>n.type==='select').props.value,'regular-season');
});
test('upcoming first basket remains provisional without confirmed starters',()=>{
  const slots=rank(regular,'SAS','NYK',{upcoming:true,eligibility:{}});
  assert(slots[0].pick.provisional);assert(!slots[0].pick.finalized);
});
test('current starter confirmation can finalize an otherwise eligible first basket',()=>{
  const leader=rank(regular)[0].pick.id;
  const now=Date.parse('2026-10-20T22:00Z'),fixture={id:'future',date:'2026-10-20',home:'SAS',away:'NYK',status:'pre',scheduledTipoff:'2026-10-20T23:00Z'},confirmation={id:leader,nbaId:'123',team:'SAS',position:'C',status:'confirmed',date:fixture.date,fixtureId:fixture.id,source:L.urlFor(fixture.date),capturedAt:new Date(now).toISOString()};
  const slots=rank(regular,'SAS','NYK',{upcoming:true,fixture,now,confirmedStarters:{[leader]:confirmation},eligibility:{[leader]:{provisional:false,reason:'Confirmed available'}}});
  assert.equal(slots[0].pick.id,leader);assert(slots[0].pick.finalized);
});
test('questionable confirmed starters still cannot become final picks',()=>{
  const leader=rank(regular)[0].pick.id;
  const slots=rank(regular,'SAS','NYK',{upcoming:true,confirmedStarters:{[leader]:true},eligibility:{[leader]:{provisional:true,reason:'Questionable'}}});
  assert(!slots[0].pick.finalized);
});
test('availability exclusions apply to all three markets',()=>{
  const ids=rank(regular).map(s=>s.pick.id),eligibility=Object.fromEntries(ids.map(id=>[id,{excluded:true,reason:'DOUBTFUL'}]));
  for(const slot of rank(regular,'SAS','NYK',{upcoming:true,eligibility}))assert(!slot.pick||!ids.includes(slot.pick.id));
});
test('frozen evaluated model and evidence files retain their hashes',()=>{const crypto=require('node:crypto'),e=read('analyst_evaluation.json'),hash=name=>crypto.createHash('sha256').update(fs.readFileSync(path.join(base,name))).digest('hex');assert.equal(hash('analyst.js'),e.modelCodeHash);assert.equal(hash('analyst_data.json'),e.evidenceHash);});
test('parent UI forwards exclusions even when excluded rows are hidden',()=>{
  const report=read('analyst_evaluation.json'),excluded='5104157';
  const states=[data,data,'auto',canonical,report,'parlay','review','2026-06-13','all','0',A.DEFAULT_TARGET,'2025-26',[],'all',{}, {},null,{},null,false,null,'grade',40,{[excluded]:'out'},false,'',Date.now(),'history',null,null,'all-opponents'];let i=0;
  const panel=function ParlayPanel(){},w={__FTB_ANALYST_DATA__:data,__FTB_MERGED__:canonical,__FTB_ANALYST_EVALUATION__:report,FTBAnalyst:A,FTBScoutingHistory:H,FTBParlayPanel:panel,__FTB_PARLAY_DATA__:extra};
  const context=vm.createContext({window:w,React:{createElement:(type,props,...children)=>({type,props,children}),Fragment:'fragment',useState:initial=>[i<states.length?states[i++]:initial,()=>{}],useMemo:fn=>fn(),useEffect:()=>{},useRef:()=>({current:0})},Date,Intl});
  vm.runInContext(fs.readFileSync(path.join(base,'analyst_ui.js'),'utf8'),context);let found;function walk(n){if(!n||typeof n!=='object')return;if(n.type===panel)found=n;for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(w.FTBAnalystApp());assert(found);assert(found.props.excludedIds.includes(excluded));
});
console.log(JSON.stringify({passed:count}));
