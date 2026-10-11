'use strict';
const assert=require('node:assert/strict'),P=require('../parlay.js'),H=require('../scouting_history.js'),T=require('../parlay_transition.js'),R=require('../parlay_research.js');
const A=require('../analyst.js'),data=require('../analyst_data.json'),extra=require('../parlay_data.json'),config=require('../parlay_research_config.json');
let passed=0;const test=(name,fn)=>{fn();passed++;console.log('PASS '+name);};
const prior=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',positionScope:'broad'});
const rank=m=>P.rankPositionVariants({specific:m,broad:m},{team:'SAS',opponent:'NYK',roster:prior.snapshot.rosters.SAS,seasonScope:m.scope,minimumGames:{'first-team-basket':5,points:10,threes:10}},'broad').map(s=>P.applySelectionPolicy(s,{scope:m.scope,minimumGames:s.market==='first-team-basket'?5:10,minimumTeamGames:s.market==='threes'?10:5}));
const archive=rank(prior),empty=P.build(A,H,{...data,meta:{...data.meta,season:'2026-27'},games:[]},extra,{mode:'review',phase:'regular-season',positionScope:'broad'});
const current=rank(empty),pointArchive=archive[1],id=pointArchive.pick.id;
function experiment(m=empty,c=rank(m)){return R.rank({archive:pointArchive,current:c[1],model:m,full:m,config,competition:'regular-season',firstBasketTarget:P.FIRST_TARGETS[0]});}
test('zero-season progress is distinct from qualifying archive selection',()=>{
  const slot={...pointArchive,evidenceSeason:'2025-26'},t=T.detail(slot,current[1],empty,empty,false);
  assert.equal(t.descriptive.gp,0);assert.equal(t.filtered.gp,0);assert.equal(t.teamGames,0);assert(!t.currentReady);assert.equal(t.targetBasis.season,'2025-26');
});
test('archive player progress cannot veto a different current candidate',()=>{
  const next={...current[1],pick:{id:'new',name:'Current contender',stats:{gp:10}}};
  const state={ready:true,requiredPlayerGames:10};const chosen=P.selectMarketEvidence(next,pointArchive,state);
  assert.equal(chosen.pick.id,'new');const t=T.detail({...pointArchive,evidenceSeason:'2025-26'},next,empty,empty,false);
  assert.equal(t.currentCandidate.id,'new');assert.equal(t.filtered.gp,0);
});
test('refresh distinguishes new games corrections duplicates context and eligibility',()=>{
  const slots=[{team:'SAS',opponent:'NYK',market:'points',pick:{id:'1',score:10},evidenceSeason:'2025-26'}];
  const payload=(hash,games)=>({meta:{season:'2026-27',evidenceContentHash:hash},games});
  const a=T.capture(slots,payload('a',[]),'fixture');assert(T.changes(null,a)['SAS|points'].includes('loaded'));
  const b=T.capture(slots,payload('b',[{id:'1',home:'SAS',away:'BOS',sourceHash:'x'}]),'fixture');
  assert(T.changes(a,b)['SAS|points'].includes('1 verified'));assert(T.changes(b,b)['SAS|points'].includes('No new'));
  const c=T.capture(slots,payload('c',[{id:'1',home:'SAS',away:'BOS',sourceHash:'y'}]),'fixture');assert(T.changes(b,c)['SAS|points'].includes('correction'));
  assert(T.changes(c,{...c,context:'other'})['SAS|points'].includes('context'));
  const unrelated=T.capture(slots,payload('d',[...c.games?Object.entries(c.games).map(([id,g])=>({id,home:g.teams[0],away:g.teams[1],sourceHash:g.hash})):[],{id:'2',home:'LAL',away:'DAL',sourceHash:'z'}]),'fixture');
  assert(T.changes(c,unrelated)['SAS|points'].includes('outside these teams'));
});
test('old exports recover without becoming verified pregame records',()=>{const r=T.normalizeExport({schemaVersion:2,recordedAt:'2026-01-01',selections:[]});assert.equal(r.schemaVersion,3);assert.equal(r.verifiedIssuedAt,null);assert.throws(()=>T.normalizeExport({schemaVersion:99,selections:[]}));});
test('fitted experiment is deterministic and off by default',()=>{assert.equal(config.defaultEnabled,false);assert(config.configurationHash);assert.deepEqual(experiment(),experiment());assert(experiment().pick);assert(experiment().ranked.every(p=>p.currentGames===0&&!p.currentProductionEligible));});
test('common position resolution cannot change a candidate target eligibility basis',()=>{
  const fakeTarget={average:99.2,threshold:100,n:10,hits:0,rate:0};
  const common={...current[1],selectionReview:{coverageReady:true,sampleReady:true},ranked:[{...pointArchive.pick,seasonTarget:fakeTarget}]};
  const e=R.rank({archive:pointArchive,current:common,productionCurrent:current[1],model:empty,full:empty,config,competition:'regular-season',firstBasketTarget:P.FIRST_TARGETS[0]});
  const p=e.ranked.find(p=>p.id===id);assert(!p.currentProductionEligible);assert.deepEqual(p.seasonTarget,pointArchive.pick.seasonTarget);
});
test('one real observation updates estimates without fabricating current eligibility',()=>{
  const game=data.games.find(g=>g.teams.SAS?.players.some(p=>p.id===id&&p.played));
  const m=P.build(A,H,{...data,meta:{...data.meta,season:'2026-27'},games:[game]},extra,{mode:'review',phase:'regular-season',positionScope:'broad'});
  const before=experiment(),after=experiment(m),b=before.ranked.find(p=>p.id===id),a=after.ranked.find(p=>p.id===id);
  assert(a);assert.equal(a.currentGames,1);assert(!a.currentProductionEligible);assert.equal(a.estimates.attempts.currentN,1);assert(a.estimates.attempts.currentWeight>0);assert.equal(a.correlationBasis,'2025-26');assert.equal(a.targetBasis.season,'2025-26');assert.equal(a.estimates.conversion.currentN,a.currentStats.total.fga);
  assert.equal(a.estimates.attempts.value,(b.estimates.attempts.value*a.estimates.attempts.priorEquivalent+a.currentStats.total.fga)/(a.estimates.attempts.priorEquivalent+1));
});
test('five undefined current pairs do not hide behind positive historical correlation',()=>{
  const row=pointArchive.pick.rows[0],rows=Array.from({length:5},(_,i)=>({...row,gameId:'synthetic-'+i,fga:10,fgm:5,points:10,threeMade:0,threeAttempted:0,ftm:0,fta:0}));
  const m={...empty,scope:{...empty.scope,byPlayer:{[id]:{all:rows,teams:{SAS:rows},appearances:5,missing:0}}}};
  assert(!experiment(m).ranked.some(p=>p.id===id));
});
test('unsupported playoffs and inadequate current positional evidence withhold research',()=>{
  assert(!R.rank({archive:pointArchive,current:current[1],model:empty,config,competition:'playoffs'}).pick);
  const m={...empty,scope:{...empty.scope,byTeam:{SAS:{totals:{points:100},points:{unknown:30}}}}};assert(!experiment(m).pick);
});
test('research has no side effects on production selections or raw season facts',()=>{
  const fingerprint=()=>JSON.stringify(archive.map(s=>({id:s.pick?.id,score:s.pick?.score,ranked:s.ranked.map(p=>({id:p.id,score:p.score,components:p.components,target:p.seasonTarget}))})));
  const before=fingerprint();experiment();assert.equal(fingerprint(),before);
  assert.equal(P.summarize(pointArchive.pick.rows).ppg,pointArchive.pick.stats.ppg);
});
console.log(JSON.stringify({passed}));
