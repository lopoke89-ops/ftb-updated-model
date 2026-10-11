const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../analyst.js'),H=require('../scouting_history.js'),base=path.join(__dirname,'..');
const archive=JSON.parse(fs.readFileSync(path.join(base,'analyst_data.json')));
const canonical=JSON.parse(fs.readFileSync(path.join(base,'merged_dataset.json')));
const report=JSON.parse(fs.readFileSync(path.join(base,'analyst_evaluation.json')));
const empty={meta:{season:'2026-27',parentDatasetId:'nba-2026-27-canonical',asOfDate:null},games:[]};
const current=A.snapshot(empty,{mode:'pregame',date:'2026-10-20'});
const refs=Object.fromEntries(Object.values(canonical.players).filter(p=>p.sourcePlayerId).map(p=>[p.sourcePlayerId,{position:p.position,source:'canonical season role reference'}]));
const options={season:'2026-27',mode:'upcoming',date:'2026-10-20',archiveTrusted:true,positionReferences:refs};
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
test('opening night automatically exposes verified prior history without changing current season',()=>{
  const before=JSON.stringify(empty),s=H.selectEvidence(A,current,archive,options);
  assert.equal(s.season,'2025-26');assert(s.isArchive);assert.equal(s.snapshot.games.length,1322);
  assert.equal(JSON.stringify(empty),before);assert.equal(current.games.length,0);
});
test('one unrelated new-season game cannot erase prior-season evidence',()=>{
  const one={...current,games:[{id:'new'}]},s=H.selectEvidence(A,one,archive,options);
  assert(s.isArchive);assert.equal(s.season,'2025-26');assert.equal(s.snapshot.games.length,1322);
  const forced=H.selectEvidence(A,one,archive,{...options,basis:'archive'});
  assert(forced.isArchive);assert.equal(forced.snapshot.games.length,1322);
});
test('current-only selection displays no record instead of fake zero first scores',()=>{
  const s=H.selectEvidence(A,current,archive,{...options,basis:'current'}),p=H.playerEvidence(s.snapshot,'5104157','SAS');
  assert.equal(s.snapshot,current);assert(!p.hasHistory);assert.equal(p.teamFtbMade,null);assert.equal(p.firstBasketRate,null);assert.equal(p.ppg,null);
});
test('unverified archive is not exposed by automatic or explicit selection',()=>{
  for(const basis of ['auto','archive']){const s=H.selectEvidence(A,current,archive,{...options,basis,archiveTrusted:false});assert.equal(s.snapshot,current);assert.equal(s.blocked,basis==='archive');}
});
test('historical views keep their own dated evidence even with a saved archive choice',()=>{
  const s=H.selectEvidence(A,current,archive,{...options,mode:'pregame',basis:'archive'});assert.equal(s.snapshot,current);assert(!s.isArchive);
});
test('prior history excludes selected-day and future results for dates before archive end',()=>{
  const s=H.selectEvidence(A,current,archive,{...options,date:'2025-10-22'});
  assert.equal(s.snapshot.games.length,2);assert(s.snapshot.games.every(g=>g.date<'2025-10-22'));
  const changed={...archive,games:archive.games.map(g=>g.date>='2025-10-22'?{...g,teams:{},firstScores:{},home:'FAKE'}:g)};
  assert.deepEqual(H.selectEvidence(A,current,changed,{...options,date:'2025-10-22'}).snapshot.players,s.snapshot.players);
});
test('prior phase and rolling filters are applied to the prior season',()=>{
  const s=H.selectEvidence(A,current,archive,{...options,phase:'playoffs',window:5});
  assert(s.snapshot.games.every(g=>g.phase==='playoffs'));assert(Object.values(s.snapshot.teamStats).every(t=>t.games<=5));
});
test('all prior inclusive scores and made free throws reconcile',()=>{
  const s=H.selectEvidence(A,current,archive,options).snapshot;
  const rows=Object.keys(s.players).map(id=>H.playerEvidence(s,id,'NEW',true));
  assert.equal(rows.reduce((n,p)=>n+(p.teamFtbMade||0),0),2644);
  assert.equal(rows.reduce((n,p)=>n+(p.scoutingDetail.shots.ft||0),0),249);
});
test('traded players retain exact cross-stint numerators and appearance denominators',()=>{
  const snap={players:{'1':{id:'1',gp:10,ppg:20,ftbByTeam:{OLD:{gp:8,starts:6,starterWins:2,ftbMade:2,teamGames:82,shots:{ft:1,layup:1}},OTHER:{gp:2,starts:2,starterWins:1,ftbMade:1,teamGames:82,shots:{dunk:1}}}}},teamStats:{NEW:{games:0}}};
  const before=JSON.stringify(snap),p=H.playerEvidence(snap,'1','NEW',true);
  assert.equal(p.teamFtbMade,3);assert.equal(p.firstBasketRate,.3);assert.equal(p.startRate,3/8);assert.equal(p.teamGames,null);
  assert.deepEqual(p.historyTeams,['OLD','OTHER']);assert.equal(p.scoutingDetail.shots.ft,1);assert.equal(JSON.stringify(snap),before);
});
test('real opening-night player counts match the corrected prior history',()=>{
  const s=H.selectEvidence(A,current,archive,options).snapshot;
  for(const [name,wins,starts] of [['Neemias Queta',25,81],['Jalen Duren',28,84],['Joel Embiid',18,45],['Jalen Brunson',28,94],['Cason Wallace',14,60],['Victor Wembanyama',32,77]]){
    const found=Object.values(s.players).find(p=>p.name===name);assert(found,name);
    const p=H.playerEvidence(s,found.id,'NEW',true);assert.equal(p.scoutingDetail.starterWins,wins,name);assert.equal(p.scoutingDetail.starts,starts,name);
  }
});
test('unknown players cannot inherit a similarly named player record',()=>{
  const p=H.playerEvidence(H.selectEvidence(A,current,archive,options).snapshot,'not-in-ledger','BOS',true);
  assert(!p.hasHistory);assert.equal(p.teamFtbMade,null);assert.deepEqual(p.historyTeams,[]);
});
test('withheld forecasts sort by observed counts with unknown records last',()=>{
  const list=[{name:'No history',teamFtbMade:null,forecastWithheld:true},{name:'Observed zero',teamFtbMade:0,forecastWithheld:true},{name:'Leader',teamFtbMade:10,forecastWithheld:true}];
  assert.deepEqual(H.sortPlayers(list,'probability').map(p=>p.name),['Leader','Observed zero','No history']);assert.equal(list[0].name,'No history');
});
test('injury identity supports profile links and rejects ambiguous links',()=>{
  assert.equal(H.injuryPlayerId({id:'42'}),'42');assert.equal(H.injuryPlayerId({links:[{href:'https://www.espn.com/nba/player/_/id/42/name'}]}),'42');
  assert.equal(H.injuryPlayerId({links:[{href:'/id/42/name'},{href:'/id/43/name'}]}),null);
  const p=H.parseInjuries({injuries:[{injuries:[{athlete:{links:[{href:'/id/42/name'}]},status:'Out'},{athlete:{displayName:'Unresolved'},status:'Out'}]}]},'capture');
  assert.equal(p.entries['42'].status,'OUT');assert.equal(p.unresolved,1);assert.equal(p.total,2);assert.throws(()=>H.parseInjuries({}));
});
test('UI shows prior history while the forecast receives only the empty new season',()=>{
  const rows=[{id:'5104157',name:'Victor Wembanyama',team:'SAS',rawPosition:'C'},{id:'rookie',name:'New Rookie',team:'SAS',rawPosition:'G'}];
  const fixture={id:'future',date:'2026-10-20',home:'SAS',away:'OKC',season:'2026-27',phase:'regular-season',status:'pre'};
  const states=[empty,archive,'auto',canonical,report,'picks','upcoming','2026-10-20','all','0',A.DEFAULT_TARGET,'2026-27',[fixture],'all',{SAS:rows,OKC:[]},{},null,{},null,false,null,'probability',40,{},false,'',Date.now(),'history',null,null,'all-opponents'];
  let index=0;const calls=[];
  const context=vm.createContext({window:{__FTB_ANALYST_DATA__:archive,__FTB_MERGED__:canonical,__FTB_ANALYST_EVALUATION__:report,FTBScoutingHistory:H,FTBAnalyst:{...A,distribution:(s,t,o)=>{calls.push(s);return A.distribution(s,t,o);}}},React:{createElement:(type,props,...children)=>({type,props,children}),Fragment:'fragment',useState:initial=>[index<states.length?states[index++]:initial,()=>{}],useEffect:()=>{},useMemo:fn=>fn(),useRef:()=>({current:0})},Date,Intl,Number,String,Set,Object,JSON});
  vm.runInContext(fs.readFileSync(path.join(base,'analyst_ui.js'),'utf8'),context);
  const tree=context.window.FTBAnalystApp(),cards=[];function walk(n){if(!n||typeof n!=='object')return;if(n.type?.name==='PlayerCard')cards.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(tree);
  assert.equal(cards.length,2);const p=cards.find(n=>n.props.p.id==='5104157').props.p;
  assert.equal(p.teamFtbMade,32);assert.equal(p.statsSeason,'2025-26');assert(p.forecastWithheld);assert.equal(p.probability,undefined);
  assert.equal(p.gradeBasis,'history');assert(p.historicalGrade.rated);assert.equal(p.historicalGrade.letter,'S');assert.equal(index,states.length);
  assert(calls.length);assert(calls.every(s=>s.games.length===0));assert(cards.find(n=>n.props.p.id==='rookie').props.p.teamFtbMade===null);
});
test('combined competition contains exactly regular season and playoffs',()=>{
  const original=JSON.stringify(archive),s=H.snapshotForScope(A,archive,{mode:'review',phase:'regular-and-playoffs'});
  assert.equal(s.games.length,1315);assert.equal(s.meta.phase,'regular-and-playoffs');
  assert.equal(s.games.filter(g=>g.phase==='regular-season').length,1230);assert.equal(s.games.filter(g=>g.phase==='playoffs').length,85);
  assert(s.games.every(g=>['regular-season','playoffs'].includes(g.phase)));assert.equal(JSON.stringify(archive),original);
  assert.equal(Object.values(s.players).reduce((n,p)=>n+p.ftbMade,0),2630);
});
test('combined counts equal the two separate samples, including free throws',()=>{
  const snap=phase=>H.snapshotForScope(A,archive,{mode:'review',phase}),combined=snap('regular-and-playoffs'),regular=snap('regular-season'),playoffs=snap('playoffs');
  for(const p of Object.values(combined.players))for(const key of ['gp','starts','ftbMade','starterWins','points'])assert.equal(p[key],(regular.players[p.id]?.[key]||0)+(playoffs.players[p.id]?.[key]||0),p.name+' '+key);
  assert.equal(Object.values(combined.players).reduce((n,p)=>n+p.shots.ft,0),Object.values(regular.players).reduce((n,p)=>n+p.shots.ft,0)+Object.values(playoffs.players).reduce((n,p)=>n+p.shots.ft,0));
});
test('combined scope preserves membership and lineup chronology in other phases',()=>{
  const dates=archive.games.filter(g=>g.phase==='play-in'||g.phase==='nba-cup-final').map(g=>g.date);
  for(const date of dates){const all=A.snapshot(archive,{mode:'pregame',date}),s=H.snapshotForScope(A,archive,{mode:'pregame',date,phase:'regular-and-playoffs'});assert.deepEqual(s.rosters,all.rosters);assert.deepEqual(s.lastLineups,all.lastLineups);assert(s.games.every(g=>g.date<date));}
});
test('combined rolling scope contains only the last eligible games per team',()=>{
  const s=H.snapshotForScope(A,archive,{mode:'review',phase:'regular-and-playoffs',window:5});
  assert(Object.values(s.teamStats).every(t=>t.games===5));assert(s.games.every(g=>['regular-season','playoffs'].includes(g.phase)));
});
const gradedSnap=H.snapshotForScope(A,archive,{mode:'review',phase:'regular-and-playoffs'}),gradeContext=H.gradeContext(gradedSnap);
const gradeSample=(starts,wins,{gp=starts,ftbMade=wins,teamGames=gp}={})=>({teamGames,scoutingDetail:{starts,starterWins:wins,gp,ftbMade}});
test('grade baseline uses starters in the selected historical sample',()=>{
  assert.equal(gradeContext.starts,13150);assert.equal(gradeContext.wins,2626);assert.equal(gradeContext.baseline,2626/13150);
});
test('historical grade blends starter results and uses exact samples',()=>{
  const p=H.playerEvidence(gradedSnap,'5104157','SAS',true),g=H.historicalGrade(p,gradeContext);
  assert(g.rated);assert.equal(g.letter,'S');assert.equal(g.starts,77);assert.equal(g.wins,32);
  assert.equal(g.adjustedStartRate,(32+20*gradeContext.baseline)/97);assert.equal(g.score,Math.min(g.adjustedStartRate,32/p.scoutingDetail.gp));assert.equal(g.rawRate,32/77);
});
test('small positive and zero starter samples cannot receive fabricated grades',()=>{
  for(const starts of [0,1,4]){const g=H.historicalGrade({scoutingDetail:{starts,starterWins:starts}},gradeContext);assert.equal(g.letter,'NR');assert.equal(g.score,null);assert(!g.rated);}
  const g=H.historicalGrade(gradeSample(5,0),gradeContext);assert(g.rated);assert(g.smallSample);assert.equal(g.score,0);assert.equal(g.letter,'D');
});
test('grades mark small samples and reject inconsistent or unsupported inputs',()=>{
  assert(H.historicalGrade(gradeSample(19,4),gradeContext).smallSample);
  assert(!H.historicalGrade(gradeSample(20,4),gradeContext).smallSample);
  assert(!H.historicalGrade({scoutingDetail:{starts:5,starterWins:6}},gradeContext).rated);
  assert(!H.historicalGrade({scoutingDetail:{starts:20,starterWins:5}},{...gradeContext,trusted:false}).rated);
  assert(!H.historicalGrade({scoutingDetail:{starts:20,starterWins:5}},{...gradeContext,target:'first-game-score-including-free-throws'}).rated);
});
test('grade boundaries follow the published historical tiers',()=>{
  for(const [score,letter] of [[.25,'S'],[.2499,'A'],[.18,'A'],[.1799,'B'],[.12,'B'],[.1199,'C'],[.06,'C'],[.0599,'D']]){
    const starts=10000,wins=Math.round(starts*score),g=H.historicalGrade(gradeSample(starts,wins),{...gradeContext,baseline:score});assert.equal(g.letter,letter);
  }
});
test('competition changes recompute the grade and its starter sample',()=>{
  const id=Object.values(gradedSnap.players).find(p=>p.name==='Jalen Brunson').id;
  const regular=H.snapshotForScope(A,archive,{mode:'review',phase:'regular-season'}),playoffs=H.snapshotForScope(A,archive,{mode:'review',phase:'playoffs'});
  const r=H.historicalGrade(H.playerEvidence(regular,id,'NYK',true),H.gradeContext(regular)),p=H.historicalGrade(H.playerEvidence(playoffs,id,'NYK',true),H.gradeContext(playoffs));
  assert(r.rated&&p.rated);assert.notEqual(r.starts,p.starts);assert.notEqual(r.score,p.score);
});
test('traded-player grade uses prior starter history instead of a new-team zero',()=>{
  const p=Object.values(gradedSnap.players).find(p=>p.name==='Paul George');
  const old=H.historicalGrade(H.playerEvidence(gradedSnap,p.id,'PHI',true),gradeContext),current=H.historicalGrade(H.playerEvidence(gradedSnap,p.id,'BOS',true),gradeContext);assert.deepEqual(current,old);assert(current.rated);
});
test('historical grade sorting keeps ungraded players last without changing forecast probabilities',()=>{
  const list=[{name:'NR',historicalGrade:{score:null},probability:.9},{name:'B',historicalGrade:{score:.14},probability:.5},{name:'S',historicalGrade:{score:.3},probability:.1}];
  const copy=JSON.stringify(list);assert.deepEqual(H.sortPlayers(list,'grade').map(p=>p.name),['S','B','NR']);assert.equal(JSON.stringify(list),copy);
});
test('Diawara cannot receive an elite grade from four first scores in seven starts',()=>{
  const s=H.snapshotForScope(A,archive,{mode:'review'}),p=H.playerEvidence(s,'5289900','NYK'),g=H.historicalGrade(p,H.gradeContext(s));
  assert.equal(p.teamFtbMade,4);assert.equal(p.teamGames,102);assert.equal(g.rawRate,4/7);assert(g.adjustedStartRate>.25);
  assert.equal(g.score,4/102);assert.equal(g.letter,'D');assert(g.shareLimited&&g.smallSample);
  const rows=['NYK','PHI'].flatMap(team=>(s.rosters[team]||[]).map(r=>{const p=H.playerEvidence(s,r.id,team);return {...p,name:r.name,historicalGrade:H.historicalGrade(p,H.gradeContext(s))};}));
  const sorted=H.sortPlayers(rows,'grade'),index=sorted.findIndex(p=>p.id==='5289900');assert(index>5);
  for(const p of sorted.slice(0,index).filter(p=>p.historicalGrade.rated))assert(p.historicalGrade.score>=g.score);
});
test('all graded players respect observed scoring share across competition and rolling scopes',()=>{
  for(const phase of Object.keys(H.PHASES))for(const window of [0,5,20]){
    const s=H.snapshotForScope(A,archive,{mode:'review',phase,window}),context=H.gradeContext(s);
    for(const row of Object.values(s.players))for(const team of Object.keys(row.ftbByTeam))for(const acrossStints of [false,true]){
      const p=H.playerEvidence(s,row.id,team,acrossStints),g=H.historicalGrade(p,context);if(!g.rated)continue;
      assert(g.score<=p.firstBasketRate+1e-12,row.name+' '+phase+' '+window);assert(g.score<=g.adjustedStartRate);
      if(g.letter==='S')assert(p.firstBasketRate>=.25);if(g.letter==='A')assert(p.firstBasketRate>=.18);
    }
  }
});
test('incomplete and contradictory scoring-share counts cannot bypass the grade cap',()=>{
  for(const p of [{scoutingDetail:{starts:7,starterWins:4}},gradeSample(7,4,{gp:6,teamGames:102}),gradeSample(7,4,{gp:75,ftbMade:3,teamGames:102}),gradeSample(7,4,{gp:75,teamGames:74})])assert(!H.historicalGrade(p,gradeContext).rated);
  const p=gradeSample(7,4,{gp:75,teamGames:null}),g=H.historicalGrade(p,gradeContext);assert.equal(g.shareBasis,'appearance');assert.equal(g.shareDenominator,75);assert.equal(g.score,4/75);assert.equal(g.letter,'D');
});
const pair={home:'OKC',away:'SAS'},pairKey=g=>[g.home,g.away].sort().join('|');
const scoped=(phase='all',extra={})=>H.snapshotForScope(A,archive,{mode:'review',phase,positionReferences:refs,historyMatchups:[pair],...extra});
test('head-to-head matches both venues by exact team identity without mutating evidence',()=>{
  const before=JSON.stringify(archive),s=scoped();assert.equal(s.games.length,12);
  assert(s.games.some(g=>g.home==='OKC')&&s.games.some(g=>g.home==='SAS'));
  assert(s.games.every(g=>pairKey(g)===pairKey(pair)));assert.deepEqual(scoped('all',{historyMatchups:[{home:'SAS',away:'OKC'}]}),s);
  assert.equal(JSON.stringify(archive),before);assert.equal(s.meta.phase,'all');
});
test('head-to-head intersects every competition instead of broadening empty scopes',()=>{
  for(const phase of Object.keys(H.PHASES)){
    const s=scoped(phase),expected=archive.games.filter(g=>pairKey(g)===pairKey(pair)&&(phase==='all'||(phase==='regular-and-playoffs'?['regular-season','playoffs'].includes(g.phase):g.phase===phase)));
    assert.deepEqual(s.games.map(g=>g.id).sort(),expected.map(g=>g.id).sort(),phase);
    assert.equal(s.meta.statsThrough,expected.at(-1)?.date||null);
  }
  assert.equal(scoped('regular-season').games.length,5);assert.equal(scoped('playoffs').games.length,7);assert.equal(scoped('regular-and-playoffs').games.length,12);
});
test('all selected matchups use a deduplicated union of exact pairs',()=>{
  const pairs=[pair,{home:'PHI',away:'NYK'},{home:'DET',away:'BOS'},pair];
  const s=scoped('regular-and-playoffs',{historyMatchups:pairs});assert.equal(s.games.length,24);assert.equal(s.meta.historyMatchups.length,3);
  assert.equal(s.teamStats.SAS.games,12);assert.equal(s.teamStats.PHI.games,8);assert.equal(s.teamStats.DET.games,4);
  assert(s.games.every(g=>pairs.some(p=>pairKey(p)===pairKey(g))));
});
test('head-to-head scoring events retain made free throws and exact starter totals',()=>{
  const s=scoped('regular-and-playoffs'),scores=s.games.flatMap(g=>Object.values(g.firstScores));
  assert.equal(scores.length,24);assert.equal(scores.filter(p=>p.shot==='ft').length,3);
  assert.equal(Object.values(s.teamStats).reduce((n,t)=>n+t.firstScoreCount,0),24);
  assert.equal(Object.values(s.players).reduce((n,p)=>n+p.ftbMade,0),24);
  for(const team of ['SAS','OKC'])assert.equal(A.positionCharts(s).scoring[team].totalGames,12);
});
test('head-to-head pregame excludes selected-day and later meetings and later mutations',()=>{
  const date='2026-05-28',s=scoped('all',{mode:'pregame',date});assert(s.games.every(g=>g.date<date));
  const changed={...archive,games:archive.games.map(g=>g.date>=date?{...g,home:'FAKE',teams:{},firstScores:{}}:g)};
  assert.deepEqual(H.snapshotForScope(A,changed,{mode:'pregame',date,historyMatchups:[pair]}),H.snapshotForScope(A,archive,{mode:'pregame',date,historyMatchups:[pair]}));
});
test('head-to-head keeps previous rosters and lineups from the full dated chronology',()=>{
  for(const mode of ['review','pregame']){const options={mode,date:'2026-05-28'},all=A.snapshot(archive,options),s=scoped('playoffs',options);
    assert.deepEqual(s.rosters,all.rosters);assert.deepEqual(s.lastLineups,all.lastLineups);
  }
});
test('last five head-to-head meetings are the last five eligible meetings per team',()=>{
  for(const phase of ['all','regular-season','playoffs','regular-and-playoffs']){const full=scoped(phase),s=scoped(phase,{window:5});
    assert.deepEqual(s.games.map(g=>g.id),full.games.slice(-5).map(g=>g.id));
    assert.equal(s.meta.totalGames,s.games.length);assert.equal(s.teamStats.SAS.games,Math.min(5,full.games.length));
    const p=H.playerEvidence(s,'5104157','SAS',true),boxes=s.games.flatMap(g=>g.teams.SAS.players.filter(p=>p.id==='5104157'&&p.played));
    assert.equal(p.scoutingDetail.gp,boxes.length);assert.equal(p.ppg,boxes.length?boxes.reduce((n,p)=>n+p.points,0)/boxes.length:null);
  }
});
test('rolling fixture provenance contains only games contributing at least one team sample',()=>{
  const s=H.snapshotForScope(A,archive,{mode:'review',phase:'regular-and-playoffs',window:5});
  assert(s.games.length<1315);assert(s.games.every(g=>s.gameTeams[g.id].length));assert.equal(s.meta.totalGames,s.games.length);
  for(const team of Object.keys(s.teamStats))assert.equal(s.games.filter(g=>s.gameTeams[g.id].includes(team)).length,s.teamStats[team].games);
});
test('empty, invalid and missing pair samples cannot inherit broader history',()=>{
  for(const historyMatchups of [[],[{home:'SAS',away:'SAS'}],[{home:'SAS'}],[{home:'SAS',away:'NONEXISTENT'}]]){
    const s=scoped('all',{historyMatchups});assert.equal(s.games.length,0);assert.deepEqual(s.teamStats,{});assert.equal(s.meta.statsThrough,null);
    const p=H.playerEvidence(s,'5104157','SAS',true);assert.equal(p.teamFtbMade,null);assert.equal(p.ppg,null);assert(!p.hasHistory);
  }
});
test('no playoff meetings remain empty while the regular-season sample still exists',()=>{
  const pairs=[{home:'BOS',away:'DET'}],s=scoped('playoffs',{historyMatchups:pairs}),p=H.playerEvidence(s,'3064560','BOS',true);
  assert.equal(s.games.length,0);assert(!p.hasHistory);assert(!H.historicalGrade(p,gradeContext).rated);
  assert.equal(scoped('regular-season',{historyMatchups:pairs}).games.length,4);
});
test('head-to-head grades use exact team-side starts and the same broader league baseline',()=>{
  const s=scoped('regular-and-playoffs'),p=H.playerEvidence(s,'5104157','SAS',true),g=H.historicalGrade(p,gradeContext);
  assert.equal(p.scoutingDetail.starts,9);assert.equal(p.teamFtbMade,2);assert.equal(p.teamGames,12);assert.equal(p.firstBasketRate,2/12);
  assert.equal(g.adjustedStartRate,(2+20*gradeContext.baseline)/29);assert.equal(g.score,2/12);assert.equal(g.baseline,gradeContext.baseline);assert(g.smallSample);assert.equal(g.letter,'B');
});
function sideGame(id,date,home,away,actorTeam,points){
  const row=team=>({id:team===actorTeam?'1':'2',name:team===actorTeam?'Traded Player':'Other Player',rawPosition:'C',starter:true,played:true,points,threeMade:1,threeAttempted:2});
  const teams=Object.fromEntries([home,away].map(t=>[t,{players:[row(t)],starters:[row(t).id]}]));
  return {id,date,home,away,phase:'regular-season',teams,firstScores:Object.fromEntries([home,away].map(t=>[t,{id:row(t).id,points:2,shot:'dunk',period:1,clock:t===home?'11:50':'11:40',position:'C'}]))};
}
test('a player who changed sides cannot inherit opponent-side counts, averages or starts',()=>{
  const data={meta:{season:'2025-26',asOfDate:'2026-03-03'},games:[sideGame('1','2026-03-01','AAA','BBB','BBB',10),sideGame('2','2026-03-02','BBB','AAA','AAA',20),sideGame('3','2026-03-03','AAA','CCC','AAA',99)]};
  const s=H.snapshotForScope(A,data,{mode:'review',historyMatchups:[{home:'AAA',away:'BBB'}]});
  const p=H.playerEvidence(s,'1','AAA',true);assert.equal(p.scoutingDetail.starts,1);assert.equal(p.teamFtbMade,1);assert.equal(p.gp,1);assert.equal(p.ppg,20);assert.equal(p.threePm,1);assert.deepEqual(p.historyTeams,['AAA']);
  const q=H.playerEvidence(s,'1','BBB',true);assert.equal(q.scoutingDetail.starts,1);assert.equal(q.ppg,10);assert.deepEqual(q.historyTeams,['BBB']);
  assert.equal(s.lastLineups.AAA.date,'2026-03-03');assert.equal(s.meta.statsThrough,'2026-03-02');assert.equal(s.meta.lineupsThrough,'2026-03-03');
});
test('new-team head-to-head is no record rather than the player previous-team season totals',()=>{
  const s=scoped('all',{historyMatchups:[{home:'BOS',away:'DET'}]}),pg=Object.values(archive.games.flatMap(g=>g.teams.PHI?.players||[])).find(p=>p.name==='Paul George');
  assert(pg);const p=H.playerEvidence(s,pg.id,'BOS',true);assert(!p.hasHistory);assert.equal(p.teamFtbMade,null);assert.equal(p.ppg,null);assert.equal(p.scoutingDetail.starts||0,0);
});
function renderUI(overrides={}){
  const fixture={id:'future',date:'2026-10-20',home:'SAS',away:'OKC',season:'2026-27',phase:'regular-season',status:'pre'};
  const rows=[{id:'5104157',name:'Victor Wembanyama',team:'SAS',rawPosition:'C'}];
  const names=['data','archive','basis','canonical','report','tab','mode','date','phase','period','target','season','schedule','gameId','rosters','injuries','pbp','sources','error','busy','expanded','sort','limit','scenario','showOut','journalMessage','now','gradeBasis','health','journal','historyScope'];
  const initial=[empty,archive,'auto',canonical,report,'picks','upcoming','2026-10-20','regular-and-playoffs','0',A.DEFAULT_TARGET,'2026-27',[fixture],'all',{SAS:rows,OKC:[]},{},null,{},null,false,null,'grade',40,{},false,'',Date.now(),'history',null,null,'head-to-head'];
  const states=initial.map((v,i)=>names[i] in overrides?overrides[names[i]]:v),calls=[];let index=0;
  const context=vm.createContext({window:{__FTB_ANALYST_DATA__:archive,__FTB_MERGED__:canonical,__FTB_ANALYST_EVALUATION__:report,FTBScoutingHistory:H,FTBAnalyst:{...A,distribution:(s,t,o)=>{calls.push(s);return A.distribution(s,t,o);}}},React:{createElement:(type,props,...children)=>({type,props,children}),Fragment:'fragment',useState:initial=>[index<states.length?states[index++]:initial,()=>{}],useEffect:()=>{},useMemo:fn=>fn(),useRef:()=>({current:0})},Date,Intl,Number,String,Set,Object,JSON});
  vm.runInContext(fs.readFileSync(path.join(base,'analyst_ui.js'),'utf8'),context);
  const tree=context.window.FTBAnalystApp(),cards=[],text=[];function walk(n){if(typeof n==='string'){text.push(n);return;}if(!n||typeof n!=='object')return;if(n.type?.name==='PlayerCard')cards.push(n.props.p);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(tree);
  assert.equal(index,names.length);return {cards,calls,tree,text:text.join(' ')};
}
test('UI head-to-head recomputes grades and keeps the current-season forecast input separate',()=>{
  const r=renderUI(),p=r.cards[0];assert.equal(p.teamFtbMade,2);assert.equal(p.scoutingDetail.starts,9);assert.equal(p.gp,12);assert.equal(p.ppg,283/12);
  assert(p.headToHead);assert.equal(p.opponent,'OKC');assert.equal(p.statsSeason,'2025-26');assert.equal(p.gradeBasis,'history');assert.equal(p.historicalGrade.letter,'B');
  assert(p.forecastWithheld);assert.equal(p.probability,undefined);assert(r.calls.every(s=>s.games.length===0));assert(r.text.includes('12 matching historical fixtures'));
});
test('UI changing competition and period recomputes head-to-head counts and grade eligibility',()=>{
  const regular=renderUI({phase:'regular-season'}).cards[0],playoffs=renderUI({phase:'playoffs'}).cards[0],last5=renderUI({period:'5'}).cards[0];
  assert.equal(regular.gp,5);assert.equal(regular.scoutingDetail.starts,2);assert.equal(regular.historicalGrade.letter,'NR');
  assert.equal(playoffs.gp,7);assert.equal(playoffs.scoutingDetail.starts,7);assert.equal(last5.gp,5);assert.equal(last5.scoutingDetail.starts,5);
});
test('UI current-only history cannot fall back to archive when head-to-head is empty',()=>{
  const r=renderUI({basis:'current'}),p=r.cards[0];assert.equal(p.statsSeason,'2026-27');assert.equal(p.teamFtbMade,null);assert.equal(p.ppg,null);assert.equal(p.historicalGrade.letter,'NR');assert(r.text.includes('No matching meetings in this scope'));
});
test('UI removes old matchup history immediately when date no longer matches schedule',()=>{
  const r=renderUI({date:'2026-10-21'});assert.equal(r.cards.length,0);assert(r.text.includes('needs a scheduled matchup'));
});
test('UI does not expose forecast percentages even in supported season when head-to-head is selected',()=>{
  const fixture={...archive.games.at(-1),season:'2025-26'};
  const r=renderUI({data:archive,mode:'review',season:'2025-26',date:fixture.date,schedule:[fixture],phase:'all',gradeBasis:'forecast'});
  assert(r.cards.length);assert(r.cards.every(p=>p.forecastWithheld&&p.probability===undefined));assert(r.calls.every(s=>s.games.length===1322));
});
test('UI field-goal grades use their own scorer counts and shared scoring-share cap',()=>{
  const r=renderUI({target:'first-team-made-field-goal'});assert(r.cards.some(p=>p.historicalGrade.rated));
  assert(!r.text.includes('Historical grades are unavailable for this scoring target'));
});
test('analysis filters default to a native collapsed panel and retain every control',()=>{
  const r=renderUI(),nodes=[];function walk(n){if(!n||typeof n!=='object')return;nodes.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(walk):walk(c);}walk(r.tree);
  const panel=nodes.find(n=>n.type==='details'&&n.props?.className==='filter-panel');assert(panel);assert(!panel.props.open);
  const children=[];function collect(n){if(!n||typeof n!=='object')return;children.push(n);for(const c of n.children||[])Array.isArray(c)?c.forEach(collect):collect(c);}collect(panel);
  assert(children.some(n=>n.type==='summary'));for(const label of ['Season','Analysis mode','Grading basis','Game date','Competition phase','Opponent history','Statistics period','Scoring target','Matchup'])assert(children.some(n=>n.props?.['aria-label']===label),label);
  assert(children.some(n=>n.props?.['aria-label']==='Selected-date matchups'));assert(r.text.includes('Head-to-head · Full sample'));
});
console.log(JSON.stringify({passed:count}));
