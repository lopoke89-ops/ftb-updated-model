'use strict';
const assert=require('node:assert/strict'),C=require('../ev_context.js');
const hash='a'.repeat(64),source=id=>'https://statsdmz.nba.com/pdfs/'+id+'.pdf',roles=C.POSITIONS;
function game(id,date,opponent,homeSG,awaySG,homeSeconds,awaySeconds){
 const players=(team,sg,seconds)=>roles.map((role,i)=>({id:team+i,name:team+' '+role,played:true,starter:true,officialPosition:i<2?'G':i<4?'F':'C',statsSource:source(id),statsSourceHash:hash,minutesSeconds:seconds,points:role==='SG'?sg:sg+i,threeMade:i,assists:i+1,rebounds:i+2,offensiveRebounds:1,defensiveRebounds:i+1}));
 const g={id,date,home:opponent,away:'BOS',phase:'regular-season',source:source(id),sourceHash:hash,teams:{[opponent]:{players:players(opponent,homeSG,homeSeconds)},BOS:{players:players('BOS',awaySG,awaySeconds)}}};
 g.roleEvidence=[opponent,'BOS'].flatMap(team=>roles.map((position,i)=>({gameId:id,playerId:team+i,team,position,effectiveGameDate:date,source:'https://stats.nba.com/js/data/leaders/00_daily_lineups_'+date.replaceAll('-','')+'.json',sourceHash:hash,gamebookSourceHash:hash,capturedAt:'2026-10-01T00:00:00Z'})));return g;
}
const games=[game('g1','2026-01-01','DET',4,10,1200,1200),game('g2','2026-01-02','DET',8,20,600,600),game('g3','2026-01-03','NYK',6,30,1200,1800)],archive={meta:{season:'2025-26',evidenceContentHash:hash},games},current={meta:{season:'2026-27',evidenceContentHash:'b'.repeat(64)},games:[]};
const fixture={id:'next',date:'2026-10-22',home:'DET',away:'BOS',season:'2026-27'},features={n:30,minutes:28,recentStarterRate:1,through:'2026-01-03',role:'G',histograms:{points:{10:2,20:3,30:1}}};
const row={quote:{playerId:'BOS1',team:'BOS',market:'points',side:'over',line:20},features,provisional:false,probabilities:{win:.6,loss:.4,push:0},ev:.1};
const view=position=>({label:'NBA expected starter Â· unconfirmed',teamStatus:'projected',record:{position,source:'expected-lineup',capturedAt:'2026-10-22T00:00:00Z'}});
const index=(a=archive,c=current)=>C.create({archive:a,current:c,trusted:true});
let n=0;function test(name,fn){fn();console.log('PASS '+name);n++;}
test('all five positions resolve independently, with explicit broad fallback',()=>{
 const x=index();for(const position of roles){const c=x.describe(row,fixture,view(position),{defensePower:.5});assert.equal(c.role.position,position);assert.equal(c.role.resolution,'five-position');assert.equal(c.status,'observed');}
 const a=structuredClone(archive);for(const g of a.games)delete g.roleEvidence;const c=index(a).describe(row,fixture,{},{});assert.equal(c.role.position,'G');assert.equal(c.role.resolution,'broad');assert.match(c.role.source,/exact current position unavailable/);
});
test('hand reconstructed exposure and defending-team-excluded baseline match',()=>{
 const c=index().describe(row,fixture,view('SG'),{defensePower:.5});assert.equal(c.profile.opposing.total,30);assert.equal(c.profile.opposing.seconds,1800);assert.equal(c.profile.opposing.per48,48);
 assert.equal(c.profile.baseline.total,48);assert.equal(c.profile.baseline.seconds,4800);assert.equal(c.profile.baseline.per48,28.8);assert.equal(c.profile.baseline.expectedGames,4);assert.equal(c.profile.opposing.games,2);assert(c.dataset.priorSeason);assert.equal(c.modelOpponent.alreadyIncluded,true);
});
test('source-matched complete supplement takes precedence over a sparse embedded role reference',()=>{
 const a={...archive,datedRoleEvidence:[games[0].roleEvidence[0]]},supplement={meta:{parentEvidenceContentHash:hash},datedRoleEvidence:games.flatMap(g=>g.roleEvidence)};
 const c=C.create({archive:a,current,supplement,trusted:true}).describe(row,fixture,view('SG'));assert.equal(c.role.position,'SG');assert.equal(c.role.resolution,'five-position');assert.equal(c.profile.opposing.total,30);
});
test('numerator and exposure exclude the same missing-stat or missing-minute row',()=>{
 for(const field of ['points','minutesSeconds']){const a=structuredClone(archive);delete a.games[1].teams.BOS.players[1][field];const c=index(a).describe(row,fixture,view('SG'));assert.equal(c.profile.opposing.total,10);assert.equal(c.profile.opposing.seconds,1200);assert.equal(c.profile.opposing.missingRows,1);assert.equal(c.profile.opposing.games,1);}
});
test('source mismatch, absent five roles and unknown roles never become fabricated SG observations',()=>{
 for(const mutate of [a=>a.games.forEach(g=>g.roleEvidence.find(r=>r.team==='BOS').gamebookSourceHash='wrong'),a=>a.games.forEach(g=>delete g.roleEvidence),a=>a.games.forEach(g=>g.roleEvidence.find(r=>r.team==='BOS').position='SG')]){const a=structuredClone(archive);mutate(a);const c=index(a).describe(row,fixture,view('SG'));assert.equal(c.role.position,'G');assert.equal(c.role.resolution,'broad');assert.equal(c.role.requestedPosition,'SG');assert.match(c.mainConcern,/broader role/);}
 const a=structuredClone(archive);for(const g of a.games)g.teams.BOS.players[1].statsSourceHash='wrong';assert.equal(index(a).describe(row,fixture,view('SG')).role.resolution,'broad');
});
test('selected-day/later outcomes and playoff records cannot change prior regular-season context',()=>{
 const baseline=index().describe(row,fixture,view('SG'));const a=structuredClone(archive);a.games.push(game('same',fixture.date,'DET',300,300,1800,1800),game('later','2026-10-23','DET',400,400,1800,1800));const p=game('playoff','2026-04-20','DET',500,500,1800,1800);p.phase='playoffs';a.games.push(p);assert.deepEqual(index(a).describe(row,fixture,view('SG')),baseline);
});
test('new season with opponent observations stays separate and never silently pools the archive',()=>{
 const g=game('new','2026-10-21','DET',2,3,1800,1800),c=index(archive,{...current,games:[g]}).describe(row,fixture,view('SG'));assert.equal(c.dataset.season,'2026-27');assert.equal(c.profile.opposing.total,3);assert.equal(c.profile.opposing.games,1);assert.equal(c.dataset.priorSeason,false);
});
test('bench broad group is not promoted to a historical starting role',()=>{
 const a=structuredClone(archive);for(const g of a.games){g.teams.BOS.players[1].starter=false;g.roleEvidence=g.roleEvidence.filter(r=>r.team!=='BOS');}const c=index(a).describe(row,fixture);assert.equal(c.role.position,'G');assert.equal(c.role.resolution,'broad');assert.match(c.opportunity.lineup,/unconfirmed/);
});
test('exact target hit/miss/push counts are descriptive and preserve zero and missing',()=>{
 assert.deepEqual(C.historicalTarget(features,row.quote),{wins:1,losses:2,pushes:3,n:6});assert.deepEqual(C.historicalTarget(features,{...row.quote,side:'at-least'}),{wins:4,losses:2,pushes:0,n:6});assert.equal(C.historicalTarget({},row.quote),null);
 const a=structuredClone(archive);for(const g of a.games)g.teams.BOS.players[1].points=0;const c=index(a).describe(row,fixture,view('SG'));assert.equal(c.profile.opposing.per48,0);assert.equal(c.status,'observed');
});
test('context does not mutate probabilities, EV, input histories or the model; cached samples are immutable',()=>{
 const a=structuredClone(archive),retained=index(a);a.games[0].teams.BOS.players[1].points=999;a.games[0].roleEvidence.find(r=>r.team==='BOS'&&r.position==='SG').position='PF';assert.equal(retained.describe(row,fixture,view('SG')).profile.opposing.total,30);
 const x=index(),before=JSON.stringify({row,archive});const c=x.describe(row,fixture,view('SG'),{defensePower:.5});assert.equal(JSON.stringify({row,archive}),before);assert(Object.isFrozen(c.profile.opposing));assert.throws(()=>{c.profile.opposing.total=999;},TypeError);assert.equal(x.describe(row,fixture,view('SG')).profile.opposing.total,30);
 const ladder=x.describe({...row,quote:{...row.quote,side:'at-least'}},fixture,view('SG'));assert.match(ladder.mainConcern,/tail accuracy/);assert(!('selection' in ladder));assert(!('probabilities' in ladder));assert(!('ev' in ladder));
});
test('missing trust, unsupported FTB and duplicate fixtures remain unavailable or rejected',()=>{
 assert(index(archive,{meta:{season:'2026-27'},games:[]}).describe(row,fixture,view('SG')).status==='observed');
 assert.equal(C.create({archive,current,trusted:false}).describe(row).status,'unavailable');assert.equal(index().describe({...row,quote:{...row.quote,market:'first-team-basket'}},fixture).status,'unavailable');const a=structuredClone(archive);a.games.push(a.games[0]);assert.throws(()=>index(a),/Duplicate context fixture/);
});
console.log(JSON.stringify({passed:n}));
