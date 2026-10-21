const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../analyst.js'),H=require('../scouting_history.js'),base=path.join(__dirname,'..');
const archive=JSON.parse(fs.readFileSync(path.join(base,'analyst_data.json'))),canonical=JSON.parse(fs.readFileSync(path.join(base,'merged_dataset.json'))),report=JSON.parse(fs.readFileSync(path.join(base,'analyst_evaluation.json')));
const manifest=JSON.parse(fs.readFileSync(path.join(base,'seasons/2026-27/manifest.json'))),current={...JSON.parse(fs.readFileSync(path.join(base,'seasons/2026-27/versions',manifest.activeVersion))),health:manifest};
const names=['data','archive','basis','canonical','report','tab','mode','date','phase','period','target','season','schedule','gameId','rosters','injuries','pbp','sources','error','busy','expanded','sort','limit','scenario','showOut','journalMessage','now','gradeBasis','health','journal','historyScope','lineups','starterScope'];
function render(overrides={},published=true,response={canonical,analysis:archive,evaluation:report},clock=Date,useInitialState=false){
  const fixture={id:'future',date:'2026-10-20',home:'SAS',away:'OKC',season:'2026-27',phase:'regular-season',status:'pre'};
  const defaults=[archive,archive,'auto',canonical,report,'data','review','2026-06-13','all','0',A.DEFAULT_TARGET,'2025-26',[],'all',{}, {},null,{},null,false,null,'grade',40,{},false,'',Date.now(),'history',null,null,'all-opponents',{confirmed:{},projected:{},issues:[]}];
  defaults.push('confirmed');
  const values=defaults.map((v,i)=>names[i] in overrides?overrides[names[i]]:v),changes={},requests=[],effects=[],initialState={};let index=0;
  const window={__FTB_ANALYST_DATA__:archive,__FTB_MERGED__:canonical,__FTB_ANALYST_EVALUATION__:report,FTBScoutingHistory:H,FTBAnalyst:A,FTBLineups:require('../lineups.js'),...(published?{__FTB_HOSTING__:{mode:'github-pages',publishedDate:'2026-10-09'}}:{})};
  const context=vm.createContext({window,React:{createElement:(type,props,...children)=>({type,props,children}),Fragment:'fragment',useState:initial=>{const i=index++;if(useInitialState)values[i]=typeof initial==='function'?initial():initial;initialState[names[i]]=values[i];return[values[i],next=>{changes[names[i]]=typeof next==='function'?next(changes[names[i]]??values[i]):next;}];},useEffect:(fn,deps)=>effects.push({fn,deps}),useMemo:fn=>fn(),useRef:()=>({current:0})},fetch:async(url,options)=>{requests.push({url,options});return{ok:true,json:async()=>/2026-27(?:\.json)?$/.test(url)?current:response};},Date:clock,Intl,Number,String,Set,Object,JSON,AbortSignal});
  window.React=context.React;vm.runInContext(fs.readFileSync(path.join(base,'lineup_projections.js'),'utf8'),context);
  window.FTBMatchup=require('../matchup.js');vm.runInContext(fs.readFileSync(path.join(base,'matchup_ui.js'),'utf8'),context);
  for(const file of ['ev_probability.js','ev_model.js','ev_ui.js'])vm.runInContext(fs.readFileSync(path.join(base,file),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(base,'analyst_ui.js'),'utf8'),context);
  const tree=window.FTBAnalystApp(),buttons=[];function walk(n){if(!n||typeof n!=='object')return;if(n.type==='button'&&typeof n.children[0]==='string')buttons.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(tree);
  return {window,tree,requests,effects,changes,initialState,fixture,button:label=>{const found=buttons.find(b=>b.children[0]===label);assert(found,label);return found;}};
}
let count=0;async function test(name,fn){await fn();count++;console.log('PASS '+name);}
(async()=>{
  await test('fresh loads open upcoming Picks on the Chicago date and fetch that slate and season',async()=>{
    class Clock extends Date{constructor(...args){super(...(args.length?args:['2026-10-22T03:00:00Z']));}static now(){return Date.parse('2026-10-22T03:00:00Z');}}
    const response={events:[{id:'today',date:'2026-10-22T01:30Z',season:{year:2027,type:2},status:{type:{state:'pre'}},competitions:[{competitors:[{homeAway:'home',team:{abbreviation:'SA'}},{homeAway:'away',team:{abbreviation:'OKC'}}]}]}]};
    for(const published of [true,false]){
      const r=render({},published,response,Clock,true);
      for(const [key,value] of Object.entries({tab:'picks',mode:'upcoming',date:'2026-10-21',season:'2026-27',gameId:'all',phase:'all',period:'0',basis:'auto'}))assert.equal(r.initialState[key],value,key);
      r.effects.find(e=>e.deps?.length===1&&e.deps[0]==='2026-27').fn();
      r.effects.find(e=>e.deps?.includes('upcoming')&&e.deps.includes('2026-10-21')&&e.deps.includes('2026-27')).fn();
      await new Promise(setImmediate);
      assert(r.requests.some(q=>q.url===(published?'data/seasons/2026-27.json':'/api/seasons/2026-27')));
      assert(r.requests.some(q=>q.url.includes('scoreboard?dates=20261021&')));
      assert.equal(r.changes.data,current);assert.equal(r.changes.sources['season history'].status,'verified in progress');assert.equal(r.changes.schedule[0].id,'today');
    }
  });
  await test('static reads resolve underneath the GitHub project URL',()=>{const r=render(),ui=r.window.FTBAnalystUI;assert(ui.publishedSite);for(const [input,expected] of [['/api/history','data/history.json'],['/api/seasons/2026-27','data/seasons/2026-27.json']])assert.equal(new URL(ui.serviceUrl(input),'https://example.github.io/ftb-updated-model/ftb-scout.html').pathname,'/ftb-updated-model/'+expected);});
  await test('local app retains its Python service routes',()=>{const ui=render({},false).window.FTBAnalystUI;assert(!ui.publishedSite);assert.equal(ui.serviceUrl('/api/history'),'/api/history');assert.equal(ui.serviceUrl('/api/seasons/2026-27'),'/api/seasons/2026-27');});
  await test('published reload atomically adopts coherent canonical analysis and evaluation',async()=>{const r=render();await r.button('Reload verified history').props.onClick();assert.equal(r.requests.length,1);assert.equal(r.requests[0].url,'data/history.json');assert.equal(r.changes.canonical,canonical);assert.equal(r.changes.archive,archive);assert.equal(r.changes.report,report);assert.equal(r.changes.sources.history.status,'verified');});
  await test('mismatched published evaluation retains the last verified dataset',async()=>{const r=render({},true,{canonical,analysis:archive,evaluation:{...report,evidenceContentHash:'wrong'}});await r.button('Reload verified history').props.onClick();assert.equal(r.changes.canonical,undefined);assert.equal(r.changes.archive,undefined);assert.equal(r.changes.report,undefined);assert.match(r.changes.error,/last verified history retained/);});
  await test('published current-season loader reads a separate versioned snapshot',async()=>{const r=render({data:current,season:'2026-27'});r.effects.find(e=>e.deps.length===1&&e.deps[0]==='2026-27').fn();await new Promise(setImmediate);assert.equal(r.requests.length,1);assert.equal(r.requests[0].url,'data/seasons/2026-27.json');assert.equal(r.changes.data.meta.season,'2026-27');assert.equal(r.changes.data.games.length,current.games.length);assert.equal(r.changes.health.evidenceContentHash,manifest.evidenceContentHash);});
  await test('published collection rebuild import and settlement controls are disabled',async()=>{const r=render({data:current,season:'2026-27'});for(const label of ['Collect selected day','Rebuild from canonical workbook','Import canonical JSON','Update completed basketball outcomes'])assert.equal(r.button(label).props.disabled,true,label);for(const label of ['Collect selected day','Rebuild from canonical workbook','Update completed basketball outcomes'])await r.button(label).props.onClick();assert.equal(r.requests.length,0);});
  await test('published journal panel never requests a local backend',async()=>{const r=render();r.effects.find(e=>e.deps.length===1&&e.deps[0]==='data').fn();await new Promise(setImmediate);assert.equal(r.requests.length,0);assert.equal(r.changes.journal,null);});
  await test('published forecast recording is guarded even when its handler is invoked',async()=>{const fixture={id:'future',date:'2026-10-20',home:'SAS',away:'OKC',season:'2026-27',phase:'regular-season',status:'pre'};const r=render({tab:'picks',data:current,season:'2026-27',mode:'upcoming',date:fixture.date,schedule:[fixture],gameId:'future',rosters:{SAS:[],OKC:[]}});const b=r.button('Record pregame forecast');assert(b.props.disabled);await b.props.onClick();assert.equal(r.requests.length,0);assert.match(r.changes.journalMessage,/local app/);});
  await test('both upcoming screens render the same sourced projection panel',()=>{
    const now=Date.parse('2026-10-18T20:00Z'),fixture={id:'advance',date:'2026-10-20',scheduledTipoff:'2026-10-20T19:00Z',home:'DET',away:'BOS',season:'2026-27',phase:'regular-season',status:'pre'};
    const projected=Object.fromEntries(['PG','SG','SF','PF','C'].map((position,i)=>[String(i+1),{id:String(i+1),name:'Projected '+(i+1),team:'BOS',position,status:'projected',origin:'espn-depth',fixtureId:fixture.id,date:fixture.date,season:fixture.season,source:'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/2/depthcharts',capturedAt:new Date(now).toISOString()}]));
    const lineupContext={confirmed:{},projected,issues:[],checkedAt:new Date(now).toISOString()};
    function nodes(tree){const result=[];function walk(n){if(!n||typeof n!=='object')return;result.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(tree);return result;}
    for(const tab of ['picks','parlay']){
      const r=render({tab,data:current,season:'2026-27',mode:'upcoming',date:fixture.date,schedule:[fixture],now,lineups:lineupContext});
      const panels=nodes(r.tree).filter(n=>n.type===r.window.FTBLineupPanel);assert.equal(panels.length,1);
      const panel=panels[0].type(panels[0].props),all=nodes(panel);
      assert(all.some(n=>n.type==='strong'&&n.children[0]==='Depth-chart projection · unconfirmed'));
      assert.equal(all.filter(n=>n.type==='li').length,5);
      assert(all.some(n=>n.type==='a'&&n.props.href===projected['1'].source));
      assert(!all.some(n=>n.type==='strong'&&n.children[0]==='NBA confirmed starters'));
    }
  });
  await test('a lineup refresh advances the view clock past new capture timestamps',async()=>{
    const fixture={id:'advance',date:'2026-10-20',scheduledTipoff:'2026-10-20T19:00Z',home:'DET',away:'BOS',season:'2026-27',phase:'regular-season',status:'pre'};
    const r=render({tab:'picks',data:current,season:'2026-27',mode:'upcoming',date:fixture.date,schedule:[fixture],now:Date.parse('2026-10-18T20:00Z')});
    const nodes=[];function walk(n){if(!n||typeof n!=='object')return;nodes.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(r.tree);
    const panel=nodes.find(n=>n.type===r.window.FTBLineupPanel);await panel.props.onRefresh();
    assert(Number.isFinite(r.changes.now));assert(r.changes.now>=Date.parse(r.changes.lineups.checkedAt));
  });
  await test('the EV tab receives current rosters and its own unmodified pregame evidence context',()=>{
    const fixture={id:'ev-game',date:'2026-10-20',scheduledTipoff:'2026-10-20T19:00Z',home:'DET',away:'BOS',season:'2026-27',phase:'regular-season',status:'pre'};
    const roster={BOS:[{id:'1',name:'Player',team:'BOS'}],DET:[]},r=render({tab:'ev',data:current,season:'2026-27',mode:'upcoming',date:fixture.date,schedule:[fixture],rosters:roster});
    const found=[];function walk(n){if(!n||typeof n!=='object')return;if(n.type===r.window.FTBEVPanel)found.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(r.tree);
    assert.equal(found.length,1);assert.equal(found[0].props.mode,'upcoming');assert.equal(found[0].props.rosters,roster);assert.equal(found[0].props.archiveData,archive);assert.equal(found[0].props.liveContext.upcoming,true);
  });
  await test('Matchup receives raw selected-season evidence and exact fixture filters without a shared team snapshot',()=>{
    const fixtures=[{id:'1',date:'2026-10-20',away:'BOS',home:'DET'},{id:'2',date:'2026-10-20',away:'OKC',home:'SAS'}];
    const r=render({tab:'matchup',data:current,season:'2026-27',mode:'upcoming',date:'2026-10-20',schedule:fixtures,gameId:'2',phase:'regular-season',period:'5',historyScope:'head-to-head',basis:'current'});
    const nodes=[];function walk(n){if(!n||typeof n!=='object')return;nodes.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(r.tree);
    const p=nodes.find(n=>n.type===r.window.FTBMatchupPanel);assert(p);assert.equal(p.props.data,current);assert.equal(p.props.archiveData,archive);assert.equal(p.props.fixtures.length,1);assert.equal(p.props.fixtures[0].id,'2');
    assert.deepEqual(JSON.parse(JSON.stringify(p.props.options)),{date:'2026-10-20',mode:'upcoming',phase:'regular-season',window:'5',basis:'current',headToHead:true});
    for(const label of ['Grading basis','Scoring target'])assert.equal(nodes.find(n=>n.props?.['aria-label']===label).props.disabled,true);
  });
  await test('Today shortcut uses the Chicago date and restores the full upcoming research scope',()=>{
    class Clock extends Date{constructor(...args){super(...(args.length?args:['2026-10-20T03:00:00Z']));}static now(){return Date.parse('2026-10-20T03:00:00Z');}}
    const r=render({tab:'matchup',phase:'playoffs',period:'5',historyScope:'head-to-head',basis:'archive',scenario:{one:'out'},expanded:'one'},true,{},Clock);
    r.button('Today · Upcoming').props.onClick();
    for(const [key,value] of Object.entries({season:'2026-27',mode:'upcoming',date:'2026-10-19',gameId:'all',phase:'all',period:'0',basis:'auto',historyScope:'all-opponents',expanded:null,error:null}))assert.equal(r.changes[key],value,key);
    assert.equal(Object.keys(r.changes.scenario).length,0);assert(!('tab' in r.changes));
  });
  await test('season-only switches reload fixtures and Today refreshes an already-current slate',async()=>{
    const response={events:[{id:'opening',date:'2026-10-20T19:00Z',season:{year:2027,type:2},status:{type:{state:'pre',shortDetail:'3:00 PM EDT'}},competitions:[{competitors:[{homeAway:'home',team:{abbreviation:'DET'}},{homeAway:'away',team:{abbreviation:'BOS'}}]}]}]};
    class Clock extends Date{constructor(...args){super(...(args.length?args:['2026-10-20T06:00:00Z']));}static now(){return Date.parse('2026-10-20T06:00:00Z');}}
    const r=render({season:'2026-27',mode:'upcoming',date:'2026-10-20'},true,response,Clock),scheduleEffect=r.effects.find(e=>e.deps?.includes('upcoming')&&e.deps.includes('2026-27'));
    assert(scheduleEffect,'A season-only switch must refresh the cleared schedule');scheduleEffect.fn();await new Promise(setImmediate);assert.equal(r.changes.schedule[0].id,'opening');assert.equal(r.changes.schedule[0].season,'2026-27');
    const requests=r.requests.length;r.button('Today · Upcoming').props.onClick();await new Promise(setImmediate);assert.equal(r.requests.length,requests+1);assert.equal(r.changes.schedule.length,1);assert.equal(r.changes.schedule[0].home,'DET');
  });
  await test('scheduled labels use Central daylight and standard time without rewriting game status',()=>{
    const format=render().window.FTBAnalystUI.scheduleLabel;
    assert.match(format({status:'pre',statusText:'3:00 PM EDT',scheduledTipoff:'2026-10-20T19:00Z'}),/2:00 PM CT/);
    assert.match(format({status:'pre',scheduledTipoff:'2026-12-20T19:00Z'}),/1:00 PM CT/);
    assert.match(format({status:'pre',scheduledTipoff:'2026-10-21T01:30Z'}),/10\/20.*8:30 PM CT/);
    for(const text of ['Postponed','Canceled','Time TBD'])assert.equal(format({status:'pre',statusText:text,scheduledTipoff:'2026-10-20T19:00Z'}),text);
    assert.equal(format({status:'post',statusText:'Final',scheduledTipoff:'2026-10-20T19:00Z'}),'Final');
    assert.equal(format({status:'in',statusText:'Q3 5:00',scheduledTipoff:'2026-10-20T19:00Z'}),'Q3 5:00');
    assert.equal(format({status:'pre',statusText:'Scheduled',scheduledTipoff:null}),'Scheduled');
  });
  const feedNow=Date.parse('2026-10-20T18:30Z'),feedFixture={id:'feed',date:'2026-10-20',home:'DET',away:'BOS',season:'2026-27',phase:'regular-season',status:'pre',scheduledTipoff:'2026-10-20T19:00Z'};
  const box=archive.games.find(g=>g.teams.BOS).teams.BOS,feedRoster=box.players.map(p=>({id:p.id,name:p.name,team:'BOS',rawPosition:p.rawPosition||''})),five=box.players.filter(p=>p.played&&p.starter).map((p,i)=>({id:p.id,name:p.name,team:'BOS',position:['PG','SG','SF','PF','C'][i],status:'confirmed',nbaId:String(i+1),fixtureId:feedFixture.id,date:feedFixture.date,capturedAt:new Date(feedNow).toISOString(),source:require('../lineups.js').urlFor(feedFixture.date)}));
  const feedLineups={confirmed:Object.fromEntries(five.map(p=>[p.id,p])),projected:{},issues:[]},feedOptions={tab:'picks',data:current,season:'2026-27',mode:'upcoming',date:feedFixture.date,schedule:[feedFixture],now:feedNow,rosters:{BOS:feedRoster},lineups:feedLineups};
  const feedSelect=render().window.FTBAnalystUI.starterFeed;
  function nodes(tree){const all=[];function walk(n){if(Array.isArray(n))return n.forEach(walk);if(!n||typeof n!=='object')return;all.push(n);(n.children||[]).forEach(walk);}walk(tree);return all;}
  const cardNames=r=>nodes(r.tree).filter(n=>n.type?.name==='PlayerCard').map(n=>n.props.p.name);
  await test('upcoming Picks shows only the same complete NBA-confirmed five as the shared lineup panel',()=>{
    const r=render(feedOptions),names=cardNames(r);assert.equal(names.length,5);assert.equal(names.sort().join('|'),five.map(p=>p.name).sort().join('|'));
    const scope=nodes(r.tree).find(n=>n.props?.['aria-label']==='Starter feed');assert.equal(scope.props.value,'confirmed');scope.props.onChange({target:{value:'projected'}});assert.equal(r.changes.starterScope,'projected');assert.equal(r.changes.expanded,null);
    const top=nodes(r.tree).find(n=>n.type?.name==='TopResearch');assert(five.some(p=>p.id===top.props.p.id));
  });
  await test('projected fives require explicit opt-in and cannot enter the default starter feed',()=>{
    const projected=Object.fromEntries(five.map(p=>[p.id,{...p,status:'projected',origin:'espn-depth',season:feedFixture.season,source:'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/2/depthcharts'}]));
    assert.equal(cardNames(render({...feedOptions,lineups:{confirmed:{},projected}})).length,0);
    const r=render({...feedOptions,starterScope:'projected',lineups:{confirmed:{},projected}});assert.equal(cardNames(r).length,5);
    assert(nodes(r.tree).filter(n=>n.type?.name==='PlayerCard').every(n=>/unconfirmed/.test(n.props.p.lineupStatus)));
  });
  await test('fresh confirmation replaces the projected five, including a changed fifth starter',()=>{
    const bench=feedRoster.find(p=>!five.some(s=>s.id===p.id));assert(bench);
    const replaced=five.map((p,i)=>i===4?{...p,id:bench.id,name:bench.name}:p),projected=Object.fromEntries(five.map(p=>[p.id,{...p,status:'projected',origin:'espn-depth',season:feedFixture.season,source:'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/2/depthcharts'}]));
    const selected=feedSelect(feedRoster,[feedFixture],{confirmed:Object.fromEntries(replaced.map(p=>[p.id,p])),projected},feedNow,{includeProjected:true});
    assert(selected.players.some(p=>p.id===bench.id));assert(!selected.players.some(p=>p.id===five[4].id));assert.equal(selected.confirmedTeams,1);assert.equal(selected.projectedTeams,0);
  });
  await test('expired, partial, mismatched and roster-unresolved confirmations fail closed',()=>{
    assert.equal(feedSelect(feedRoster,[feedFixture],feedLineups,feedNow+300001).players.length,0);
    const partial={...feedLineups,confirmed:Object.fromEntries(five.slice(0,4).map(p=>[p.id,p]))};assert.equal(feedSelect(feedRoster,[feedFixture],partial,feedNow).players.length,0);
    const wrong={...feedLineups,confirmed:Object.fromEntries(five.map(p=>[p.id,{...p,fixtureId:'other'}]))};assert.equal(feedSelect(feedRoster,[feedFixture],wrong,feedNow).players.length,0);
    assert.equal(feedSelect(feedRoster.filter(p=>p.id!==five[0].id),[feedFixture],feedLineups,feedNow).players.length,0);
  });
  await test('tipoff, completed games and unavailable schedules close the pregame cards',()=>{
    for(const fixture of [{...feedFixture,status:'post'},{...feedFixture,scheduledTipoff:new Date(feedNow).toISOString()},{...feedFixture,scheduledTipoff:null},{...feedFixture,statusText:'Postponed'}])assert.equal(feedSelect(feedRoster,[fixture],feedLineups,feedNow).players.length,0);
  });
  await test('scenario assumptions and Show excluded cannot promote a bench player into the starter feed',()=>{
    const bench=feedRoster.find(p=>!five.some(s=>s.id===p.id));const r=render({...feedOptions,showOut:true,scenario:{[bench.id]:'starter'}});assert.equal(cardNames(r).length,5);assert(!cardNames(r).includes(bench.name));
    assert.equal(cardNames(render({...feedOptions,lineups:{confirmed:{},projected:{}},scenario:{[bench.id]:'starter'}})).length,0);
  });
  await test('main-feed filtering leaves historical research and other tabs on their existing roster scope',()=>{
    const r=render({tab:'picks'});assert(!nodes(r.tree).some(n=>n.props?.['aria-label']==='Starter feed'));assert(cardNames(r).length>5);
    for(const tab of ['parlay','ev','matchup'])assert(!nodes(render({...feedOptions,tab}).tree).some(n=>n.props?.['aria-label']==='Starter feed'));
  });
  console.log(JSON.stringify({passed:count}));
})().catch(error=>{console.error(error);process.exitCode=1;});
