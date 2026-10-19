'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const base=path.resolve(__dirname,'..'),read=n=>JSON.parse(fs.readFileSync(path.join(base,n))),sha=n=>crypto.createHash('sha256').update(fs.readFileSync(path.join(base,n))).digest('hex');
const A=require('../analyst.js'),H=require('../scouting_history.js'),P=require('../parlay.js'),T=require('../parlay_transition.js'),R=require('../parlay_research.js');
const archive=read('analyst_data.json'),supplement=read('parlay_data.json'),manifest=read('seasons/2026-27/manifest.json'),current=read('seasons/2026-27/versions/'+manifest.activeVersion);
const storage=new Map(),states=['regular-season',{},P.FIRST_TARGETS[0],'','auto',true,{}];let state=0,blob,requested=false;
const hashes=Object.fromEntries(['parlay.js','scouting_history.js','lineups.js','lineup_projections.js','parlay_transition.js','parlay_research.js','parlay_research_config.js','parlay_ui.js','analyst_ui.js'].map(n=>[n,sha(n)]));
const w={FTBParlay:P,FTBParlayTransition:T,FTBParlayResearch:R,FTBLineups:require('../lineups.js'),FTBProjectedLineups:require('../lineup_projections.js'),__FTB_PARLAY_RESEARCH_CONFIG__:read('parlay_research_config.json')};
const context=vm.createContext({window:w,Date,Blob,localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
  URL:{createObjectURL:b=>{blob=b;return 'blob:integration-test';},revokeObjectURL:()=>{}},document:{createElement:()=>({click:()=>{requested=true;}})},setTimeout:fn=>fn(),
  React:{createElement:(type,props,...children)=>({type,props,children}),useState:initial=>[states[state++]??initial,()=>{}],useMemo:fn=>fn(),useEffect:()=>{},useRef:()=>({current:null})}});
vm.runInContext(fs.readFileSync(path.join(base,'parlay_ui.js'),'utf8'),context);
const prior=P.build(A,H,archive,supplement,{mode:'review',phase:'regular-season'});
const fixture={id:'test-fixture',date:'2026-10-20',season:'2026-27',phase:'regular-season',status:'pre',home:'NYK',away:'SAS'};
const lineupContext={checkedAt:'2026-10-20T20:00Z',confirmed:{},projected:{test:{id:'test',team:'SAS',status:'projected',origin:'espn-depth',source:'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/24/depthcharts',capturedAt:'2026-10-20T20:00Z',fixtureId:fixture.id,date:fixture.date}},issues:[]};
const tree=w.FTBParlayPanel({A,H,data:current,supplement:current.parlay,archiveData:archive,archiveSupplement:supplement,options:{mode:'pregame',date:'2026-10-20'},phase:'regular-season',period:0,
  teams:['NYK','SAS'],fixtures:[fixture],rosters:prior.snapshot.rosters,acrossStints:true,excludedIds:[],trusted:true,liveContext:{upcoming:true,now:Date.now(),lineupContext},
  refreshMetadata:{publication:{parlayCodeHashes:hashes,researchProtocolHash:'test-protocol-hash'}}});
const nodes=[];function walk(n){if(!n||typeof n!=='object')return;nodes.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(tree);
nodes.find(n=>n.type==='button'&&n.children[0]==='Save selection evidence').props.onClick();
(async()=>{
  assert(requested);const downloaded=JSON.parse(await blob.text()),recovered=JSON.parse(storage.get('ftb-selection-audit-v1')).at(-1);
  assert.deepEqual(downloaded,recovered);assert.equal(downloaded.schemaVersion,3);assert.equal(downloaded.verifiedIssuedAt,null);assert.equal(downloaded.recordType,'research-snapshot');
  assert.deepEqual(downloaded.assumptions.lineupContext,lineupContext);assert.equal(downloaded.assumptions.lineupContext.projected.test.status,'projected');
  assert.equal(downloaded.selections.length,6);assert.deepEqual(downloaded.modelHashes,hashes);
  assert(downloaded.selections.every(s=>s.transition&&s.research&&s.fixture.id===fixture.id));
  assert(downloaded.selections.filter(s=>s.pick).every(s=>s.pick.provisional));
  for(const s of downloaded.selections.filter(s=>s.market!=='first-team-basket'&&s.pick&&s.research.pick&&s.pick.id===s.research.pick.id))assert.deepEqual(s.pick.seasonTarget,s.research.pick.seasonTarget);
  console.log('PASS actual UI JSON download payload matches recoverable browser record, six market slots, target contract and research metadata');
})().catch(e=>{console.error(e);process.exitCode=1;});
