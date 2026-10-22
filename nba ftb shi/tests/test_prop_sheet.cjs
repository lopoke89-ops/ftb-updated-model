'use strict';
const assert=require('node:assert/strict'),C=require('../ev_context.js'),P=require('../prop_sheet.js');
const hash='a'.repeat(64),teams=C.TEAMS,roles=C.POSITIONS;
function fixture(home,away,day,id){
 const date='2026-01-'+String(day).padStart(2,'0'),url='https://statsdmz.nba.com/pdfs/'+id+'.pdf';
 const players=(own,defending)=>roles.map((position,i)=>{const n=teams.indexOf(defending);return {id:own+i,name:own+' '+position,played:true,starter:true,officialPosition:i<2?'G':i<4?'F':'C',minutesSeconds:1800,statsSource:url,statsSourceHash:hash,points:n+i,threeMade:Math.floor(n/3),assists:n+i,rebounds:n+i+1,offensiveRebounds:0,defensiveRebounds:n+i+1};});
 const g={id,date,home,away,phase:'regular-season',source:url,sourceHash:hash,teams:{[home]:{players:players(home,away)},[away]:{players:players(away,home)}}};
 g.roleEvidence=[home,away].flatMap(team=>roles.map((position,i)=>({gameId:id,playerId:team+i,team,position,effectiveGameDate:date,gamebookSourceHash:hash,source:'https://stats.nba.com/js/data/leaders/00_daily_lineups_'+date.replaceAll('-','')+'.json',sourceHash:hash})));
 const firstScores=Object.fromEntries([home,away].map(team=>{const defender=team===home?away:home,position=day-1<teams.indexOf(defender)%21?0:4;return [team,{id:team+position,team,points:day%2?1:2,period:1,page:4,sequence:5+position}];}));
 g.firstScores=structuredClone(firstScores);g.openingEvidence={source:url,sourceHash:hash,firstScores};return g;
}
const games=[];let rotation=[...teams];for(let round=0;round<20;round++){for(let i=0;i<15;i++)games.push(fixture(rotation[i],rotation[29-i],round+1,'g'+round+'-'+i));rotation=[rotation[0],rotation.at(-1),...rotation.slice(1,-1)];}
const archive={meta:{season:'2025-26',evidenceContentHash:hash},games};
function supplement(a){return {meta:{parentEvidenceContentHash:hash},datedRoleEvidence:a.games.flatMap(g=>g.roleEvidence),openingEvidence:{meta:{parentEvidenceContentHash:hash},games:Object.fromEntries(a.games.map(g=>[g.id,g.openingEvidence]))}};}
const next={id:'next',date:'2026-10-22',home:'BOS',away:'NYK',season:'2026-27'},row={quote:{team:'NYK',playerId:'NYK0',market:'points'},features:{role:'G'}};
const index=(a=archive,current)=>C.create({archive:a,supplement:supplement(a),current,trusted:true});
const view=position=>({record:{position},label:'Projected starter · unconfirmed',teamStatus:'projected'});
let passed=0;function test(name,fn){fn();passed++;console.log('PASS '+name);}
test('all 30 teams, five positions and four metrics rank by exact numerator/exposure with ties',()=>{
 const x=index();for(const t of teams)for(const position of roles)for(const market of C.MARKETS){const away=t==='NYK'?'BOS':'NYK',c=x.describe({...row,quote:{...row.quote,team:away,market}}, {...next,home:t,away},view(position)),r=c.profile.ranking;
  assert.equal(r.status,'ranked');assert.equal(r.eligibleTeams,30);assert.equal(r.mostRank,market==='threes'?1+teams.filter(v=>Math.floor(teams.indexOf(v)/3)>Math.floor(teams.indexOf(t)/3)).length:30-teams.indexOf(t));assert.equal(r.fewestRank,market==='threes'?1+teams.filter(v=>Math.floor(teams.indexOf(v)/3)<Math.floor(teams.indexOf(t)/3)).length:teams.indexOf(t)+1);
  assert.equal(r.tiedTeams,market==='threes'?3:1);
 }
});
test('one-game current evidence stays unranked beside independently ranked prior-season research',()=>{
 const current={meta:{season:'2026-27',evidenceContentHash:'b'.repeat(64)},games:[fixture('BOS','NYK',1,'new')]};current.games[0].date='2026-10-21';for(const r of current.games[0].roleEvidence){r.effectiveGameDate='2026-10-21';r.source='https://stats.nba.com/js/data/leaders/00_daily_lineups_20261021.json';}
 const c=index(archive,current).describe(row,next,view('PG'));assert.equal(c.dataset.season,'2026-27');assert.equal(c.profile.ranking.status,'unavailable');assert.equal(c.profile.opposing.games,1);assert.equal(c.priorSeason.season,'2025-26');assert.equal(c.priorSeason.profile.ranking.status,'ranked');assert.equal(c.priorSeason.profile.opposing.games,20);
});
test('missing paired rows reduce coverage and never receive an invented league rank',()=>{
 const a=structuredClone(archive);for(let i=0;i<3;i++){const g=fixture('BOS','NYK',21+i,'bad'+i);delete g.teams.NYK.players[0].points;a.games.push(g);}
 const c=index(a).describe(row,next,view('PG'));assert.equal(c.profile.opposing.games,20);assert.equal(c.profile.opposing.expectedGames,23);assert.equal(c.profile.ranking.status,'unavailable');assert.equal(c.profile.ranking.mostRank,null);assert.match(c.profile.ranking.reason,/coverage/);
});
test('a sparse league cannot be labeled a rank among thirty teams',()=>{
 const a=structuredClone(archive);a.games=a.games.filter(g=>g.home!=='WAS'&&g.away!=='WAS');const c=index(a).describe(row,next,view('PG'));assert.equal(c.profile.ranking.status,'unavailable');assert(c.profile.ranking.eligibleTeams<20);assert.equal(c.profile.ranking.mostRank,null);
});
test('selected day, later outcomes and playoffs cannot affect ranks or player averages',()=>{
 const a=structuredClone(archive),base=index().describe(row,next,view('PG'));
 for(const [id,date,phase] of [['same',next.date,'regular-season'],['later','2026-10-23','regular-season'],['playoff','2026-04-01','playoffs']]){const g=fixture('BOS','NYK',1,id);g.date=date;g.phase=phase;a.games.push(g);}
 assert.deepEqual(index(a).describe(row,next,view('PG')),base);
});
test('opening ranks use verified first-team scoring events including free throws, with all categories summing to one',()=>{
 const x=index();for(const team of teams){const o=x.opening({...next,home:team,away:team==='NYK'?'BOS':'NYK'},team),p=o.profile;assert.equal(p.games,20);assert.equal(p.positions.reduce((s,r)=>s+r.count,0)+p.other,20);assert.equal(p.positions[0].count,teams.indexOf(team)%21);assert.equal(p.positions[0].ranking.status,'ranked');assert(!('probabilities' in o));}
});
test('an unresolved opening identity removes only its event coverage while preserving official boxes and independently verified opposite opening path',()=>{
 const a=structuredClone(archive),g=a.games.find(g=>g.home==='BOS'||g.away==='BOS'),offensive=g.home==='BOS'?g.away:g.home;g.openingEvidence.firstScores[offensive].id='unresolved';
 const x=index(a),c=x.describe(row,next,view('PG')),o=x.opening(next,'BOS');assert.equal(c.profile.opposing.games,20);assert.equal(o.profile.games,19);assert.equal(o.profile.expectedGames,20);const opposite=x.opening({home:offensive,away:'BOS',date:next.date},offensive);assert.equal(opposite.profile.games,20);
});
test('roster sheet covers four stats even without supported odds, preserving excluded/unconfirmed players',()=>{
 const x=index(),p={id:'NYK0',name:'Roster PG',team:'NYK'},sheet=P.build({context:x,fixtures:[next],rosters:{NYK:[p]},viewPlayer:()=>view('PG'),eligibility:{NYK0:{excluded:true,reason:'Out'}}});const player=sheet[0].teams[0].players[0];assert(player.excluded);assert.equal(player.cells.length,4);assert(player.cells.every(c=>!c.offer&&c.reason==='Out'));assert.equal(player.cells[0].context.playerSample.n,20);assert.equal(player.cells[0].context.playerSample.minutes,30);assert(!('probabilities' in player.cells[0].context));
});
test('worksheet uses only evaluated supported offers and does not mutate their probabilities, prices or EV',()=>{
 const q={fixtureId:'next',team:'NYK',playerId:'NYK0',market:'points'},r={quote:{...q,side:'under',line:20.5,american:-110,capturedAt:'2026-10-22T01:00Z'},features:{role:'G'},ev:.1,probabilities:{win:.55,push:0,loss:.45}},before=JSON.stringify(r);
 const sheet=P.build({context:index(),fixtures:[next],rosters:{NYK:[{id:'NYK0',name:'Roster PG',team:'NYK'}]},viewPlayer:()=>view('PG'),rows:[r]});assert.equal(sheet[0].teams[0].players[0].cells[0].offer.quote.side,'under');assert.equal(JSON.stringify(r),before);assert.equal(P.build({context:index(),fixtures:[next],rosters:{NYK:[{id:'NYK0',name:'Roster PG'}]},viewPlayer:()=>view('PG'),rows:[]})[0].teams[0].players[0].cells[0].offer,null);
});
test('rank wording discloses ties and eligible denominator instead of assuming 30 qualified teams',()=>{
 assert.equal(P.rankText({status:'ranked',mostRank:2,eligibleTeams:27,tiedTeams:3}),'Tied 2nd-most allowed of 27');assert.equal(P.rankText({status:'unavailable'}),'Rank unavailable');
});
console.log(JSON.stringify({passed}));
