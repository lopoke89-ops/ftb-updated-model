'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const E=require('../ev_probability.js'),source=path.join(__dirname,'..');
let n=0;function test(name,fn){fn();n++;console.log('PASS '+name);}
const now=Date.parse('2026-10-19T02:00Z'),fixture={id:'401909088',date:'2026-10-20',season:'2026-27',phase:'regular-season',home:'DET',away:'BOS',status:'pre',scheduledTipoff:'2026-10-20T19:00Z'};
const p={mass:[.1,.2,.3,.25,.15],calibration:{a:1,b:0}};
test('milestones and half-point overs agree; integer lines refund exact outcomes',()=>{
 const a=E.probabilities(p,{side:'at-least',line:3}),b=E.probabilities(p,{side:'over',line:2.5}),c=E.probabilities(p,{side:'over',line:3});
 assert.deepEqual(a,b);assert(Math.abs(a.win-.4)<1e-12);assert(Math.abs(c.win-.15)<1e-12);assert(Math.abs(c.push-.25)<1e-12);assert(Math.abs(c.loss-.6)<1e-12);
 assert(Math.abs(E.probabilities(p,{side:'under',line:3}).win-.6)<1e-12);
});
test('EV accounts for losses and refunded pushes; bookmaker implied chance is not model chance',()=>{
 assert(Math.abs(E.expectedValue({win:.38,loss:.62,push:0},3)-.14)<1e-12);
 assert(Math.abs(E.expectedValue({win:.4,loss:.3,push:.3},2)-.1)<1e-12);
 assert.throws(()=>E.expectedValue({win:.8,loss:.8,push:0},2));assert.throws(()=>E.probabilities(p,{side:'at-least',line:2.5}));
});
test('count distributions normalize and retain fitted means and monotonic calibrated CDFs',()=>{
 for(const mu of [0,.1,2.8,24,60]){const mass=E.distribution(mu,.32);assert(Math.abs(mass.reduce((a,b)=>a+b,0)-1)<1e-8);assert(Math.abs(mass.reduce((a,b,i)=>a+i*b,0)-mu)<1e-7);let prior=0;for(let k=0;k<120;k++){const c=E.calibratedCDF(mass,k,{a:.8,b:.1});assert(c>=prior);prior=c;}}
});
const row=(id,team,step)=>({id,name:id,played:true,starter:true,officialPosition:'G',minutes:30+step%3,fga:10+step%4,fgm:4+step%4,threeAttempted:3+step%4,threeMade:step%4,ftm:2,fta:3,points:2*(4+step%4)+step%4+2});
const games=Array.from({length:30},(_,i)=>({id:String(i),date:'2025-11-'+String(i+1).padStart(2,'0'),phase:'regular-season',home:'BOS',away:'DET',teams:{BOS:{players:[row('1','BOS',i)]},DET:{players:[row('2','DET',i)]}}}));
test('future and selected-day boxes cannot change prior features; outcomes obey scoring identities',()=>{
 const before='2025-11-25',a=E.features(E.buildState(games,{before}),'1','BOS','DET'),bad={...games.at(-1),id:'later',date:'2026-01-01',teams:{BOS:{players:[{...row('1','BOS',2),points:99}]},DET:games[0].teams.DET}};
 assert.deepEqual(a,E.features(E.buildState([...games,bad],{before}),'1','BOS','DET'));assert.equal(a.n,24);assert.equal(a.through,'2025-11-24');assert(!E.validRow({...row('1','BOS',1),points:80}));assert(Math.abs(a.base.points-(2*(a.fgm-a.threePm)+3*a.threePm+a.ftm))<1e-10);
});
test('small samples, unknown roles and unsupported shooting evidence withhold probabilities',()=>{
 assert.match(E.features(E.buildState(games.slice(0,8)),'1','BOS','DET').reason,/20/);
 assert(E.predict({role:null,positionSample:false},'points',{}).reason);
 assert(E.predict({role:'G',positionSample:true,correlation:{threes:0}},'threes',{}).reason);
});
test('official played appearances with printed zero minutes remain in the participation sample',()=>{
 const zero={...row('1','BOS',0),minutes:0,points:0,fgm:0,fga:0,threeMade:0,threeAttempted:0,ftm:0,fta:0};
 assert(E.validRow(zero));assert(!E.validRow({...zero,played:false}));
 const g={...games[0],id:'zero',date:'2025-12-01',teams:{...games[0].teams,BOS:{players:[zero]}}};
 assert.equal(E.features(E.buildState([...games,g]),'1','BOS','DET').n,31);
});
test('displayed projections match calibrated count probabilities rather than the raw mean',()=>{
 const model=JSON.parse(fs.readFileSync(path.join(source,'ev_model.json'))),f=E.features(E.buildState(games),'1','BOS','DET'),prediction=E.predict(f,'points',model);
 let expected=0;for(let k=0;k<prediction.mass.length;k++)expected+=1-E.calibratedCDF(prediction.mass,k,prediction.calibration);
 assert(Math.abs(prediction.calibratedMean-expected)<1e-10);assert(Number.isFinite(prediction.mu));
});
const quote={key:'fd|m|s',fixtureId:fixture.id,fanduelEventId:'35928218',fanduelTipoff:fixture.scheduledTipoff,playerId:'1',player:'Player',team:'BOS',market:'points',period:'full-game',side:'over',line:2.5,american:200,decimal:3,region:'TN',capturedAt:new Date(now-10000).toISOString(),marketStatus:'OPEN',runnerStatus:'ACTIVE',captureState:'fresh',source:'https://sportsbook.fanduel.com/basketball/nba/game-35928218'};
const entry={fixture,fanduelEventId:quote.fanduelEventId,quotes:[quote]},snapshot={schemaVersion:1,bookmaker:'fanduel',region:'TN',fixtures:{[fixture.id]:entry}};
const props={snapshot,fixtures:[fixture],rosters:{BOS:[{id:'1',name:'Player',team:'BOS'}]},predictions:{[fixture.id+'|BOS|1|points']:{...p,mu:2,features:{n:30,baseline:{points:2},histograms:{points:{0:10,2:10,4:10}}}}},eligibility:{1:{provisional:false}},now};
test('fresh exact-fixture prices rank by estimated EV; Out is excluded and Questionable stays provisional',()=>{
 assert.equal(E.evaluateQuotes(props).rows.length,1);assert.equal(E.evaluateQuotes({...props,eligibility:{1:{excluded:true,reason:'OUT'}}}).rows.length,0);
 assert(E.evaluateQuotes({...props,eligibility:{1:{provisional:true,reason:'QUESTIONABLE'}}}).rows[0].provisional);
});
test('stale, future, cached, suspended, wrong-team and started-game quotes cannot produce EV',()=>{
 for(const changes of [{capturedAt:new Date(now-300001).toISOString()},{capturedAt:new Date(now+1).toISOString()},{captureState:'cached'},{runnerStatus:'SUSPENDED'},{team:'SAC'},{region:'NJ'},{american:-120}]){
  const s={...snapshot,fixtures:{[fixture.id]:{...entry,quotes:[{...quote,...changes}]}}};assert.equal(E.evaluateQuotes({...props,snapshot:s}).rows.length,0,JSON.stringify(changes));
 }
 assert.equal(E.evaluateQuotes({...props,now:Date.parse(fixture.scheduledTipoff)}).rows.length,0);
 assert.equal(E.evaluateQuotes({...props,predictions:{['other|BOS|1|points']:p}}).rows.length,0);
});
test('ambiguous current rosters and duplicate quote IDs are audited rather than double counted',()=>{
 assert.equal(E.evaluateQuotes({...props,rosters:{BOS:[...props.rosters.BOS,...props.rosters.BOS]}}).rows.length,0);
 const r=E.evaluateQuotes({...props,snapshot:{...snapshot,fixtures:{[fixture.id]:{...entry,quotes:[quote,quote]}}}});assert.equal(r.rows.length,1);assert.match(r.audit[0].reason,/Duplicate/);
});
test('wrong-date, wrong-season, wrong-phase and changed-tipoff snapshots fail exact fixture matching',()=>{
 for(const change of [{date:'2026-10-21'},{season:'2025-26'},{phase:'preseason'},{id:'other'},{scheduledTipoff:'2026-10-20T20:00Z'}]){
  const s={...snapshot,fixtures:{[fixture.id]:{...entry,fixture:{...fixture,...change}}}};assert.equal(E.evaluateQuotes({...props,snapshot:s}).rows.length,0);
 }
 assert.equal(E.quoteState({...quote,fanduelTipoff:undefined},fixture,now),'identity-mismatch');
});
test('unsupported tails and new-team histories do not become enormous positive EV estimates',()=>{
 const f=props.predictions[fixture.id+'|BOS|1|points'];assert.match(E.contractSupport(f,{market:'points',side:'at-least',line:40}),/range/);
 assert.match(E.contractSupport({...f,features:{...f.features,histograms:{points:{0:29,4:1}}}},{market:'points',side:'over',line:2.5}),/five/);
 assert.match(E.features(E.buildState(games),'1','PHI','DET').reason,/other-team/);
});
test('frozen model matches engine and has disjoint chronological windows without historical ROI claims',()=>{
 const model=JSON.parse(fs.readFileSync(path.join(source,'ev_model.json'))),engine=crypto.createHash('sha256').update(fs.readFileSync(path.join(source,'ev_probability.js'))).digest('hex');assert.equal(model.engineHash,engine);
 const {modelHash,...content}=model;assert.equal(modelHash,crypto.createHash('sha256').update(JSON.stringify(content)).digest('hex'));
 assert.equal(model.version,E.VERSION);
 for(const [field,file] of [['forwardProtocolHash','EV_FORWARD_PROTOCOL.json'],['rulesProfileHash','EV_RULES_PROFILE.json']])assert.equal(model[field],crypto.createHash('sha256').update(fs.readFileSync(path.join(source,'..',file))).digest('hex'));
 assert(model.protocol.developmentEnd<model.protocol.calibrationStart);assert(model.protocol.calibrationEnd<model.protocol.diagnosticStart);assert(model.experimental);assert(!('roi' in model));
 for(const m of Object.values(model.markets)){assert(m.calibration.a>0);assert(m.diagnostic.fixtures>100);assert(m.diagnostic.brier>=0&&m.diagnostic.brier<=1);}
});
console.log(JSON.stringify({passed:n}));
