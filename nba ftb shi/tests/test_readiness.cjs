'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=path.resolve(__dirname,'..'),A=require('../analyst.js'),H=require('../scouting_history.js'),P=require('../parlay.js'),L=require('../lineups.js');
const data=JSON.parse(fs.readFileSync(base+'/analyst_data.json')),extra=JSON.parse(fs.readFileSync(base+'/parlay_data.json'));
const canonical=JSON.parse(fs.readFileSync(base+'/merged_dataset.json')),refs=Object.fromEntries(Object.values(canonical.players).map(p=>[p.sourcePlayerId,{position:p.position}]));
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
const empty={meta:{season:'2026-27',asOfDate:null},games:[]},options={season:'2026-27',date:'2026-10-20',mode:'upcoming',archiveTrusted:true,phase:'regular-season',positionReferences:refs};
test('one game for unrelated teams cannot change a selected matchup history',()=>{
  const g=data.games[0],current=A.snapshot({...empty,games:[{...g,date:'2026-10-19'}]},{date:options.date,mode:'pregame'});
  const selection=H.selectEvidence(A,current,data,{...options,team:'NYK',opponent:'PHI'});
  assert(selection.isArchive);assert.equal(selection.readiness.teamGames,0);assert.equal(selection.season,'2025-26');
});
test('readiness is specific to the selected team, opponent, competition and current player sample',()=>{
  const current=H.snapshotForScope(A,data,{mode:'review',phase:'regular-season'}),state=H.readiness(current,'NYK','PHI');
  assert(state.ready);assert(!H.readiness(current,'NYK','NEW').ready);
  assert(!H.readiness({...current,rosters:{NYK:[{id:'rookie'}]}},'NYK','PHI').ready);
  const selection=H.selectEvidence(A,current,data,{...options,team:'NYK',opponent:'PHI'});assert(!selection.isArchive);
});
test('market fallback retains separate seasons and honors explicit current and archive controls',()=>{
  const current={pick:{id:'new',stats:{gp:5}},ranked:[],reason:null},archive={pick:{id:'old',stats:{gp:80}}},state={ready:true,requiredPlayerGames:8};
  assert.equal(P.selectMarketEvidence(current,archive,state).pick.id,'old');
  assert.equal(P.selectMarketEvidence(current,archive,state,'current').pick,null);
  assert.equal(P.selectMarketEvidence({...current,pick:{id:'ready',stats:{gp:8}}},archive,state).pick.id,'ready');
  assert.equal(P.selectMarketEvidence(current,archive,state,'archive').pick.id,'old');
});
test('head-to-head without meetings never substitutes broader history',()=>{
  const s=H.selectEvidence(A,A.snapshot(empty,{date:options.date}),data,{...options,team:'NYK',opponent:'PHI',historyMatchups:[{home:'NYK',away:'FAKE'}]});
  assert(s.isArchive);assert.equal(s.snapshot.games.length,0);assert(!H.playerEvidence(s.snapshot,'3934672','NYK',true).hasHistory);
});
test('Diawara conditional starting rate is capped and penalized in actual Parlay ranking',()=>{
  const model=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',positionReferences:refs});
  const slot=P.rankTeam({team:'NYK',opponent:'SAS',roster:model.snapshot.rosters.NYK,snapshot:model.snapshot,sample:model.scope})[0];
  const player=H.playerEvidence(model.snapshot,'5289900','NYK'),quality=H.firstBasketQuality(player,H.gradeContext(model.snapshot));
  assert(quality.rated);assert(quality.rawRate>.5);assert(quality.share<.06);assert(quality.factor<.3);assert.notEqual(slot.pick?.id,'5289900');
  const ranked=slot.ranked.find(p=>p.id==='5289900');if(ranked){assert.equal(ranked.firstQuality.score,quality.score);assert(ranked.score<ranked.rawScore*.3);}else assert(slot.audit.some(p=>p.id==='5289900'));
});
test('first field-goal scoring safeguard uses the field-goal definition',()=>{
  const model=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',positionReferences:refs,firstBasketTarget:P.FIRST_TARGETS[1]});
  const p=H.playerEvidence(model.snapshot,'5104157','SAS'),q=H.firstBasketQuality(p,H.gradeContext(model.snapshot));
  assert(q.rated);assert.equal(q.shareNumerator,p.scoutingDetail.ftbMade);assert(q.score<=q.share);
});
test('head-to-head Picks and Parlay use the same league grade baseline',()=>{
  const model=P.build(A,H,data,extra,{mode:'review',phase:'regular-season',positionReferences:refs,historyMatchups:[{home:'NYK',away:'SAS'}]});
  const broader=H.snapshotForScope(A,data,{mode:'review',phase:'regular-season',positionReferences:refs});
  assert.equal(H.gradeContext(model.snapshot).baseline,H.gradeContext(broader).baseline);
  for(const slot of P.rankTeam({team:'NYK',opponent:'SAS',roster:model.snapshot.rosters.NYK,snapshot:model.snapshot,sample:model.scope}))for(const p of slot.ranked)if(slot.market==='first-team-basket')assert.equal(p.firstQuality.score,H.historicalGrade(H.playerEvidence(model.snapshot,p.id,'NYK'),H.gradeContext(model.snapshot)).score);
});
const now=Date.parse('2026-10-20T22:00Z'),fixture={id:'fixture',date:'2026-10-20',home:'NYK',away:'PHI',status:'pre',scheduledTipoff:'2026-10-20T23:00Z'};
const players=L.POS.map((position,i)=>({personId:100+i,playerName:'Player '+i,position,lineupStatus:'Confirmed',rosterStatus:'Active',timestamp:'2026-10-20T17:55:00'}));
const rosters={NYK:players.map((p,i)=>({id:String(500+i),name:p.playerName})),PHI:[]},payload={games:[{gameId:'0022600001',gameStatus:1,homeTeam:{teamAbbreviation:'NYK',players},awayTeam:{teamAbbreviation:'PHI',players:[]}}]};
const context={date:fixture.date,fixtures:[fixture],rosters,capturedAt:new Date(now).toISOString(),now};
test('NBA explicit confirmed active five-position lineup retains source and time',()=>{
  const parsed=L.parse(payload,context);assert.equal(Object.keys(parsed.confirmed).length,5);const p=parsed.confirmed['500'];
  assert(L.validConfirmation(p,fixture,now));assert.equal(p.sourceTimestamp,players[0].timestamp);assert.equal(p.source,L.urlFor(fixture.date));
});
test('expected, incomplete, ambiguous and postgame lineups never confirm starters',()=>{
  const expected=structuredClone(payload);expected.games[0].homeTeam.players[0].lineupStatus='Expected';assert.equal(Object.keys(L.parse(expected,context).confirmed).length,0);assert.equal(Object.keys(L.parse(expected,context).projected).length,5);
  const final=structuredClone(payload);final.games[0].gameStatus=3;assert.equal(Object.keys(L.parse(final,context).confirmed).length,0);
  const missing=structuredClone(payload);missing.games[0].homeTeam.players.pop();assert.equal(Object.keys(L.parse(missing,context).confirmed).length,0);
  const ambiguous={...rosters,NYK:[...rosters.NYK,{id:'other',name:'Player 0'}]};assert.equal(Object.keys(L.parse(payload,{...context,rosters:ambiguous}).confirmed).length,0);
});
test('stale, future, other-fixture, assumed and after-tipoff records cannot finalize',()=>{
  const p=L.parse(payload,context).confirmed['500'];assert(!L.validConfirmation(p,fixture,now+300001));assert(!L.validConfirmation(p,fixture,now-1));assert(!L.validConfirmation(p,{...fixture,id:'other'},now));assert(!L.validConfirmation(true,fixture,now));assert(!L.validConfirmation(p,fixture,Date.parse(fixture.scheduledTipoff)));assert(!L.validConfirmation({...p,status:'projected'},fixture,now));
});
test('fresh NBA active-starter evidence explicitly clears Questionable while Out stays excluded',()=>{
  const confirmed=L.parse(payload,context).confirmed,injuries={'500':{status:'QUESTIONABLE'},'501':{status:'OUT'}};
  const merged=L.availableInjuries(injuries,confirmed,fixture,now);assert.equal(merged['500'].status,'AVAILABLE');assert.equal(merged['501'].status,'OUT');assert.equal(injuries['500'].status,'QUESTIONABLE');
  assert.equal(L.availableInjuries(injuries,confirmed,fixture,now+300001)['500'].status,'QUESTIONABLE');
});
test('future results cannot alter earlier Parlay rankings or averages',()=>{
  const date='2026-01-01',build=d=>P.build(A,H,d,extra,{mode:'pregame',date,phase:'regular-season'});
  const a=build(data),b=build({...data,games:data.games.filter(g=>g.date<date)});
  for(const team of ['NYK','PHI']){const args=m=>({team,opponent:team==='NYK'?'PHI':'NYK',roster:m.snapshot.rosters[team],snapshot:m.snapshot,sample:m.scope});const x=P.rankTeam(args(a)),y=P.rankTeam(args(b));assert.deepEqual(x.map(s=>s.pick?.id),y.map(s=>s.pick?.id));assert.deepEqual(x.map(s=>s.pick?.stats.ppg),y.map(s=>s.pick?.stats.ppg));}
});
console.log(JSON.stringify({passed:count}));
