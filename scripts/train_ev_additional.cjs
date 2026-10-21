/* Chronological, participation-conditional diagnostics; no historical odds or ROI. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),source=path.join(root,'nba ftb shi'),E=require(path.join(source,'ev_additional.js'));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const protocol=read(path.join(root,'ASSISTS_REBOUNDS_PROTOCOL.json')),data=read(path.join(source,'analyst_data.json'));
const sets={development:[],calibration:[],diagnostic:[]},state=E.newState();
const games=data.games.filter(g=>g.phase==='regular-season').sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id));
for(let start=0;start<games.length;){let end=start+1;while(end<games.length&&games[end].date===games[start].date)end++;
  for(const g of games.slice(start,end))for(const team of [g.home,g.away])for(const p of g.teams[team].players)for(const market of E.MARKETS){
    if(!E.validRow(p,market))continue;const f=E.features(state,p.id,team,team===g.home?g.away:g.home,market);if(f.reason||!f.positionSample)continue;
    const set=g.date<=protocol.developmentEnd?'development':g.date<=protocol.calibrationEnd?'calibration':'diagnostic';
    if(g.date<=protocol.diagnosticEnd)sets[set].push({market,gameId:g.id,id:p.id,date:g.date,f,y:{[market]:p[market]}});
  }
  for(const g of games.slice(start,end))E.addGame(state,g);start=end;
}
function eligible(rows,market){return rows.filter(r=>r.market===market);}
function mu(r,market,c){return(c.meanMode==='season-mean'?r.f.baseline[market]:c.meanMode==='recent-mean'?r.f.recent[market]:r.f.base[market])*Math.pow(r.f.ratios[market].defense,c.defensePower);}
function alpha(r,market,c){return Math.max(.01,Math.min(2,c.alpha*(1-(c.dispersionBlend||0))+r.f.dispersion[market]*(c.dispersionBlend||0)));}
function loss(rows,market,c){let out=0;for(const r of rows){const m=E.distribution(mu(r,market,c),alpha(r,market,c));out-=Math.log(Math.max(1e-12,m[r.y[market]]||0));}return out/rows.length;}
function thresholds(r,market){return E.thresholds(r.f,market);}
function pairs(rows,market,c){const result=[];for(const r of rows){const mass=E.distribution(mu(r,market,c),alpha(r,market,c)),cuts=thresholds(r,market);for(const k of cuts)result.push({x:E.logit(E.cdf(mass,k)),y:Number(r.y[market]<=k),weight:1/cuts.length});}return result;}
function fitCalibration(rows){
  let a=1,b=0;const objective=(a,b)=>rows.reduce((n,r)=>{const p=E.sigmoid(a*r.x+b);return n-r.weight*(r.y*Math.log(Math.max(1e-12,p))+(1-r.y)*Math.log(Math.max(1e-12,1-p)));},0);
  for(let step=0;step<35;step++){
    let ga=.01*(a-1),gb=.01*b,aa=.01,ab=0,bb=.01;
    for(const r of rows){const p=E.sigmoid(a*r.x+b),v=r.weight*p*(1-p),err=r.weight*(p-r.y);ga+=err*r.x;gb+=err;aa+=v*r.x*r.x;ab+=v*r.x;bb+=v;}
    const det=aa*bb-ab*ab;if(!(det>0))break;const da=(bb*ga-ab*gb)/det,db=(aa*gb-ab*ga)/det,old=objective(a,b);let t=1,accepted=false;
    while(t>1e-6){const na=Math.max(.1,Math.min(5,a-t*da)),nb=Math.max(-4,Math.min(4,b-t*db));if(objective(na,nb)<=old){a=na;b=nb;accepted=true;break;}t/=2;}
    if(!accepted||Math.abs(t*da)+Math.abs(t*db)<1e-7)break;
  }return {a,b,method:'positive-slope logistic CDF calibration; later dates only'};
}
function metrics(rows,market,c,cal,supported=false){
  let brier=0,logLoss=0,n=0;const fixtures=new Set(),bins=Array.from({length:10},()=>({n:0,predicted:0,observed:0}));
  for(const r of rows){const mass=E.distribution(mu(r,market,c),alpha(r,market,c)),cuts=thresholds(r,market).filter(k=>!supported||!E.contractSupport({features:r.f},{market,side:'over',line:k+.5}));if(!cuts.length)continue;
    for(const k of cuts){const p=E.calibratedCDF(mass,k,cal),y=Number(r.y[market]<=k),w=1/cuts.length;brier+=w*(p-y)**2;logLoss-=w*(y*Math.log(Math.max(1e-12,p))+(1-y)*Math.log(Math.max(1e-12,1-p)));const bin=bins[Math.min(9,Math.floor(p*10))];bin.n++;bin.predicted+=p;bin.observed+=y;}n++;fixtures.add(r.gameId);
  }
  return {appearances:n,fixtures:fixtures.size,brier:n?brier/n:null,logLoss:n?logLoss/n:null,bins:bins.map(b=>({n:b.n,meanPrediction:b.n?b.predicted/b.n:null,observed:b.n?b.observed/b.n:null})),interpretation:'One total weight per player appearance; threshold observations are correlated. Reliability bins count thresholds. No independent-trial intervals or historical price returns.'};
}
const model={version:E.VERSION,experimental:true,phase:'regular-season',archiveEvidenceHash:data.meta.evidenceContentHash,archiveThrough:data.meta.asOfDate,engineHash:hash(path.join(source,'ev_additional.js')),trainerHash:hash(__filename),protocolHash:hash(path.join(root,'ASSISTS_REBOUNDS_PROTOCOL.json')),forwardProtocolHash:hash(path.join(root,'ASSISTS_REBOUNDS_FORWARD_PROTOCOL.json')),rulesProfileHash:hash(path.join(root,'ASSISTS_REBOUNDS_RULES.json')),protocol,markets:{}};
for(const market of ['assists','rebounds']){
  const dev=eligible(sets.development,market),cal=eligible(sets.calibration,market),test=eligible(sets.diagnostic,market);if(!dev.length||!cal.length||!test.length)throw Error('Missing chronological samples');
  const candidates=[];
  for(const meanMode of ['exposure-rate','season-mean','recent-mean'])for(const defensePower of [0,.25,.5])for(const offensePower of [0])for(const dispersionBlend of [0])for(const alpha of [.04,.16,.4,.8]){const c={meanMode,defensePower,offensePower,alpha,dispersionBlend};c.developmentNll=loss(dev,market,c);candidates.push(c);}
  candidates.sort((a,b)=>a.developmentNll-b.developmentNll);const selected=candidates[0],baseline=candidates.filter(c=>c.meanMode==='season-mean'&&c.defensePower===0&&c.offensePower===0&&c.dispersionBlend===0).sort((a,b)=>a.developmentNll-b.developmentNll)[0];
  const calibration=fitCalibration(pairs(cal,market,selected)),baselineCalibration=fitCalibration(pairs(cal,market,baseline));
  const recentBaseline=candidates.filter(c=>c.meanMode==='recent-mean'&&c.defensePower===0).sort((a,b)=>a.developmentNll-b.developmentNll)[0],recentCalibration=fitCalibration(pairs(cal,market,recentBaseline));
  const diagnostic={...metrics(test,market,selected,calibration),uncalibrated:metrics(test,market,selected,null),meanBaseline:metrics(test,market,baseline,baselineCalibration),recentBaseline:metrics(test,market,recentBaseline,recentCalibration)};
  const supportedDiagnostic={...metrics(test,market,selected,calibration,true),meanBaseline:metrics(test,market,baseline,baselineCalibration,true),recentBaseline:metrics(test,market,recentBaseline,recentCalibration,true)};
  diagnostic.beatsMeanBaseline=diagnostic.brier<=diagnostic.meanBaseline.brier&&diagnostic.logLoss<=diagnostic.meanBaseline.logLoss;
  const enabled=supportedDiagnostic.fixtures>=200&&supportedDiagnostic.appearances>=1000&&supportedDiagnostic.brier<=supportedDiagnostic.meanBaseline.brier&&supportedDiagnostic.logLoss<=supportedDiagnostic.meanBaseline.logLoss;
  model.markets[market]={...selected,calibration,baseline:{...baseline,calibration:baselineCalibration},recentBaseline:{...recentBaseline,calibration:recentCalibration},enabled,withheldReason:enabled?null:'Separate diagnostic gate failed; market EV withheld',developmentAppearances:dev.length,calibrationAppearances:cal.length,diagnostic,supportedDiagnostic};
  console.log(JSON.stringify({market,selected,calibration,diagnostic:{n:diagnostic.appearances,fixtures:diagnostic.fixtures,brier:diagnostic.brier,logLoss:diagnostic.logLoss,baselineBrier:diagnostic.meanBaseline.brier,beatsMeanBaseline:diagnostic.beatsMeanBaseline}}));
}
model.modelHash=crypto.createHash('sha256').update(JSON.stringify(model)).digest('hex');
fs.writeFileSync(path.join(source,'ev_additional_model.json'),JSON.stringify(model,null,2)+'\n');
fs.writeFileSync(path.join(source,'ev_additional_model.js'),'window.__FTB_EV_ADDITIONAL_MODEL__='+JSON.stringify(model)+';\n');
