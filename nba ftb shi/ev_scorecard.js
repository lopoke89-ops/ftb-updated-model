/* Daily research accounting. Repeated snapshots are not independent bets. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVScorecard=api;})(typeof window==='object'?window:this,function(){
 'use strict';const MARKETS=['points','threes','assists','rebounds','first-team-basket'],OUTCOMES=['win','loss','push','void','pending','review','invalid'];
 const contract=q=>[q.fixtureId,q.playerId,q.market,q.side,q.line].join('|');
 function totals(rows){
  const counts=Object.fromEntries(OUTCOMES.map(k=>[k,0]));let net=0,priced=0;
  for(const r of rows){if(counts[r.statisticalOutcome]===undefined)continue;counts[r.statisticalOutcome]++;
   if(['win','loss','push'].includes(r.statisticalOutcome)&&Number.isFinite(r.illustrativeUnitReturn)){net+=r.illustrativeUnitReturn;priced++;}}
  const decided=counts.win+counts.loss;
  return {selections:rows.length,counts,decisiveHitRate:decided?counts.win/decided:null,illustrativeNetUnits:priced?net:null,illustrativeUnitsAtRisk:priced,illustrativeROI:priced?net/priced:null,unresolved:counts.pending+counts.review+counts.invalid,settlement:'unverified'};
 }
 function grouped(rows,key){return Object.fromEntries([...new Set(rows.map(key))].sort().map(k=>[k,totals(rows.filter(r=>key(r)===k))]));}
 function summarize(records,grading){
  const rows=grading?.results||[],byRecord=new Map();
  for(const r of rows){const key=r.snapshotId||r.snapshotCapturedAt;if(!byRecord.has(key))byRecord.set(key,[]);byRecord.get(key).push(r);}
  const candidates=new Map();
  for(const record of records||[]){
   const selected=byRecord.get(record.id||record.capturedAt)||[];if(!selected.length)continue;
   for(const fixture of record.fixtures||[]){
    if(!(Date.parse(record.capturedAt)<Date.parse(fixture.scheduledTipoff)))continue;
    const rs=selected.filter(r=>r.quote?.fixtureId===fixture.id&&MARKETS.includes(r.quote?.market));if(!rs.length)continue;
    const complete=record.filters?.selection==='all supported offers before display filters',key=fixture.date+'|'+fixture.id,prior=candidates.get(key);
    if(!prior||Number(complete)>Number(prior.complete)||complete===prior.complete&&record.capturedAt>prior.record.capturedAt)candidates.set(key,{record,rows:rs,complete,fixture});
   }
  }
  const dates=[...new Set([...candidates.values()].map(c=>c.fixture.date))].sort(),days=dates.map(date=>{
   const captures=[...candidates.values()].filter(c=>c.fixture.date===date),rs=captures.flatMap(c=>c.rows),displayed=rs.filter(r=>r.displayed===true),ids=[...new Set(captures.map(c=>c.record.id||c.record.capturedAt))],last=captures.reduce((a,b)=>a.record.capturedAt>b.record.capturedAt?a:b);
   const selections=captures.flatMap(c=>c.rows.filter(r=>r.displayed===true).map(r=>{const original=c.record.results?.find(x=>x.quote?.key===r.quote.key)||{};return {snapshotId:c.record.id,capturedAt:c.record.capturedAt,quote:r.quote,outcome:r.statisticalOutcome,reason:r.reason,modelVersion:r.modelVersion,originalProvisional:original.provisional??null,availability:original.availability||null,lineupBasis:original.lineupBasis||null,frozenLineup:original.projectedLineup||original.confirmedLineup||null,historicalMinutes:original.features?.minutes??null,fixtureIdentityReview:r.fixtureIdentityReview||null};}));
   const snapshots=captures.map(c=>({fixtureId:c.fixture.id,snapshotId:c.record.id||null,capturedAt:c.record.capturedAt,filters:c.record.filters||null,completeSupportedUniverse:c.complete}));
   return {date,selections,primarySnapshotId:ids.length===1?last.record.id||null:null,capturedAt:last.record.capturedAt,snapshots,filters:ids.length===1?last.record.filters||null:null,modelVersions:[...new Set(rs.map(r=>r.modelVersion).filter(Boolean))],universe:'Latest saved supported pregame snapshot per fixture; '+captures.length+' fixtures. '+(captures.every(c=>c.complete)?'Full supported universes recorded.':'Some fixtures have visible-only saved universes.'),allSupported:totals(rs),displayed:totals(displayed),byMarket:grouped(displayed,r=>r.quote.market),byMarketAndBetType:grouped(displayed,r=>r.quote.market+' / '+r.quote.side)};
  });
  const unique=new Map(),everDisplayed=new Map();
  for(const r of [...rows].sort((a,b)=>(a.snapshotCapturedAt||'').localeCompare(b.snapshotCapturedAt||''))){if(!MARKETS.includes(r.quote?.market))continue;unique.set(contract(r.quote),r);if(r.displayed===true)everDisplayed.set(contract(r.quote),r);}
  return {version:'ev-daily-research-scorecard-v1',days,allSavedUniqueContracts:totals([...unique.values()]),everDisplayedUniqueContracts:totals([...everDisplayed.values()]),interpretation:'Primary daily view prefers the latest saved full supported-offer pregame snapshot for each fixture, preserving earlier-game records when later snapshots show only another game. Filters and timestamp are preserved. Other snapshots are appendices, not extra bets. One illustrative unit per acted selection at its recorded odds; pushes count as action with zero profit, voids have zero action, pending/review/invalid are excluded from returns and never losses. Editable browser research is not authenticated issuance or account settlement. Same-game picks and alternate lines are correlated. No combined-parlay EV.'};
 }
 return {MARKETS,OUTCOMES,contract,totals,summarize};
});
