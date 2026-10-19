const assert=require('node:assert/strict'),M=require('../matchup.js'),archive=require('../analyst_data.json');
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
const opts={date:'2026-10-20',mode:'upcoming',phase:'all',window:'0',trusted:true};
const fixtures=[['BOS','DET'],['PHI','NYK'],['OKC','SAS']].map(([away,home],i)=>({id:'f'+i,date:opts.date,away,home,season:'2026-27'}));
const current={meta:{season:'2026-27',asOfDate:null},games:[]};
const report=M.build(current,archive,fixtures,opts);
test('every fixture owns two correctly keyed comparisons and distinct opponent records',()=>{
  assert.equal(report.comparisons.length,3);
  for(const [i,c] of report.comparisons.entries()){assert.equal(c.season,'2025-26');assert(c.isArchive);assert.deepEqual(c.directions.map(d=>[d.production.team,d.allowance.team]),[[fixtures[i].away,fixtures[i].home],[fixtures[i].home,fixtures[i].away]]);}
  assert.notDeepEqual(M.rows(report.comparisons[0].directions[0],'points','per48'),M.rows(report.comparisons[2].directions[0],'points','per48'));
});
test('appearance roles stay broad or unknown without invented five-position assignments',()=>{
  assert.equal(M.position({officialPosition:'G',rawPosition:'PG'},'strict'),'unknown');
  assert.equal(M.position({rawPosition:'SG'},'broad'),'G');assert.equal(M.position({officialPosition:'F',rawPosition:'C'},'broad'),'F');
  for(const p of ['',null,'F-C','G-F','unrecorded'])assert.equal(M.position({rawPosition:p}),'unknown');
});
test('season totals reconcile all six box-score metrics without losing unknown roles',()=>{
  const c=report.comparisons[0];for(const [metric,total] of Object.entries({points:304328,blocks:12858,rebounds:115498,offensiveRebounds:30054,defensiveRebounds:85444,assists:70096})){
    assert.equal(c.reference[metric].total,total);assert.equal(Object.values(c.reference[metric].buckets).reduce((n,b)=>n+b.total,0),total);assert.equal(c.reference[metric].missing,0);
  }assert.equal(c.reference.firstTeam.total,2644);
});
test('per-minute, per-game and share denominators are independently reproducible',()=>{
  const own=report.comparisons[0].directions[0].production.own.points,b=own.buckets.G;
  assert.equal(M.value(own,'G','per48'),b.total*2880/b.seconds);assert.equal(M.value(own,'G','perGame'),b.total/89);assert.equal(M.value(own,'G','share'),100*b.total/own.total);
});
test('all competition and rolling filters select only each team’s own sample',()=>{
  for(const phase of ['all','regular-season','playoffs','regular-and-playoffs','play-in','nba-cup-final'])for(const window of ['0','5','10','20']){
    const r=M.build(archive,archive,fixtures,{...opts,mode:'review',phase,window});
    for(const c of r.comparisons)for(const d of c.directions)for(const t of [d.production,d.allowance]){
      const expected=archive.games.filter(g=>[g.home,g.away].includes(t.team)&&(phase==='all'||(phase==='regular-and-playoffs'?['regular-season','playoffs'].includes(g.phase):g.phase===phase))).slice(Number(window)?-Number(window):0);
      assert.deepEqual(t.gameIds,expected.map(g=>g.id));
      assert.equal(t.own.points.games,expected.length);assert.equal(t.against.assists.games,expected.length);
    }
  }
});
test('head-to-head is the exact unordered pair and correctly identical event comparison',()=>{
  const r=M.build(current,archive,fixtures,{...opts,headToHead:true,window:'5'});
  for(const c of r.comparisons){const d=c.directions[0];assert.deepEqual(d.production.gameIds,d.allowance.gameIds);for(const id of d.production.gameIds){const g=archive.games.find(g=>g.id===id);assert.deepEqual([g.away,g.home].sort(),[c.fixture.away,c.fixture.home].sort());}for(const metric of Object.keys(M.METRICS))assert.deepEqual(d.production.own[metric],d.allowance.against[metric]);}
});
test('historical pregame excludes selected day and future values or current roster changes',()=>{
  const fixture={...fixtures[0],date:'2025-10-23'},o={...opts,date:fixture.date,mode:'pregame'};
  const a=M.build(archive,archive,[fixture],o);const changed={...archive,games:archive.games.map(g=>g.date>=o.date?{...g,teams:{}}:g),rosters:{BOS:[{id:'FAKE',position:'C'}]}};
  assert.deepEqual(M.build(changed,archive,[fixture],o),a);for(const d of a.comparisons[0].directions)for(const s of [d.production,d.allowance])assert(!s.through||s.through<o.date);
});
test('automatic descriptive history switches as soon as both teams have eligible evidence',()=>{
  const mini={...archive,meta:{...archive.meta,season:'2026-27'}};
  const r=M.build(mini,archive,[fixtures[0]],opts);assert(!r.comparisons[0].isArchive);assert.equal(r.comparisons[0].season,'2026-27');
  assert(M.build(mini,archive,[fixtures[0]],{...opts,basis:'archive'}).comparisons[0].isArchive);
});
test('current-only and empty head-to-head never silently substitute broader samples',()=>{
  const c=M.build(current,archive,[fixtures[0]],{...opts,basis:'current'}).comparisons[0];assert.equal(c.directions[0].production.games,0);assert(M.rows(c.directions[0],'points','per48').every(r=>r.production===null));
  const f={...fixtures[0],away:'NO-SUCH-TEAM'};assert.equal(M.build(current,archive,[f],{...opts,headToHead:true}).comparisons[0].directions[0].production.games,0);
});
const p=(id,pos,stats={})=>({id,rawPosition:pos,played:true,statsSource:'https://stats.nba.com/pdfs/box.pdf',statsSourceHash:'a'.repeat(64),minutesSeconds:1200,points:10,blocks:1,rebounds:4,offensiveRebounds:1,defensiveRebounds:3,assists:2,...stats});
const game=(id,date,home='A',away='B')=>({id,date,home,away,phase:'regular-season',teams:{[home]:{players:[p('1','G')]},[away]:{players:[p('2','C',{points:20,blocks:3,assists:6})]}},firstScores:{[home]:{id:'1'},[away]:{id:'2'}},firstFieldGoals:{[home]:{id:'1'},[away]:{id:'2'}}});
test('blocks are credited to blocker and assists to passer, not the opposing player',()=>{
  const s=M.aggregate([game('g','2026-01-01')],'A',{positions:'broad'});
  assert.equal(s.own.blocks.buckets.G.total,1);assert.equal(s.against.blocks.buckets.C.total,3);assert.equal(s.own.assists.buckets.G.total,2);assert.equal(s.against.assists.buckets.C.total,6);
});
test('played zero-minute rows, DNPs, missing minutes and missing counts remain distinct',()=>{
  const g=game('g','2026-01-01');g.teams.A.players.push(p('3','G',{played:false,points:1000}),p('4','F',{minutesSeconds:0,points:2}));
  let s=M.aggregate([g],'A',{positions:'broad'});assert.equal(s.own.points.total,12);assert.equal(s.own.points.appearances,2);assert.equal(M.value(s.own.points,'F','per48'),null);assert.equal(M.value(s.own.points,'F','perGame'),2);
  g.teams.A.players[0].minutesSeconds=null;s=M.aggregate([g],'A',{positions:'broad'});assert.equal(M.value(s.own.points,'G','per48'),null);assert.equal(M.value(s.own.points,'G','perGame'),10);
  g.teams.A.players[0].points=null;s=M.aggregate([g],'A',{positions:'broad'});assert.equal(M.value(s.own.points,'G','perGame'),null);assert.equal(M.value(s.own.points,'F','share'),null);assert.equal(s.own.points.total,null);
});
test('unverified counts, duplicate games and duplicate identities fail explicitly',()=>{
  const g=game('g','2026-01-01'),data={meta:{season:'2025-26',asOfDate:g.date},games:[g,g]};assert.throws(()=>M.build(data,null,[],opts),/Duplicate game/);
  g.teams.A.players.push(g.teams.A.players[0]);assert.throws(()=>M.aggregate([g],'A',{positions:'broad'}),/Duplicate or missing player/);g.teams.A.players.pop();g.teams.A.players[0].statsSource='https://notnba.com/fake.pdf';assert.equal(M.aggregate([g],'A',{positions:'broad'}).own.points.total,null);
});
test('first-team FT and FG targets change only opening counts, and missing evidence is unavailable',()=>{
  const g=game('g','2026-01-01');g.teams.A.players.push(p('3','F'));g.firstFieldGoals.A={id:'3'};
  const a=M.aggregate([g],'A',{positions:'broad'}),b=M.aggregate([g],'A',{positions:'broad',firstTarget:'field-goals'});assert.equal(a.own.firstTeam.buckets.G.total,1);assert.equal(b.own.firstTeam.buckets.F.total,1);assert.deepEqual(a.own.points,b.own.points);
  delete g.firstScores.A;assert.equal(M.aggregate([g],'A',{positions:'broad'}).own.firstTeam.total,null);
});
test('traded players retain each appearance’s team and role',()=>{
  const g1=game('g1','2026-01-01'),g2=game('g2','2026-01-02','C','A');g2.teams.C.players=[p('1','F',{points:30})];g2.teams.A.players=[p('new','C',{points:3})];
  const a=M.aggregate([g1,g2],'A',{positions:'broad'}),c=M.aggregate([g2],'C',{positions:'broad'});assert.equal(a.own.points.total,13);assert.equal(a.own.points.buckets.G.total,10);assert.equal(c.own.points.buckets.F.total,30);
});
test('invalid scope, date and failed evidence validation do not yield estimates',()=>{
  for(const o of [{phase:'fake'},{window:7},{date:'invalid'},{trusted:false}])assert.throws(()=>M.build(current,archive,fixtures,{...opts,...o}));assert.throws(()=>M.build(current,archive,[{...fixtures[0],date:'2026-10-21'}],opts),/game date/);
});
console.log(JSON.stringify({passed:count}));
