/* Reproducible chronological research evaluation; no packages required. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const A=require('./analyst.js'),base=__dirname,protocolDir=path.join(base,'../implementation_2026-10-04'),out=process.argv[3]?path.resolve(process.argv[3]):protocolDir;
fs.mkdirSync(out,{recursive:true});
const evidenceDir=process.argv[2]?path.resolve(process.argv[2]):base;
const data=JSON.parse(fs.readFileSync(path.join(evidenceDir,'analyst_data.json'),'utf8'));
const protocol=JSON.parse(fs.readFileSync(fs.existsSync(path.join(base,'evaluation_protocol.json'))?path.join(base,'evaluation_protocol.json'):path.join(protocolDir,'evaluation_protocol.json'),'utf8'));
const reportPath=path.join(out,'evaluation_report.json');
const models=['share','opportunity'],snapshots=new Map(),rows=[];
function score(prob,winner){const p=prob[winner]??prob.OTHER;const ranked=Object.keys(prob).sort((a,b)=>prob[b]-prob[a]);const actual=winner in prob?winner:'OTHER';return {logLoss:-Math.log(Math.max(p,1e-15)),brier:Object.entries(prob).reduce((s,[id,v])=>s+(v-(id===actual?1:0))**2,0),topOne:ranked[0]===actual?1:0,topThree:ranked.slice(0,3).includes(actual)?1:0,covered:actual!=='OTHER',p,actual};}
for(const g of data.games){
  let snap=snapshots.get(g.date);if(!snap){snap=A.snapshot(data,{date:g.date,mode:'pregame'});snapshots.set(g.date,snap);}
  for(const team of [g.home,g.away]){
    const sample=snap.teamStats[team]?.games||0;
    if(sample<protocol.warmupTeamGames){rows.push({gameId:g.id,date:g.date,team,phase:g.phase,withheld:true,reason:'warmup',sample});continue;}
    const predictions={};for(const model of models){const d=A.distribution(snap,team,{model});if(!A.validateDistribution(d))throw Error('Invalid distribution');if(d.withheld)throw Error('Expected dated roster');predictions[model]=d.probabilities;}
    const winner=g.firstScores[team].id;
    const prior=snap.games.filter(v=>v.home===team||v.away===team).slice(-2),previousGroup=prior.length===2?prior[0].teams[team].starters:[],reference=snap.lastLineups[team];
    rows.push({gameId:g.id,date:g.date,team,phase:g.phase,home:team===g.home,sample,winner,freeThrow:g.firstScores[team].shot==='ft',predictions,
      featureSnapshot:{statsThrough:snap.meta.statsThrough,priorFixtureIds:snap.games.filter(v=>v.home===team||v.away===team).map(v=>v.id),referenceLineupDate:reference.date,referenceLineupIds:reference.ids,candidates:Object.keys(predictions.share).filter(id=>id!=='OTHER').map(id=>{const d=snap.players[id]?.ftbByTeam[team]||{};return {id,wins:d.ftbMade||0,appearances:d.gp||0,starts:d.starts||0,startWins:d.starterWins||0};})},
      priorStarterContinuity:previousGroup.length===5?reference.ids.filter(id=>previousGroup.includes(id)).length/5:null,
      sourceHash:g.sourceHash,lineupCertainty:'prior-lineup-reference',historicalPublicationEvidence:false});
  }
}
function aggregate(list,model,temp=1){const evaluated=list.filter(r=>!r.withheld);if(!evaluated.length)return {events:0};const scored=evaluated.map(r=>({r,...score(temper(r.predictions[model],temp),r.winner)}));
  return {events:scored.length,fixtures:new Set(scored.map(s=>s.r.gameId)).size,logLoss:mean(scored.map(s=>s.logLoss)),brier:mean(scored.map(s=>s.brier)),topOne:mean(scored.map(s=>s.topOne)),topThree:mean(scored.map(s=>s.topThree)),candidateCoverage:mean(scored.map(s=>+s.covered))};}
function mean(xs){return xs.reduce((a,b)=>a+b,0)/xs.length;}
function temper(prob,temp){const w=Object.fromEntries(Object.entries(prob).map(([id,p])=>[id,p**(1/temp)]));const sum=Object.values(w).reduce((a,b)=>a+b,0);return Object.fromEntries(Object.entries(w).map(([id,p])=>[id,p/sum]));}
const calibration=rows.filter(r=>r.date>=protocol.calibrationStart&&r.date<=protocol.calibrationEnd),test=rows.filter(r=>r.date>=protocol.lockedTestStart&&r.date<=protocol.lockedTestEnd);
const temps={};for(const m of models)temps[m]=protocol.calibrationTemperatures.map(t=>({temperature:t,...aggregate(calibration,m,t)})).sort((a,b)=>a.logLoss-b.logLoss)[0].temperature;
const summary={};for(const m of models)summary[m]={temperature:temps[m],calibration:aggregate(calibration,m,temps[m]),test:aggregate(test,m,temps[m])};
const paired={};for(const r of test.filter(r=>!r.withheld)){const a=score(temper(r.predictions.share,temps.share),r.winner),b=score(temper(r.predictions.opportunity,temps.opportunity),r.winner);(paired[r.gameId]??=[]).push(a.logLoss-b.logLoss);}
const differences=Object.values(paired).map(mean);let seed=protocol.bootstrapSeed;
function random(){seed=(Math.imul(1664525,seed)+1013904223)>>>0;return seed/4294967296;}
const boot=[];for(let i=0;i<protocol.bootstrapReplicates;i++){let sum=0;for(let j=0;j<differences.length;j++)sum+=differences[Math.floor(random()*differences.length)];boot.push(sum/differences.length);}boot.sort((a,b)=>a-b);
const interval=[boot[Math.floor(boot.length*.025)],boot[Math.floor(boot.length*.975)]];
const baseStats=summary.share.test,ch=summary.opportunity.test;
let promoted=(baseStats.logLoss-ch.logLoss)/baseStats.logLoss>=.01&&interval[0]>0&&ch.brier<=baseStats.brier*1.01&&ch.candidateCoverage>=baseStats.candidateCoverage;
// Compute the declared series/time-block sensitivity before selecting the model.
const blocks={};for(const r of test.filter(r=>!r.withheld)){const g=data.games.find(g=>g.id===r.gameId),block=g.phase==='playoffs'?[g.home,g.away].sort().join('-'):g.date;(blocks[block]??=[]).push(score(temper(r.predictions.share,temps.share),r.winner).logLoss-score(temper(r.predictions.opportunity,temps.opportunity),r.winner).logLoss);}
const blockValues=Object.values(blocks).map(mean),blockBoot=[];for(let i=0;i<1000;i++){let sum=0;for(let j=0;j<blockValues.length;j++)sum+=blockValues[Math.floor(random()*blockValues.length)];blockBoot.push(sum/blockValues.length);}blockBoot.sort((a,b)=>a-b);
promoted=promoted&&blockBoot[25]>0;
const selected=promoted?'opportunity':'share';
const reliability=protocol.calibrationBins.slice(0,-1).map((lo,i)=>({low:lo,high:protocol.calibrationBins[i+1],n:0,sum:0,wins:0}));
for(const r of test.filter(r=>!r.withheld)){const ps=temper(r.predictions[selected],temps[selected]),actual=r.winner in ps?r.winner:'OTHER';for(const [id,p] of Object.entries(ps)){const bin=reliability.find(b=>p>=b.low&&(p<b.high||b.high===1&&p<=1));if(bin){bin.n++;bin.sum+=p;if(id===actual)bin.wins++;}}}
for(const b of reliability){b.meanForecast=b.n?b.sum/b.n:null;b.observed=b.n?b.wins/b.n:null;b.descriptiveInterval=A.wilson(b.wins,b.n);delete b.sum;}
const slices={};for(const group of ['regular-season','playoffs','play-in','nba-cup-final','free-throw','field-goal']){const filtered=group==='free-throw'?test.filter(r=>r.freeThrow):group==='field-goal'?test.filter(r=>r.freeThrow===false):test.filter(r=>r.phase===group);slices[group]=aggregate(filtered,selected,temps[selected]);}
for(const [label,filter] of [['home',r=>r.home===true],['away',r=>r.home===false],['prior-lineup-unchanged',r=>r.priorStarterContinuity===1],['prior-lineup-changed',r=>r.priorStarterContinuity!==null&&r.priorStarterContinuity<1],['prior-sample-10-to-29',r=>r.sample>=10&&r.sample<30],['prior-sample-30-plus',r=>r.sample>=30]])slices[label]=aggregate(test.filter(filter),selected,temps[selected]);
const report={protocol,evidenceContentHash:data.meta.evidenceContentHash,protocolHash:crypto.createHash('sha256').update(JSON.stringify(protocol)).digest('hex'),evidenceHash:crypto.createHash('sha256').update(fs.readFileSync(path.join(evidenceDir,'analyst_data.json'))).digest('hex'),
  modelCodeHash:crypto.createHash('sha256').update(fs.readFileSync(path.join(base,'analyst.js'))).digest('hex'),models:summary,
  pairedGameImprovement:{mean:mean(differences),interval95:interval,fixtures:differences.length},seriesBlockSensitivity:{blocks:blockValues.length,interval95:[blockBoot[25],blockBoot[975]]},
  selectedModel:selected,selectedTemperature:temps[selected],challengerPromoted:promoted,reliability,slices,
  diagnosticSlicePurpose:'Descriptive home/away, prior-reference-lineup continuity and sample-size audit; no additional model fitting or promotion criterion. All evaluated lineups are unconfirmed prior references; confirmed-lineup comparison unavailable.',
  evaluatorCodeHash:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
  coverage:{totalTeamEvents:rows.length,evaluated:rows.filter(r=>!r.withheld).length,withheld:rows.filter(r=>r.withheld).length},
  interpretation:'Retrospective corrected-data research; unconfirmed prior lineups; original publication history unavailable; no live track record or profitability claim',
  builtAt:new Date().toISOString()};
fs.writeFileSync(reportPath,JSON.stringify(report,null,2));fs.writeFileSync(path.join(out,'retrospective_predictions.jsonl'),rows.map(r=>JSON.stringify(r)).join('\n')+'\n');
fs.writeFileSync(path.join(evidenceDir,'analyst_evaluation.json'),JSON.stringify(report));fs.writeFileSync(path.join(evidenceDir,'analyst_evaluation.js'),'window.__FTB_ANALYST_EVALUATION__ = '+JSON.stringify(report)+';\n');
console.log(JSON.stringify({selectedModel:selected,temperatures:temps,test:summary,pairedInterval:interval,coverage:report.coverage},null,2));
