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
test('coarse positions preserve gamebook groups without guessing finer roles',()=>{
  for(const [role,group] of [['PG','G'],['SG','G'],['G','G'],['SF','F'],['PF','F'],['F','F'],['C','C'],['F-C','unknown'],['G-F','unknown']])assert.equal(P.positionGroup({rawPosition:role},'broad'),group);
  assert.equal(P.positionGroup({position:'SG',rawPosition:'F'},'broad'),'F');
});
test('automatic position comparisons fall back per market for both teams and keep strict mode',()=>{
  const broad=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',positionReferences:refs,positionScope:'broad'}),pair={specific:regular,broad},args={team:'SAS',opponent:'OKC',roster:regular.snapshot.rosters.SAS,minimumGames:10};
  const auto=P.rankPositionVariants(pair,args),strict=P.rankPositionVariants(pair,args,'specific'),forced=P.rankPositionVariants(pair,args,'broad');
  assert.equal(auto[0].positionScope,'specific');
  for(const i of [1,2]){assert.equal(auto[i].positionScope,'broad');assert(auto[i].positionFallbackReason.includes('for both teams'));assert(auto[i].ranked.every(p=>['G','F','C'].includes(p.group)));assert(P.applySelectionPolicy(auto[i],{scope:broad.scope,minimumGames:10}).pick);assert(!P.applySelectionPolicy(strict[i],{scope:regular.scope,minimumGames:10}).pick);}
  assert(forced.every(s=>s.positionScope==='broad'));
  for(const t of Object.values(broad.scope.byTeam))for(const field of ['points','allowedPoints','threes','allowedThrees'])assert(Object.keys(t[field]).every(p=>['G','F','C','unknown'].includes(p)));
  assert.throws(()=>P.rankPositionVariants(pair,args,'invalid'));
});
test('G/F/C comparisons preserve pregame cutoffs and the same shooting totals',()=>{
  const options={mode:'pregame',date:'2026-01-01',phase:'regular-season'},fine=P.build(A,H,data,extra,options),broad=P.build(A,H,data,extra,{...options,positionScope:'broad'});
  assert(broad.snapshot.games.every(g=>g.date<options.date));
  for(const team of Object.keys(fine.scope.byTeam))assert.deepEqual(broad.scope.byTeam[team].totals,fine.scope.byTeam[team].totals);
  for(const id of Object.keys(fine.scope.byPlayer))assert.deepEqual(P.summarize(broad.scope.byPlayer[id].all),P.summarize(fine.scope.byPlayer[id].all));
});
test('Parlay UI renders six slots and separate season comparison tables',()=>{
  const states=['regular-season',{}];let i=0;const w={FTBParlay:P,FTBParlayTransition:require('../parlay_transition.js'),__FTB_PARLAY_DATA__:extra};
  const context=vm.createContext({window:w,React:{createElement:(type,props,...children)=>({type,props,children}),useState:initial=>[states[i++]??initial,()=>{}],useMemo:fn=>fn(),useEffect:()=>{},useRef:()=>({current:null})}});
  vm.runInContext(fs.readFileSync(path.join(base,'parlay_ui.js'),'utf8'),context);
  const tree=w.FTBParlayPanel({A,H,data,supplement:extra,options:{mode:'review',positionReferences:refs},phase:'all',period:0,teams:['SAS','NYK'],fixtures:[{home:'SAS',away:'NYK'}],rosters:regular.snapshot.rosters,acrossStints:false,excludedIds:[],trusted:true});
  const nodes=[];function walk(n){if(!n||typeof n!=='object')return;nodes.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(tree);
  assert.equal(nodes.filter(n=>n.props?.['data-market']).length,6);
  assert.equal(nodes.filter(n=>n.type==='summary'&&n.children[0]==='Compare market candidates').length,6);
  const selectedCards=nodes.filter(n=>n.props?.className==='player-name parlay-player-name').length;
  assert.equal(nodes.filter(n=>n.type==='caption'&&String(n.children[0]).includes('season averages')).length,selectedCards);
  assert(nodes.filter(n=>n.type==='input'&&n.props?.type==='number').length<=4);
  const researchControl=nodes.find(n=>n.type==='input'&&n.props?.type==='checkbox');assert(researchControl);assert.equal(researchControl.props.checked,false);assert.equal(researchControl.props.disabled,true);
  assert.equal(nodes.find(n=>n.type==='select').props.value,'regular-season');
  const positions=nodes.find(n=>n.props?.['aria-label']==='Position comparison');assert.equal(positions.props.value,'auto');assert.equal(positions.children.length,3);
  assert(nodes.some(n=>n.type==='strong'&&n.children[0]==='G/F/C comparison'));
});
test('upcoming research cards qualify historical evidence and unconfirmed lineups without changing selection rules',()=>{
  const w={FTBParlay:P,FTBParlayTransition:require('../parlay_transition.js'),__FTB_PARLAY_DATA__:extra};
  const context=vm.createContext({window:w,React:{createElement:(type,props,...children)=>({type,props,children}),useState:value=>[value,()=>{}],useMemo:fn=>fn(),useEffect:()=>{},useRef:()=>({current:null})}});
  vm.runInContext(fs.readFileSync(path.join(base,'parlay_ui.js'),'utf8'),context);
  const current={meta:{season:'2026-27',asOfDate:null},games:[]},fixture={id:'future',home:'SAS',away:'NYK',date:'2026-10-20',scheduledTipoff:'2026-10-21T01:30Z',status:'pre',phase:'regular-season'},tree=w.FTBParlayPanel({A,H,data:current,supplement:{games:{}},archiveData:data,archiveSupplement:extra,options:{mode:'upcoming',date:fixture.date,positionReferences:refs},phase:'all',period:0,teams:['SAS','NYK'],fixtures:[fixture],rosters:regular.snapshot.rosters,acrossStints:false,excludedIds:[],trusted:true,liveContext:{upcoming:true,date:fixture.date,today:fixture.date,now:Date.parse('2026-10-20T15:00Z'),fresh:true,injuries:{}}});
  const cards=[];function visit(n){if(!n||typeof n!=='object')return;if(n.props?.className==='analyst-notice research-readiness')cards.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(visit):visit(c);}visit(tree);
  assert(cards.length>0);const text=JSON.stringify(cards);assert.match(text,/Prior-season evidence · lineup unconfirmed/);assert.match(text,/Research eligible/);assert.match(text,/Provisional research/);assert(!text.includes('NBA-confirmed starter'));assert(!text.includes('Eligible selection'));
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

test('unsupported positions cannot set the opportunity scale for eligible players',()=>{
  const original=rank(regular),fake='unresolved-high-volume';
  const rows=Array.from({length:5},(_,i)=>({points:200+i*2,fga:200+i,fgm:100+i,threeMade:0,threeAttempted:0,ftm:0,fta:0,minutes:100}));
  const model={...regular,snapshot:{...regular.snapshot,players:{...regular.snapshot.players,[fake]:{position:'?',rawPosition:'G',ftbByTeam:{}}}},scope:{...regular.scope,byPlayer:{...regular.scope.byPlayer,[fake]:{all:rows,teams:{SAS:rows}}}}};
  const after=rank(model,'SAS','NYK',{roster:[...regular.snapshot.rosters.SAS,{id:fake,name:'Unknown guard',rawPosition:'G'}]});
  for(let i=0;i<3;i++){assert.deepEqual(after[i].ranked.map(p=>[p.id,p.score]),original[i].ranked.map(p=>[p.id,p.score]));assert(after[i].audit.some(p=>p.id===fake));}
});

test('market-specific appearance limits apply to archived and review candidates',()=>{
  for(const team of Object.keys(regular.snapshot.rosters))for(const slot of rank(regular,team,team==='SAS'?'NYK':'SAS',{minimumGames:{'first-team-basket':5,points:5,threes:8}}))
    assert(slot.ranked.every(p=>p.stats.gp>=(slot.market==='threes'?8:5)));
});

test('partial pregame position coverage withholds the center-only market leaders',()=>{
  const m=P.build(A,H,data,{...extra,roleEvidenceMeta:null,datedRoleEvidence:[]},{mode:'pregame',date:'2026-01-01',phase:'regular-season'});
  const slots=rank(m,'OKC','NYK');assert(slots.every(s=>s.pick));assert.equal(new Set(slots.map(s=>s.pick.id)).size,1);
  for(const slot of slots){const reviewed=P.applySelectionPolicy(slot,{scope:m.scope,minimumGames:slot.market==='threes'?8:5,rosterSize:m.snapshot.rosters.OKC.length});assert(!reviewed.pick);assert(!reviewed.selectionReview.coverageReady);assert(reviewed.ranked.length>0);assert(reviewed.reason.includes('positional coverage'));}
});

test('NBA/PDF matched roles restore dated guards and wings without changing season stats',()=>{
  assert.equal(extra.datedRoleEvidence.length,13210);assert.equal(extra.roleEvidenceMeta.matchedTeamGames,2642);
  const m=P.build(A,H,data,extra,{mode:'pregame',date:'2026-01-01',phase:'regular-season'});
  const slots=rank(m,'OKC','NYK');assert(slots[1].ranked.some(p=>['PG','SG'].includes(p.group)));assert(slots[2].ranked.some(p=>['SF','PF'].includes(p.group)));
  assert(slots[1].ranked.length>2);assert(m.scope.byTeam.OKC.points.unknown/m.scope.byTeam.OKC.totals.points<.2);
  for(const p of Object.values(m.snapshot.players)){const date=p.positionSource.match(/\((\d{4}-\d{2}-\d{2})\)/)?.[1];if(date)assert(date<'2026-01-01');}
  const wrong=P.build(A,H,data,{...extra,roleEvidenceMeta:{...extra.roleEvidenceMeta,parentEvidenceContentHash:'wrong'}},{mode:'pregame',date:'2026-01-01',phase:'regular-season'});
  assert.equal(wrong.snapshot.roleRecords,data.datedRoleEvidence.length);
});

test('selection guard uses each market production and does not force distinct names',()=>{
  const own={points:{unknown:10},threes:{unknown:1},first:{unknown:1},totals:{points:100,threes:10,first:10}},opp={allowedPoints:{unknown:10},allowedThrees:{unknown:1},allowedFirst:{unknown:1},totals:{allowedPoints:100,allowedThrees:10,allowedFirst:10}};
  const scope={byTeam:{AAA:own,BBB:opp}},p={id:'same',name:'Supported player',stats:{gp:20}};
  const slots=P.MARKETS.map(market=>P.applySelectionPolicy({team:'AAA',opponent:'BBB',market,pick:p,ranked:[p],audit:[]},{scope,minimumGames:market==='threes'?8:5,rosterSize:5}));
  assert(slots.every(s=>s.pick.id==='same'&&s.selectionReview.coverageReady));
  const sparse=structuredClone(scope);sparse.byTeam.BBB.allowedThrees.unknown=3;
  assert(!P.applySelectionPolicy({...slots[2],pick:p},{scope:sparse}).pick);
  assert(P.applySelectionPolicy({...slots[1],pick:p},{scope:sparse}).pick);
});

test('selection guard never restores withheld picks and reports insufficient player samples',()=>{
  const scope={byTeam:{AAA:{points:{},totals:{points:10}},BBB:{allowedPoints:{},totals:{allowedPoints:10}}}},p={id:'one',name:'Player',stats:{gp:6}};
  const slot={team:'AAA',opponent:'BBB',market:'points',pick:p,ranked:[p],audit:[]};
  const tooSmall=P.applySelectionPolicy(slot,{scope,minimumGames:8});assert(!tooSmall.pick);assert(tooSmall.audit[0].reason.includes('8 appearances'));
  const withheld=P.applySelectionPolicy({...slot,pick:null,reason:'Current evidence not ready'},{scope});assert(!withheld.pick);assert.equal(withheld.reason,'Current evidence not ready');
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
