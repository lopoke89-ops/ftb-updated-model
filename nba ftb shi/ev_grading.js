/* PDF-based research outcomes. Never a sportsbook account settlement or verified issuance receipt. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVGrading=api;})(typeof window==='object'?window:this,function(){
 'use strict';
 const VERSION='ev-research-grading-v1';
 function finalError(g){
  if(g.boxScoreSource!=='NBA official final box'||!/^https:\/\/(?:statsdmz|stats)\.nba\.com\/pdfs\//.test(g.source||'')||!/^[a-f0-9]{64}$/.test(g.sourceHash||''))return 'Verified NBA PDF final box unavailable';
  const ids=new Set();for(const team of [g.home,g.away]){const box=g.teams?.[team];if(!box||!Array.isArray(box.players))return 'Final team box missing';const ps=box.players.filter(p=>p.played===true);
   if(ps.filter(p=>p.starter).length!==5||ps.reduce((n,p)=>n+p.points,0)!==box.points)return 'Final score or starters do not reconcile';
   const seconds=ps.reduce((n,p)=>n+p.minutesSeconds,0),overtime=(seconds-14400)/1500;
   if(!Number.isFinite(seconds)||seconds<14395||Math.abs(overtime-Math.round(overtime))*1500>5)return 'Full-game playing time is not verified; incomplete games require review';
   for(const p of ps){if(ids.has(String(p.id)))return 'Duplicate final player identity';ids.add(String(p.id));
    if(p.statsSourceHash!==g.sourceHash||['points','fgm','fga','threeMade','threeAttempted','ftm','fta','minutesSeconds'].some(k=>!Number.isFinite(p[k])||p[k]<0)||p.fgm>p.fga||p.threeMade>p.fgm||p.threeMade>p.threeAttempted||p.threeAttempted>p.fga||p.ftm>p.fta||2*p.fgm+p.threeMade+p.ftm!==p.points)return 'Incomplete or inconsistent final player line';
   }
  }return null;
 }
 function grade(records,datasets,{now=Date.now()}={}){
  const games=new Map(),versions=[];for(const data of datasets||[]){if(!data?.meta?.evidenceContentHash)continue;versions.push({season:data.meta.season,evidenceHash:data.meta.evidenceContentHash,through:data.meta.asOfDate});for(const g of data.games||[]){const prior=games.get(String(g.id));if(prior&&prior.sourceHash!==g.sourceHash)games.set(String(g.id),{conflict:true});else if(!prior)games.set(String(g.id),g);}}
  const results=[];
  for(const record of records||[])for(const r of record.results||[]){const q=r.quote||{},fixture=(record.fixtures||[]).find(f=>f.id===q.fixtureId),captured=Date.parse(record.capturedAt),age=captured-Date.parse(q.capturedAt),tip=fixture?Math.min(Date.parse(fixture.scheduledTipoff),Date.parse(q.fanduelTipoff)):NaN;
   const item={snapshotId:record.id||null,snapshotCapturedAt:record.capturedAt,modelHash:record.modelHash,forwardProtocolHash:record.forwardProtocolHash||null,rulesProfileHash:record.rulesProfileHash||null,quote:q,probabilities:r.probabilities,estimatedConditionalEV:r.ev,displayed:record.displayedSelectionKeys?record.displayedSelectionKeys.includes(q.key):null,statisticalOutcome:'pending',bookSettlement:'unverified',illustrativeUnitReturn:null};
   const finish=(outcome,reason)=>{results.push({...item,statisticalOutcome:outcome,reason});};
   if(record.recordType!=='experimental-ev-snapshot'||!record.modelHash||!fixture||!Number.isFinite(captured)||captured>now||!Number.isFinite(tip)||captured>=tip||!Number.isFinite(age)||age<0||age>300000||q.captureState!=='fresh'||q.marketStatus!=='OPEN'||q.runnerStatus!=='ACTIVE'){finish('invalid','Missing valid pregame capture evidence');continue;}
   const ps=r.probabilities,price=q.american>0?1+q.american/100:1+100/Math.abs(q.american);
   if(q.region!=='TN'||q.period!=='full-game'||fixture.phase!=='regular-season'||![fixture.home,fixture.away].includes(q.team)||!['points','threes'].includes(q.market)||!['over','under','at-least'].includes(q.side)||!Number.isFinite(q.line)||q.line<0||!Number.isInteger(2*q.line)||q.side==='at-least'&&!Number.isInteger(q.line)||!Number.isInteger(q.american)||Math.abs(q.american)<100||!Number.isFinite(q.decimal)||Math.abs(price-q.decimal)>1e-6||!/^https:\/\/sportsbook\.fanduel\.com\//.test(q.source||'')){finish('invalid','Unsupported exact market or fixture identity');continue;}
   if(!ps||['win','loss','push'].some(k=>!Number.isFinite(ps[k])||ps[k]<0)||Math.abs(ps.win+ps.loss+ps.push-1)>1e-7||!Number.isFinite(r.ev)||Math.abs(r.ev-(ps.win*(q.decimal-1)-ps.loss))>1e-8){finish('invalid','Recorded probabilities, price and EV do not reconcile');continue;}
   if(!r.features?.through||r.features.through>=fixture.date){finish('invalid','Prior-only feature evidence unavailable');continue;}
   const g=games.get(String(q.fixtureId));if(!g){finish('pending','Verified final PDF not collected yet');continue;}
   if(g.conflict){finish('review','Conflicting final source versions');continue;}
   if(g.date!==fixture.date||g.home!==fixture.home||g.away!==fixture.away||g.phase!==fixture.phase||g.scheduledTipoff&&Math.abs(Date.parse(g.scheduledTipoff)-Date.parse(fixture.scheduledTipoff))>900000){finish('review','Final fixture differs from frozen pregame fixture; check rescheduling');continue;}
   const error=finalError(g);if(error){finish('review',error);continue;}
   item.outcomeSource={url:g.source,sha256:g.sourceHash,date:g.date};
   const actual=g.teams[q.team].players.find(p=>String(p.id)===q.playerId),elsewhere=g.teams[q.team===g.home?g.away:g.home].players.some(p=>String(p.id)===q.playerId&&p.played);
   if(elsewhere){finish('review','Selected player appears on the other team in the final box');continue;}
   if(!actual||!actual.played){item.illustrativeUnitReturn=0;finish('void','No participation in the verified final box; rule-indicated void, sportsbook settlement unverified');continue;}
   const observed=actual[q.market==='points'?'points':'threeMade'],outcome=q.side==='at-least'?(observed>=q.line?'win':'loss'):observed===q.line?'push':q.side==='over'?(observed>q.line?'win':'loss'):(observed<q.line?'win':'loss');
   item.observed=observed;item.illustrativeUnitReturn=outcome==='win'?q.decimal-1:outcome==='loss'?-1:0;finish(outcome,'Official final statistic, including overtime; ordinary contract result only');
  }
  const counts=Object.fromEntries(['win','loss','push','void','pending','review','invalid'].map(k=>[k,results.filter(r=>r.statisticalOutcome===k).length]));
  return {schemaVersion:1,recordType:'experimental-ev-grading',graderVersion:VERSION,generatedAt:new Date(now).toISOString(),datasetVersions:versions,snapshots:(records||[]).length,counts,results,
   interpretation:'Research statistical outcomes only. Repeated snapshots and alternate lines are correlated and are not independent trials. Browser records are editable local research, not trusted pregame receipts. Illustrative returns assume ordinary rules; no sportsbook settlement, actual profit, ROI, bonus-credit value, or promotional protection is verified. Venue changes, abandoned games and other settlement exceptions require sportsbook confirmation. Pending/review/invalid outcomes are never losses.'};
 }
 return {VERSION,grade,finalError};
});
