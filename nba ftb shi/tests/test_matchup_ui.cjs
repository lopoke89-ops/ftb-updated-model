const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const M=require('../matchup.js'),H=require('../scouting_history.js'),archive=require('../analyst_data.json'),base=path.join(__dirname,'..');
const current={meta:{season:'2026-27',asOfDate:null},games:[]},fixture={id:'BOSDET',date:'2026-10-20',away:'BOS',home:'DET'};
function render({state=['points','broad','per48','including-free-throws'],fixtures=[fixture],options={},trusted=true}={}){
  let index=0;const changes={},window={FTBMatchup:M,FTBScoutingHistory:H};
  const React={Fragment:'fragment',createElement:(type,props,...children)=>({type,props:props||{},children}),useState:initial=>{const i=index++;return[state[i]??initial,v=>changes[i]=v];},useMemo:fn=>fn()};
  vm.runInNewContext(fs.readFileSync(path.join(base,'matchup_ui.js'),'utf8'),{window,React,Number});
  function expand(n){if(Array.isArray(n))return n.map(expand);if(!n||typeof n!=='object')return n;if(typeof n.type==='function')return expand(n.type(n.props));return {...n,children:n.children.map(expand)};}
  const tree=expand(window.FTBMatchupPanel({data:current,archiveData:archive,fixtures,options:{date:fixture.date,mode:'upcoming',phase:'all',window:'0',basis:'auto',...options},teamColors:{BOS:'#0a0',DET:'#f00'},trusted}));
  const nodes=[];function walk(n){if(Array.isArray(n))return n.forEach(walk);if(!n||typeof n!=='object')return;nodes.push(n);n.children.forEach(walk);}walk(tree);
  const text=n=>Array.isArray(n)?n.map(text).join(' '):n&&typeof n==='object'?n.children.map(text).join(' '):String(n??'');
  return {tree,nodes,text:text(tree),changes};
}
let passed=0;function test(name,fn){fn();passed++;console.log('PASS '+name);}
test('both directions and fixture keys render from actual selected teams',()=>{const r=render();assert.deepEqual(r.nodes.filter(n=>n.props.className==='matchup-direction').map(n=>[n.props['data-production-team'],n.props['data-allowance-team']]),[['BOS','DET'],['DET','BOS']]);assert(r.text.includes('2025-26 · prior-season history'));});
test('charts contain only position rows with two bars, not shared evidence or next charts',()=>{
  const r=render(),charts=r.nodes.filter(n=>n.props.className==='matchup-chart');assert.equal(charts.length,2);
  for(const c of charts){const rows=c.children.flat(Infinity).filter(n=>n&&typeof n==='object');assert.equal(rows.length,4);assert(rows.every(n=>n.props.className==='matchup-position'));}
});
test('every metric has independent labels, rates and correct attribution',()=>{
  for(const metric of Object.keys(M.METRICS))for(const rate of ['per48','perGame','share']){
    const r=render({state:[metric,'broad',rate,'including-free-throws']});assert.equal(r.nodes.filter(n=>n.props.className==='matchup-direction').length,2);
    if(metric==='blocks')assert(r.text.includes('player recording the block'));if(metric==='assists')assert(r.text.includes('passer’s position'));
    if(metric==='firstTeam'){assert(r.text.includes('one first score per team'));assert(r.nodes.some(n=>n.props['aria-label']==='Matchup opening score'));assert(!r.nodes.some(n=>n.props['aria-label']==='Matchup rate'));}
  }
});
test('strict mode reveals unknown coverage without relabeling broad positions',()=>{const r=render({state:['points','strict','per48']});assert(r.text.includes('Unknown roles:'));assert(r.text.includes('Point guards'));assert(r.text.includes('Unavailable'));});
test('current-only empty samples and absent fixtures produce explicit unavailable states',()=>{assert(render({options:{basis:'current'}}).text.includes('no completed games in this scope'));assert(render({fixtures:[]}).text.includes('No matchup on this selected date'));assert(render({trusted:false}).text.includes('failed validation'));});
test('rate, role and metric selectors update their own control states',()=>{const r=render();for(const [label,value,i] of [['Matchup statistic','blocks',0],['Matchup positions','strict',1],['Matchup rate','perGame',2]]){r.nodes.find(n=>n.props['aria-label']===label).props.onChange({target:{value}});assert.equal(r.changes[i],value);}});
test('first-team FT and FG control and global scope are independent from full-game scoring',()=>{const r=render({state:['firstTeam','broad','per48','field-goals'],options:{headToHead:true,window:'5'}});assert(r.text.includes('same head-to-head meetings'));assert(r.text.includes('last 5 meetings'));assert.equal(r.nodes.find(n=>n.props['aria-label']==='Matchup opening score').props.value,'field-goals');});
test('methodology is available in a collapsed disclosure without burying charts on phones',()=>{const r=render(),method=r.nodes.find(n=>n.props.className==='matchup-methodology');assert(method);assert.equal(method.props.open,undefined);assert(r.text.includes('do not move a traded player'));});
console.log(JSON.stringify({passed}));
