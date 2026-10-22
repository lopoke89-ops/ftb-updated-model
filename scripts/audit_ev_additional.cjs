/* Independent raw-box accounting and same-observation diagnostics for new markets. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const ROOT=path.resolve(__dirname,'..'),SRC=path.join(ROOT,'nba ftb shi'),OUT=path.join(ROOT,'audits/2026-10-21-assists-rebounds'),X=require(path.join(SRC,'ev_additional.js')),model=require(path.join(SRC,'ev_additional_model.json')),data=require(path.join(SRC,'analyst_data.json'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),baseline=JSON.parse(fs.readFileSync(path.join(OUT,'frozen-baseline-hashes.json')));
// The leakage repair deliberately retires only these two live FTB files. Verify
// their original bytes in the preserved baseline; all other freezes remain live.
const retiredFirstTeam=new Set(['nba ftb shi/ev_first_team.js','nba ftb shi/ev_first_team_model.json']),originalFileChecks=[];
for(const [name,value]of Object.entries(baseline)){
 const retired=retiredFirstTeam.has(name),evidence=retired?'audits/2026-10-21-ftb-leakage-repair/baseline-v1.1/'+path.basename(name):name;
 assert.equal(hash(path.join(ROOT,evidence)),value,'Original frozen file changed: '+name);
 originalFileChecks.push({original:name,evidence,sha256:value,disposition:retired?'preserved-retired-ftb-baseline':'unchanged-live-file'});
}
const repaired=JSON.parse(fs.readFileSync(path.join(SRC,'ev_first_team_model.json')));
assert.equal(repaired.version,'ev-first-team-v1.2');assert.equal(repaired.enabled,false);assert.equal(repaired.engineHash,hash(path.join(SRC,'ev_first_team.js')));
const state=X.newState(),rawHistory=new Map(),observations={assists:[],rebounds:[]},fixtures=new Set(),sourceTotals={assists:0,rebounds:0,offensiveRebounds:0,defensiveRebounds:0},checks={rows:0,featureReconstructions:0,sameDayExcluded:0};
const games=data.games.filter(g=>g.phase==='regular-season').sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id));
for(const g of data.games)for(const team of [g.home,g.away])for(const p of g.teams[team].players)if(p.played){
 assert.equal(p.statsSourceHash,g.sourceHash);for(const k of Object.keys(sourceTotals)){assert(Number.isInteger(p[k])&&p[k]>=0);sourceTotals[k]+=p[k];}
 assert.equal(p.offensiveRebounds+p.defensiveRebounds,p.rebounds);checks.rows++;
}
function mean(r,k){return r.reduce((n,p)=>n+p[k],0)/r.length;}
function forecast(f,m,c){const mu=(c.meanMode==='season-mean'?f.baseline[m]:c.meanMode==='recent-mean'?f.recent[m]:f.base[m])*f.ratios[m].defense**c.defensePower;return {mass:X.distribution(mu,c.alpha),calibration:c.calibration};}
for(let start=0;start<games.length;){
 let end=start+1;while(end<games.length&&games[end].date===games[start].date)end++;
 for(const g of games.slice(start,end))for(const team of [g.home,g.away])for(const p of g.teams[team].players)for(const m of X.MARKETS){
  if(!X.validRow(p,m))continue;const f=X.features(state,p.id,team,team===g.home?g.away:g.home,m);if(f.reason)continue;
  const raw=(rawHistory.get(String(p.id))||[]).filter(r=>r.team===team);
  assert.equal(f.n,raw.length);assert(raw.every(r=>r.date<g.date));assert.equal(f.through,raw.at(-1).date);
  assert(Math.abs(f.baseline[m]-mean(raw,m))<1e-12);assert(f.historySeasons.every(s=>s==='2025-26'));
  const hist={};for(const r of raw)hist[r[m]]=(hist[r[m]]||0)+1;assert.deepEqual(f.histograms[m],hist);
  const recent=raw.slice(-20),w=recent.map((_,i)=>.94**(recent.length-1-i)),weighted=key=>recent.reduce((n,r,i)=>n+w[i]*r[key],0)/w.reduce((a,b)=>a+b,0);
  assert(Math.abs(f.recent[m]-weighted(m))<1e-12);checks.featureReconstructions++;checks.sameDayExcluded++;
  if(!f.positionSample||g.date<model.protocol.diagnosticStart||g.date>model.protocol.diagnosticEnd)continue;
  const cuts=X.thresholds(f,m).filter(k=>!X.contractSupport({features:f},{market:m,side:'over',line:k+.5}));if(!cuts.length)continue;
  const c=model.markets[m],configs={selected:c,seasonMean:c.baseline,recentMean:c.recentBaseline},predictions=Object.fromEntries(Object.entries(configs).map(([name,c])=>[name,forecast(f,m,c)]));
  for(const k of cuts){
   const values={};for(const [name,pred]of Object.entries(predictions)){assert(Math.abs(pred.mass.reduce((a,b)=>a+b,0)-1)<1e-8);const pwin=1-X.calibratedCDF(pred.mass,k,pred.calibration),y=Number(p[m]>k);values[name]={p:pwin,y,brier:(pwin-y)**2,logLoss:-(y*Math.log(Math.max(1e-12,pwin))+(1-y)*Math.log(Math.max(1e-12,1-pwin)))};}
   observations[m].push({gameId:g.id,date:g.date,id:p.id,role:f.role,history:f.n,weight:1/cuts.length,threshold:k+.5,values});
  }
 }
 for(const g of games.slice(start,end)){
  X.addGame(state,g);
  for(const team of [g.home,g.away])for(const p of g.teams[team].players)if(p.played){const rows=rawHistory.get(String(p.id))||[];rows.push({...p,date:g.date,team});rawHistory.set(String(p.id),rows);}
 }
 start=end;
}
let seed=20261021;const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
function metrics(rows,name){
 const weight=rows.reduce((n,r)=>n+r.weight,0),bins=Array.from({length:10},()=>({weight:0,p:0,y:0}));let brier=0,logLoss=0;
 for(const r of rows){const v=r.values[name],b=bins[Math.min(9,Math.floor(v.p*10))];b.weight+=r.weight;b.p+=r.weight*v.p;b.y+=r.weight*v.y;brier+=r.weight*v.brier;logLoss+=r.weight*v.logLoss;}
 return {appearances:new Set(rows.map(r=>r.gameId+'|'+r.id)).size,fixtures:new Set(rows.map(r=>r.gameId)).size,thresholdObservations:rows.length,brier:brier/weight,logLoss:logLoss/weight,weightedCalibrationError:bins.reduce((n,b)=>n+(b.weight?Math.abs(b.p-b.y)/weight:0),0),reliability:bins.map(b=>({weight:b.weight,meanPrediction:b.weight?b.p/b.weight:null,observed:b.weight?b.y/b.weight:null}))};
}
function interval(rows,benchmark,metric){
 const group=new Map();for(const r of rows){const g=group.get(r.gameId)||{loss:0,weight:0};g.loss+=r.weight*(r.values.selected[metric]-r.values[benchmark][metric]);g.weight+=r.weight;group.set(r.gameId,g);}
 const clusters=[...group.values()],result=[];for(let i=0;i<1000;i++){let n=0,w=0;for(let j=0;j<clusters.length;j++){const g=clusters[Math.floor(random()*clusters.length)];n+=g.loss;w+=g.weight;}result.push(n/w);}result.sort((a,b)=>a-b);return {clusters:clusters.length,replicates:1000,lower:result[24],upper:result[974],interpretation:'Model loss minus benchmark loss; fixture-cluster exploratory interval on an already inspected archive'};
}
const report={status:'passed-experimental-validation',generatedAt:new Date().toISOString(),modelHash:model.modelHash,engineHash:hash(path.join(SRC,'ev_additional.js')),trainerHash:hash(path.join(ROOT,'scripts/train_ev_additional.cjs')),auditorHash:hash(__filename),protocolHash:model.protocolHash,checks,sourceTotals,frozenOriginalsUnchanged:false,frozenOriginalsPreserved:true,originalFileChecks,firstTeamRepair:{version:repaired.version,modelHash:repaired.modelHash,enabled:repaired.enabled},markets:{},interpretation:'Separate retrospective diagnostic and source audit; not untouched prospective evidence, no historical odds ROI, no profitable-edge claim. Original count/Parlay files remain unchanged; two retired FTB files are verified in their preserved baseline after the separately versioned leakage repair.'};
for(const m of X.MARKETS){
 const rows=observations[m],selected=metrics(rows,'selected'),seasonMean=metrics(rows,'seasonMean'),recentMean=metrics(rows,'recentMean'),stored=model.markets[m].supportedDiagnostic;
 for(const k of ['brier','logLoss'])assert(Math.abs(selected[k]-stored[k])<1e-10,'Independent metric mismatch '+m+' '+k);
 assert.equal(selected.appearances,stored.appearances);assert.equal(selected.fixtures,stored.fixtures);
 assert(selected.fixtures>=200&&selected.appearances>=1000);
 assert.equal(model.markets[m].enabled,selected.brier<=seasonMean.brier&&selected.logLoss<=seasonMean.logLoss);
 report.markets[m]={selected,seasonMean,recentMean,gatePassed:model.markets[m].enabled,pairedIntervals:{seasonBrier:interval(rows,'seasonMean','brier'),seasonLogLoss:interval(rows,'seasonMean','logLoss'),recentBrier:interval(rows,'recentMean','brier'),recentLogLoss:interval(rows,'recentMean','logLoss')},byRole:Object.fromEntries(['G','F','C'].map(role=>[role,metrics(rows.filter(r=>r.role===role),'selected')]))};
 console.log(JSON.stringify({market:m,...selected,gatePassed:model.markets[m].enabled}));
}
fs.writeFileSync(path.join(OUT,'validation.json'),JSON.stringify(report,null,2)+'\n');
