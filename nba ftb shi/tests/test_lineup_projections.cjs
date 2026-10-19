'use strict';
const assert=require('node:assert/strict'),Q=require('../lineup_projections.js'),L=require('../lineups.js');
const now=Date.parse('2026-10-18T20:00Z'),capturedAt=new Date(now).toISOString();
const fixture={id:'game',date:'2026-10-20',season:'2026-27',home:'BOS',away:'DET',status:'pre',scheduledTipoff:'2026-10-20T19:00Z'};
const roster=Array.from({length:10},(_,i)=>({id:String(i+1),nbaId:String(100+i+1),name:'Player '+(i+1),team:'BOS'}));
const chart=()=>({team:{id:'2',abbreviation:'BOS'},season:{year:2027},timestamp:capturedAt,
  depthchart:[{positions:Object.fromEntries(Q.POS.map((p,i)=>[p.toLowerCase(),{athletes:[{id:String(i+1),displayName:roster[i].name,injuries:[]},{id:String(i+6),displayName:roster[i+5].name,injuries:[]}]}]))}]});
const parse=(data=chart(),extra={})=>Q.parseDepth(data,{team:'BOS',fixture,roster,capturedAt,now,...extra});
const response=data=>({ok:true,json:async()=>data});
let passed=0;async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
(async()=>{
  await test('all 30 teams are supported and Sacramento resolves a complete projected five',()=>{
    const teams='ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS'.split(' ');
    assert.deepEqual(Object.keys(Q.TEAM_IDS).sort(),teams.sort());
    assert.equal(new Set(Object.values(Q.TEAM_IDS)).size,30);
    assert.equal(Q.depthUrl('SAC'),'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/23/depthcharts');
    const source=chart();source.team={id:'23',abbreviation:'SAC'};
    const game={...fixture,home:'SAC'};
    const players=Object.values(Q.parseDepth(source,{team:'SAC',fixture:game,roster:roster.map(p=>({...p,team:'SAC'})),capturedAt,now}));
    assert.equal(players.length,5);assert(players.every(p=>p.team==='SAC'&&Q.validProjection(p,game,now)));
  });
  await test('advance projection maps five current-roster IDs to the selected fixture',()=>{
    const players=Object.values(parse());assert.equal(players.length,5);assert(players.every(p=>p.status==='projected'&&p.fixtureId==='game'&&p.date===fixture.date&&p.source===Q.depthUrl('BOS')));
    assert.deepEqual(players.map(p=>p.position),Q.POS);assert(players.every(p=>!L.validConfirmation(p,fixture,now)));
  });
  await test('wrong team, wrong season, old date, and beyond-seven-day fixtures are rejected',()=>{
    const bad=chart();bad.team.id='8';assert.throws(()=>parse(bad),/identity/);
    const stale=chart();stale.season.year=2026;assert.throws(()=>parse(stale),/season/);
    for(const date of ['2026-10-17','2026-10-26'])assert.throws(()=>parse(chart(),{fixture:{...fixture,date}}),/stale/);
  });
  await test('a traded player outside the current roster cannot enter the projected five',()=>{
    const players=parse(chart(),{roster:roster.filter(p=>p.id!=='1')});assert(!players['1']);assert(players['6']);assert.equal(players['6'].depthRank,2);
  });
  await test('Out and Doubtful players are excluded while Questionable stays labeled',()=>{
    const players=parse(chart(),{injuries:{1:{status:'OUT'},2:{status:'DOUBTFUL'},3:{status:'QUESTIONABLE'}}});
    assert(!players['1']&&!players['2']);assert(players['6']&&players['7']);assert.equal(players['3'].availability,'QUESTIONABLE');
    const source=chart();source.depthchart[0].positions.pg.athletes[0].injuries=[{status:'Out'}];assert(!parse(source)['1']);
  });
  await test('duplicate depth-chart leaders resolve to five distinct players',()=>{
    const source=chart();source.depthchart[0].positions.sg.athletes.unshift(source.depthchart[0].positions.pg.athletes[0]);
    const players=Object.values(parse(source));assert.equal(new Set(players.map(p=>p.id)).size,5);assert(players.find(p=>p.position==='SG').id!=='1');
  });
  await test('incomplete or ambiguous charts withhold the team rather than inventing a starter',()=>{
    const source=chart();source.depthchart[0].positions.c.athletes=[];assert.throws(()=>parse(source),/distinct/);
    const ambiguous=chart();ambiguous.depthchart.push(ambiguous.depthchart[0]);assert.throws(()=>parse(ambiguous),/Complete/);
  });
  await test('future captures, stale captures, and impossible source timestamps are rejected',()=>{
    assert.throws(()=>parse(chart(),{capturedAt:new Date(now+1).toISOString()}),/stale/);
    assert.throws(()=>parse(chart(),{capturedAt:new Date(now-Q.MAX_AGE-1).toISOString()}),/stale/);
    const future=chart();future.timestamp=new Date(now+600001).toISOString();assert.throws(()=>parse(future),/source time/);
  });
  await test('projection labels expire at tipoff and cannot match another fixture',()=>{
    const projected=parse(),p=projected['1'];assert(Q.validProjection(p,fixture,now));
    assert(!Q.validProjection(p,{...fixture,id:'other'},now));assert(!Q.validProjection(p,fixture,Date.parse(fixture.scheduledTipoff)));
    assert.equal(Q.playerView('1','BOS',fixture,{projected},now).label,'Depth-chart projected starter · unconfirmed');
    assert.equal(Q.playerView('10','BOS',fixture,{projected},now).label,'Not in current projected five');
  });
  await test('future-date loading uses sourced projections without inventing NBA confirmations',async()=>{
    const calls=[];const result=await Q.load({date:fixture.date,fixtures:[fixture],rosters:{BOS:roster},clock:()=>now,officialParser:L.parse,fetcher:async url=>{calls.push(url);if(url===Q.depthUrl('BOS'))return response(chart());return {ok:false,status:404};}});
    assert.equal(Object.keys(result.confirmed).length,0);assert.equal(Object.keys(result.projected).length,5);assert(!calls.some(u=>u.includes('stats.nba.com')));
  });
  await test('cloud projection fallback preserves actual capture time and rejects stale entries',async()=>{
    const load=age=>Q.load({date:fixture.date,fixtures:[fixture],rosters:{BOS:roster},clock:()=>now,officialParser:L.parse,fetcher:async url=>{
      if(url.includes('projected-lineups.json'))return response({schemaVersion:1,teams:{BOS:{source:Q.depthUrl('BOS'),capturedAt:new Date(now-age).toISOString(),payload:chart()}}});
      return {ok:false,status:503};
    }});
    const good=await load(3600000);assert.equal(good.projected['1'].capturedAt,new Date(now-3600000).toISOString());assert.equal(Object.keys((await load(Q.MAX_AGE+1)).projected).length,0);
  });
  await test('fresh official NBA confirmation supersedes a depth-chart projection',async()=>{
    const todayFixture={...fixture,date:'2026-10-18',scheduledTipoff:'2026-10-18T23:00Z'};
    const nba={games:[{gameId:'nba-game',gameStatus:1,homeTeam:{teamAbbreviation:'BOS',players:roster.slice(0,5).map((p,i)=>({personId:p.nbaId,playerName:p.name,position:Q.POS[i],lineupStatus:'Confirmed',rosterStatus:'Active'}))},awayTeam:{teamAbbreviation:'DET',players:[]}}]};
    const result=await Q.load({date:todayFixture.date,fixtures:[todayFixture],rosters:{BOS:roster},clock:()=>now,officialParser:L.parse,fetcher:async url=>url.includes('stats.nba.com')?response(nba):url===Q.depthUrl('BOS')?response(chart()):{ok:false,status:404}});
    assert.equal(Object.keys(result.confirmed).length,5);assert.equal(Object.keys(result.projected).length,0);
    assert.equal(Q.teamView('BOS',todayFixture,result,now).kind,'confirmed');assert(Object.values(result.confirmed).every(p=>L.validConfirmation(p,todayFixture,now)));
  });
  await test('an old official cloud capture cannot confirm a starter',async()=>{
    const game={...fixture,date:'2026-10-18',scheduledTipoff:'2026-10-18T23:00Z'};
    const result=await Q.load({date:game.date,fixtures:[game],rosters:{BOS:roster},clock:()=>now,officialParser:L.parse,fetcher:async url=>url.includes('live-lineups.json')?response({schemaVersion:1,date:game.date,source:Q.officialUrl(game.date),capturedAt:new Date(now-300001).toISOString(),payload:{games:[]}}):url===Q.depthUrl('BOS')?response(chart()):{ok:false,status:503}});
    assert.equal(Object.keys(result.confirmed).length,0);assert.equal(Object.keys(result.projected).length,5);assert.match(result.officialStatus,/older than five/);
  });
  await test('unavailable NBA expected players do not replace an injury-adjusted depth projection',async()=>{
    const game={...fixture,date:'2026-10-18',scheduledTipoff:'2026-10-18T23:00Z'};
    const nba={games:[{gameId:'nba-game',gameStatus:1,homeTeam:{teamAbbreviation:'BOS',players:roster.slice(0,5).map((p,i)=>({personId:p.nbaId,playerName:p.name,position:Q.POS[i],lineupStatus:'Expected',rosterStatus:'Active'}))},awayTeam:{teamAbbreviation:'DET',players:[]}}]};
    const result=await Q.load({date:game.date,fixtures:[game],rosters:{BOS:roster},injuries:{1:{status:'OUT'}},clock:()=>now,officialParser:L.parse,fetcher:async url=>url.includes('stats.nba.com')?response(nba):url===Q.depthUrl('BOS')?response(chart()):{ok:false,status:404}});
    assert(!result.projected['1']);assert(result.projected['6']);assert.equal(result.projected['6'].origin,'espn-depth');assert.equal(Object.keys(result.confirmed).length,0);
  });
  await test('archived fallback payload retains its original source and capture time',async()=>{
    const captured=[];const old=new Date(now-3600000).toISOString();
    await Q.load({date:fixture.date,fixtures:[fixture],rosters:{BOS:roster},clock:()=>now,onCapture:(kind,source,payload,time)=>captured.push({kind,source,payload,time}),fetcher:async url=>url.includes('projected-lineups.json')?response({schemaVersion:1,teams:{BOS:{source:Q.depthUrl('BOS'),capturedAt:old,payload:chart()}}}):{ok:false,status:503}});
    assert.equal(captured.length,1);assert.equal(captured[0].time,old);assert.equal(captured[0].source,Q.depthUrl('BOS'));assert.deepEqual(captured[0].payload,chart());
  });
  await test('lineup polling runs independently, avoids overlap, refreshes on return, and cleans up',async()=>{
    let tick,visible,resolve,calls=0,cleared=false;
    const target={visibilityState:'visible',addEventListener:(name,fn)=>{visible=fn;},removeEventListener:(name,fn)=>{assert.equal(fn,visible);visible=null;}};
    const stop=Q.startRefresh(async()=>{calls++;await new Promise(r=>{resolve=r;});},{target,setTimer:(fn,ms)=>{assert.equal(ms,300000);tick=fn;return 1;},clearTimer:()=>{cleared=true;}});
    tick();tick();assert.equal(calls,1);resolve();await new Promise(setImmediate);
    target.visibilityState='hidden';tick();assert.equal(calls,1);target.visibilityState='visible';visible();assert.equal(calls,2);
    stop();resolve();await new Promise(setImmediate);tick();assert.equal(calls,2);assert(cleared);assert.equal(visible,null);
  });
  console.log(JSON.stringify({passed}));
})().catch(error=>{console.error(error);process.exitCode=1;});
