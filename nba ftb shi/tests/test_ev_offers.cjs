'use strict';
const assert=require('node:assert/strict'),O=require('../ev_offers.js'),V=require('../ev_service.js');
const now=Date.parse('2026-11-11T21:00:00Z'),f={id:'1',phase:'regular-season',status:'pre',home:'IND',away:'WAS',scheduledTipoff:'2026-11-12T00:00:00Z'};
function quote(market,line,label){
 const type=market==='points'?'TO_SCORE_'+line+'+_POINTS':market==='threes'?line+'+_MADE_THREES':'TO_RECORD_'+line+'+_'+market.toUpperCase();
 return {fixtureId:'1',fanduelEventId:'123',fanduelTipoff:f.scheduledTipoff,marketId:'747.1',selectionId:'2',playerId:'3',player:'Example Player',team:'IND',market,marketType:type,marketName:label,period:'full-game',side:'at-least',line,american:100,decimal:2,region:'TN',capturedAt:new Date(now).toISOString(),marketStatus:'OPEN',runnerStatus:'ACTIVE',captureState:'fresh',source:'https://sportsbook.fanduel.com/basketball/nba/game-123?tab=player-'+market,key:['123','747.1','2',line,'at-least'].join('|')};
}
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
test('observed label aliases preserve source quotes and pass unchanged full contract guards',()=>{
 for(const [m,n,short,old]of [['points',20,'20+ Points','To Score 20+ Points'],['threes',3,'3+ Threes','3+ Made Threes'],['assists',6,'6+ Assists','To Record 6+ Assists'],['rebounds',8,'8+ Rebounds','To Record 8+ Rebounds']]){
  const q=quote(m,n,short),before=JSON.stringify(q);assert.equal(V.offerError(q,f,now),'Milestone type/threshold mismatch');assert.equal(O.offerError(q,f,now),null);assert.equal(JSON.stringify(q),before);assert.equal(O.offerError({...q,marketName:old},f,now),null);
 }
});
test('wrong targets, periods, source tabs, identities, stale and suspended aliases remain rejected',()=>{
 const q=quote('points',20,'20+ Points');
 for(const change of [{marketName:'15+ Points'},{marketName:'20+ Rebounds'},{marketName:'20+ Points First Half'},{marketType:'TO_SCORE_25+_POINTS'},{period:'first-half'},{source:q.source.replace('player-points','player-rebounds')},{selectionId:'99'},{marketStatus:'SUSPENDED'},{capturedAt:new Date(now-300001).toISOString()}])assert(O.offerError({...q,...change},f,now),JSON.stringify(change));
 assert.equal(O.availability,V.availability);
});
test('screening retains exact original quote objects and reports rejected contracts',()=>{
 const q=Object.freeze(quote('points',20,'20+ Points')),bad={...q,marketName:'25+ Points'},snapshot={schemaVersion:1,bookmaker:'fanduel',region:'TN',checkedAt:new Date(now).toISOString(),fixtures:{1:{fixture:f,quotes:[q,bad]}}};
 const result=O.screenSnapshot(snapshot,[f],now);assert.equal(result.snapshot.fixtures[1].quotes.length,1);assert.equal(result.snapshot.fixtures[1].quotes[0],q);assert.equal(result.audit.length,1);assert.equal(snapshot.fixtures[1].quotes.length,2);
});
test('coverage distinguishes missing offers from captured offers failing freshness',()=>{
 const q=quote('points',20,'20+ Points'),snapshot={fixtures:{1:{quotes:[q]}}},predicate=q=>q.side==='at-least';
 assert.equal(O.coverage(null,[f],now,predicate).offered.length,0);assert.equal(O.coverage(snapshot,[f],now,predicate).fresh.length,1);const stale=O.coverage(snapshot,[f],now+300001,predicate);assert.equal(stale.offered.length,1);assert.equal(stale.fresh.length,0);
});
test('FTB retains exact team-first target; game-first scorers are never substituted',()=>{
 const q={...quote('points',20,'20+ Points'),market:'first-team-basket',marketType:'FIRST_TEAM_BASKET_SCORER',marketName:'First Team Basket Scorer',period:'team-first-score',side:'yes',line:null,scoringDefinition:'first-team-score-including-free-throws',settlement:'starter-required',source:'https://sportsbook.fanduel.com/basketball/nba/game-123?tab=quick-bets',key:'123|747.1|2|None|yes'};
 assert.equal(O.offerError(q,f,now),null);for(const change of [{marketType:'FIRST_BASKET_SCORER'},{marketName:'First Basket'},{scoringDefinition:'field-goals-only'}])assert(O.offerError({...q,...change},f,now));
});
test('FTB history is descriptive same-team counts, separate from probabilities and model release',()=>{
 const q={team:'IND',playerId:'3'},state={players:{'IND|3':{starts:25,wins:6,history:[{date:'2026-11-10',season:'2026-27'}]},'WAS|3':{starts:50,wins:40,history:[]}}},before=JSON.stringify(state),r=O.firstTeamHistory(state,q);
 assert.equal(r.starts,25);assert.equal(r.wins,6);assert.equal(r.through,'2026-11-10');assert.equal(r.probability,undefined);assert.equal(r.ev,undefined);assert.equal(JSON.stringify(state),before);assert.equal(O.firstTeamHistory(null,q).status,'unavailable');assert.equal(require('../ev_first_team_model.json').enabled,false);
});
console.log(JSON.stringify({passed:count}));
