'use strict';
const assert=require('node:assert/strict'),H=require('../scouting_history.js');
async function main(){
  let tick,interval,cleared=false,calls=0,release;
  const stop=H.startLiveRefresh(async()=>{calls++;await new Promise(resolve=>{release=resolve;});},
    {setTimer:(callback,ms)=>{tick=callback;interval=ms;return 42;},clearTimer:id=>{assert.equal(id,42);cleared=true;}});
  assert.equal(interval,300000);assert.equal(calls,0);
  tick();tick();assert.equal(calls,1,'overlapping refresh is skipped');
  release();await new Promise(setImmediate);tick();assert.equal(calls,2,'next interval can refresh');
  stop();release();await new Promise(setImmediate);tick();assert.equal(calls,2);assert(cleared);
  let failures=0,next;
  const end=H.startLiveRefresh(async()=>{failures++;throw Error('source down');},{setTimer:f=>{next=f;return 1;},clearTimer:()=>{}});
  next();await new Promise(setImmediate);next();await new Promise(setImmediate);assert.equal(failures,2,'source failure does not stop future refreshes');end();
  const context={upcoming:true,date:'2026-10-20',today:'2026-10-20',fresh:true,injuries:{}};
  for(const status of ['OUT','DOUBTFUL'])assert(H.pickEligibility('1',{...context,injuries:{1:{status}}}).excluded);
  assert(H.pickEligibility('1',{...context,injuries:{1:{status:'QUESTIONABLE'}}}).provisional);
  assert(H.pickEligibility('1',{...context,fresh:false}).provisional);
  assert(H.pickEligibility('1',{...context,date:'2026-10-21'}).provisional);
  assert(!H.pickEligibility('1',context).provisional);
  const prior={1:{status:'QUESTIONABLE',capturedAt:'2026-10-20T12:00Z'},2:{status:'OUT'}};
  const retained=H.mergeInjuries(prior,{});assert(retained[1].carriedForward);assert.equal(retained[2].status,'OUT');
  assert(H.pickEligibility('1',{...context,injuries:retained}).provisional);
  assert.equal(H.mergeInjuries(prior,{1:{status:'UNKNOWN'}})[1].status,'QUESTIONABLE');
  assert.equal(H.mergeInjuries(prior,{1:{status:'PROBABLE'}})[1].status,'QUESTIONABLE');
  const clearedInjury=H.mergeInjuries(prior,{1:{status:'AVAILABLE',capturedAt:'2026-10-20T12:05Z'}});
  assert(!H.pickEligibility('1',{...context,injuries:clearedInjury}).provisional);
  assert.throws(()=>H.validateCollectedSeason({meta:{season:'2026-27',parentDatasetId:'nba-2026-27-canonical',totalGames:1},games:[]}),/Invalid/);
  console.log('Live refresh and availability checks passed');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
