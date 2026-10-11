const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {createController}=require('../scout_music.js');
class AudioStub{
  constructor(){this.paused=true;this.error=null;this.events=new Map();this.calls=0;this.loads=0;}
  addEventListener(name,fn){this.events.set(name,fn);}
  removeEventListener(name,fn){assert.equal(this.events.get(name),fn);this.events.delete(name);}
  emit(name){this.events.get(name)?.();}
  play(){this.calls++;if(this.fail)return Promise.reject(this.fail);this.paused=false;this.emit('playing');return this.pending||Promise.resolve();}
  pause(){const changed=!this.paused;this.paused=true;if(changed)this.emit('pause');}
  load(){this.loads++;this.error=null;}
}
function setup(saved){const audio=new AudioStub(),states=[],store=new Map(saved===undefined?[]:[['ftb-scout-music-volume-v1',saved]]);const controller=createController(audio,{storage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},onChange:s=>states.push(s)});return {audio,states,store,controller,last:()=>states.at(-1)};}
let passed=0;async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
(async()=>{
  await test('page load stays silent and configures native continuous looping',()=>{const r=setup();assert.equal(r.audio.calls,0);assert.equal(r.audio.loop,true);assert.equal(r.audio.volume,.18);assert.equal(r.last().status,'off');});
  await test('toggle starts, pauses and resumes the same media instance',async()=>{const r=setup();await r.controller.toggle();assert.equal(r.last().status,'playing');r.controller.toggle();assert.equal(r.last().status,'paused');await r.controller.toggle();assert.equal(r.last().status,'playing');assert.equal(r.audio.calls,2);});
  await test('OS media pause is reflected and next toggle resumes',async()=>{const r=setup();await r.controller.play();r.audio.pause();assert.equal(r.last().status,'paused');await r.controller.toggle();assert.equal(r.last().status,'playing');});
  await test('blocked autoplay reports a retryable state without claiming playback',async()=>{const r=setup();r.audio.fail={name:'NotAllowedError'};await r.controller.play();assert.equal(r.last().status,'blocked');r.audio.fail=null;await r.controller.toggle();assert.equal(r.last().status,'playing');});
  await test('pause while play is pending cannot be undone by its late promise',async()=>{const r=setup();let resolve;r.audio.pending=new Promise(done=>resolve=done);const pending=r.controller.play();r.controller.pause();resolve();await pending;assert.equal(r.last().status,'paused');assert.equal(r.audio.paused,true);});
  await test('saved volume survives a new controller including zero and clamps inputs',()=>{const r=setup('.34');assert.equal(r.audio.volume,.34);r.controller.setVolume(0);assert.equal(setup(r.store.get('ftb-scout-music-volume-v1')).audio.volume,0);r.controller.setVolume(8);assert.equal(r.audio.volume,1);r.controller.setVolume(NaN);assert.equal(r.audio.volume,1);for(const bad of ['bad','-1','2'])assert.equal(setup(bad).audio.volume,.18);});
  await test('denied local storage does not prevent playback',async()=>{const audio=new AudioStub();const c=createController(audio,{storage:{getItem(){throw Error('denied');},setItem(){throw Error('denied');}}});c.setVolume(.5);await c.play();assert.equal(audio.paused,false);c.destroy();});
  await test('network or decoding error can reload and retry',async()=>{const r=setup();r.audio.error={code:3};r.audio.emit('error');assert.equal(r.last().status,'error');await r.controller.toggle();assert.equal(r.audio.loads,1);assert.equal(r.last().status,'playing');});
  await test('unmount stops audio and removes every event listener',async()=>{const r=setup();await r.controller.play();r.controller.destroy();assert.equal(r.audio.paused,true);assert.equal(r.audio.events.size,0);const count=r.states.length;await r.controller.play();assert.equal(r.states.length,count);r.controller.destroy();});
  await test('published soundtrack matches source manifest and starts with no prefetch or autoplay',()=>{const base=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(base,'ftb-scout.html'),'utf8'),tag=html.match(/<audio\b[^>]*>/g);assert.equal(tag.length,1);assert.match(tag[0],/loop/);assert.match(tag[0],/preload="none"/);assert.doesNotMatch(tag[0],/autoplay/);const meta=JSON.parse(fs.readFileSync(path.join(base,'scout_music_source.json'))),hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');assert.equal(hash(path.join(base,'roundball-rock-8bit.mp3')),meta.audioSha256);assert.equal(hash(path.join(base,'../scripts/music/nba-nbc.mid')),meta.sourceSha256);assert(meta.seconds>70&&meta.seconds<80);});
  console.log(JSON.stringify({passed}));
})().catch(error=>{console.error(error);process.exitCode=1;});
