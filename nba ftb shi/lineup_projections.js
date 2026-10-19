/* Dated, sourced lineup context. Projections never grant starter confirmation. */
(function(root,factory){
  'use strict';
  const api=factory(typeof module==='object'&&module.exports?require('./lineups.js'):root?.FTBLineups);
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(!root)return;root.FTBProjectedLineups=api;
  if(!root.React)return;
  const h=root.React.createElement;
  const time=value=>value&&Number.isFinite(Date.parse(value))?new Date(value).toLocaleString('en-US',{timeZone:'America/Chicago',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' CT':'Unavailable';
  root.FTBLineupPanel=function LineupPanel({fixtures=[],lineups={},now=Date.now(),teamColors={},onRefresh,busy=false}){
    const teams=fixtures.flatMap(f=>[f.away,f.home].map(team=>({team,fixture:f,view:api.teamView(team,f,lineups,now)})));
    const confirmed=teams.filter(t=>t.view.kind==='confirmed').length,projected=teams.filter(t=>t.view.kind==='projected').length;
    return h('details',{className:'starting-lineups'},h('summary',null,'Starting lineups',h('span',null,`${confirmed} confirmed · ${projected} projected · ${teams.length-confirmed-projected} unavailable`)),
      h('div',{className:'lineup-panel-body'},h('p',null,'Depth-chart projections use the current roster and reported availability. Expected starters remain unconfirmed. EV can use these projections for provisional lineup scenarios; finalized first-basket picks need fresh NBA confirmation.'),
        h('button',{type:'button',onClick:onRefresh,disabled:busy},busy?'Checking lineups…':'Refresh lineups'),
        h('small',{className:'lineup-check'},`Last check: ${time(lineups.checkedAt)} · checks every 5 minutes while this view is open`),
        !teams.length&&h('p',null,'Choose an upcoming game date with scheduled fixtures.'),
        h('div',{className:'lineup-team-grid'},teams.map(({team,fixture,view})=>h('section',{key:fixture.id+'|'+team,className:'lineup-team',style:{'--team-color':teamColors[team]||'#64748b'}},
          h('h3',null,team,h('small',null,` vs ${fixture.home===team?fixture.away:fixture.home}`)),
          h('strong',{className:'lineup-kind '+view.kind},view.label),
          view.players.length?h('ol',null,view.players.map(p=>h('li',{key:p.id},h('span',{className:'lineup-position'},p.position),h('span',null,p.name,p.availability==='QUESTIONABLE'?' · Questionable':'',p.depthRank>1?h('small',null,`Depth chart #${p.depthRank} · next listed available player`):null)))):h('p',null,view.reason||'A complete current five is unavailable.'),
          view.players.length>0&&h('p',{className:'lineup-provenance'},h('a',{href:view.players[0].source,target:'_blank',rel:'noreferrer'},view.players[0].origin==='espn-depth'?'ESPN depth chart':'NBA daily lineups'),` · checked ${time(view.players[0].capturedAt)}`,view.players[0].sourceTimestamp?h('small',null,`Source updated ${time(view.players[0].sourceTimestamp)}`):null),
          (lineups.issues||[]).filter(s=>s.startsWith(team+':')).map((s,i)=>h('small',{key:i,className:'lineup-issue'},s.substring(team.length+2)))))),
        lineups.officialStatus&&h('p',{className:'lineup-provenance'},lineups.officialStatus)));
  };
})(typeof window==='object'?window:null,function(L){
  'use strict';
  const POS=['PG','SG','SF','PF','C'],MAX_AGE=6*60*60*1000,OFFICIAL_AGE=5*60*1000,LOOKAHEAD=7;
  const TEAM_IDS={ATL:1,BOS:2,BKN:17,CHA:30,CHI:4,CLE:5,DAL:6,DEN:7,DET:8,GSW:9,HOU:10,IND:11,LAC:12,LAL:13,MEM:29,MIA:14,MIL:15,MIN:16,NOP:3,NYK:18,OKC:25,ORL:19,PHI:20,PHX:21,POR:22,SAC:23,SAS:24,TOR:28,UTA:26,WAS:27};
  const normalizeTeam=t=>({GS:'GSW',NY:'NYK',SA:'SAS',NO:'NOP',WSH:'WAS',UTAH:'UTA',PHO:'PHX'}[t]||t);
  const dayFormat=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Chicago',year:'numeric',month:'2-digit',day:'2-digit'});
  const day=now=>dayFormat.format(new Date(now));
  const depthUrl=team=>'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+TEAM_IDS[team]+'/depthcharts';
  const officialUrl=date=>'https://stats.nba.com/js/data/leaders/00_daily_lineups_'+date.replace(/-/g,'')+'.json';
  const BRIDGE='https://raw.githubusercontent.com/lopoke89-ops/ftb-updated-model/nba-live-lineups/';
  const fresh=(capturedAt,now,limit)=>{const age=now-Date.parse(capturedAt);return Number.isFinite(age)&&age>=0&&age<=limit;};
  function withinHorizon(date,now){const days=(Date.parse(date+'T12:00Z')-Date.parse(day(now)+'T12:00Z'))/86400000;return Number.isInteger(days)&&days>=0&&days<=LOOKAHEAD;}
  function validProjection(record,fixture,now=Date.now()){
    if(!record||record.status!=='projected'||record.fixtureId!==fixture?.id||record.date!==fixture.date||![fixture.home,fixture.away].includes(record.team)||fixture.status!=='pre'||now>=Date.parse(fixture.scheduledTipoff)||!POS.includes(record.position)||!withinHorizon(fixture.date,now))return false;
    return record.origin==='espn-depth'?record.source===depthUrl(record.team)&&record.season===fixture.season&&fresh(record.capturedAt,now,MAX_AGE):record.origin==='nba-expected'&&record.source===officialUrl(fixture.date)&&fresh(record.capturedAt,now,OFFICIAL_AGE);
  }
  function injuryStatus(injuries){
    const values=(injuries||[]).flatMap(i=>[i.status,i.type?.name,i.type?.description]).filter(v=>typeof v==='string').map(s=>s.toUpperCase().replace(/[-_]/g,' '));
    return values.includes('OUT')?'OUT':values.includes('DOUBTFUL')?'DOUBTFUL':values.some(s=>['QUESTIONABLE','DAY TO DAY'].includes(s))?'QUESTIONABLE':null;
  }
  function parseDepth(json,{team,fixture,roster=[],injuries={},capturedAt,now=Date.now()}){
    if(!TEAM_IDS[team]||String(json?.team?.id)!==String(TEAM_IDS[team])||normalizeTeam(json.team.abbreviation)!==team)throw Error('Depth-chart team identity mismatch');
    const season=Number(json.season?.year),expected=Number(String(fixture.season).split('-')[0])+1;
    if(season!==expected||!fresh(capturedAt,now,MAX_AGE)||!withinHorizon(fixture.date,now)||fixture.status!=='pre'||now>=Date.parse(fixture.scheduledTipoff))throw Error('Depth-chart season, fixture, or capture is stale');
    if(json.timestamp&&(!Number.isFinite(Date.parse(json.timestamp))||Date.parse(json.timestamp)>now+300000))throw Error('Invalid depth-chart source time');
    const charts=(json.depthchart||[]).filter(d=>d.positions&&POS.every(p=>d.positions[p.toLowerCase()]));
    if(charts.length!==1)throw Error('Complete five-position depth chart unavailable');
    const pool=POS.map(position=>(charts[0].positions[position.toLowerCase()].athletes||[]).map((p,index)=>{
      const matches=roster.filter(r=>String(r.id)===String(p.id)&&r.team===team);
      if(matches.length!==1)return null;
      const listed=injuryStatus(p.injuries),current=injuries[String(p.id)]?.status;
      if(['OUT','DOUBTFUL'].includes(current)||['OUT','DOUBTFUL'].includes(listed))return null;
      return {id:String(p.id),name:matches[0].name,team,position,status:'projected',origin:'espn-depth',depthRank:index+1,
        availability:current==='QUESTIONABLE'||listed==='QUESTIONABLE'?'QUESTIONABLE':current||'Unconfirmed',
        fixtureId:fixture.id,date:fixture.date,season:fixture.season,capturedAt,sourceTimestamp:json.timestamp||null,source:depthUrl(team)};
    }).filter(Boolean).slice(0,5));
    // Choose a complete unique five using the smallest sum of listed depth ranks.
    let best=null,bestRank=Infinity;
    function assign(index,chosen,used,rank){
      if(rank>=bestRank)return;
      if(index===POS.length){best=chosen;bestRank=rank;return;}
      for(const p of pool[index])if(!used.has(p.id))assign(index+1,[...chosen,p],new Set([...used,p.id]),rank+p.depthRank);
    }
    assign(0,[],new Set(),0);
    if(!best)throw Error('Five distinct current-roster players unavailable after availability checks');
    return Object.fromEntries(best.map(p=>[p.id,p]));
  }
  function teamView(team,fixture,lineups,now=Date.now()){
    const confirmed=Object.values(lineups?.confirmed||{}).filter(p=>p.team===team&&L?.validConfirmation(p,fixture,now));
    if(confirmed.length===5&&new Set(confirmed.map(p=>p.position)).size===5&&new Set(confirmed.map(p=>p.id)).size===5)return {kind:'confirmed',label:'NBA confirmed starters',players:POS.map(pos=>confirmed.find(p=>p.position===pos))};
    const projected=Object.values(lineups?.projected||{}).filter(p=>p.team===team&&validProjection(p,fixture,now));
    if(projected.length===5&&new Set(projected.map(p=>p.position)).size===5&&new Set(projected.map(p=>p.id)).size===5&&new Set(projected.map(p=>p.origin)).size===1&&new Set(projected.map(p=>p.capturedAt)).size===1)return {kind:'projected',label:projected[0].origin==='nba-expected'?'NBA expected starters · unconfirmed':'Depth-chart projection · unconfirmed',players:POS.map(pos=>projected.find(p=>p.position===pos))};
    return {kind:'unavailable',label:'Lineup unavailable',players:[],reason:fixture.status!=='pre'||now>=Date.parse(fixture.scheduledTipoff)?'Pregame lineup context is closed for this fixture.':'No complete, fresh lineup for this game.'};
  }
  function playerView(id,team,fixture,lineups,now=Date.now()){
    if(!fixture)return {label:'Starter status unconfirmed',record:null};
    const view=teamView(team,fixture,lineups,now),record=view.players.find(p=>p.id===String(id));
    return {label:record?(view.kind==='confirmed'?'NBA confirmed starter':record.origin==='nba-expected'?'NBA expected starter · unconfirmed':'Depth-chart projected starter · unconfirmed'):view.players.length?'Not in '+(view.kind==='confirmed'?'NBA confirmed':'current projected')+' five':'Starter status unconfirmed',record:record||null,teamStatus:view.kind};
  }
  async function load({date,fixtures,rosters,injuries={},officialParser,fetcher=fetch,clock=Date.now,onCapture}){
    const start=clock(),checkedAt=new Date(start).toISOString(),issues=[],confirmed={},projected={};
    const eligible=fixtures.filter(f=>f.date===date&&f.status==='pre'&&start<Date.parse(f.scheduledTipoff)&&withinHorizon(date,start));
    const teams=[...new Set(eligible.flatMap(f=>[f.home,f.away]))];
    if(!teams.length)return {date,checkedAt,confirmed,projected,issues,officialStatus:'Choose a pregame fixture within the next seven days.'};
    const request=async url=>{const response=await fetcher(url,{cache:'no-store',signal:AbortSignal.timeout(7000)});if(!response.ok)throw Error('HTTP '+response.status);return response.json();};
    let bridge;
    const fallback=()=>bridge||(bridge=request(BRIDGE+'projected-lineups.json?capture='+Math.floor(start/300000)));
    const depth=Promise.all(teams.map(async team=>{
      try{
        let json,capturedAt;
        try{json=await request(depthUrl(team));capturedAt=new Date(clock()).toISOString();}
        catch(error){const saved=await fallback(),entry=saved?.teams?.[team];if(saved.schemaVersion!==1||entry?.source!==depthUrl(team))throw Error('Depth-chart capture unavailable');json=entry.payload;capturedAt=entry.capturedAt;}
        const fixture=eligible.find(f=>[f.home,f.away].includes(team));
        Object.assign(projected,parseDepth(json,{team,fixture,roster:rosters[team],injuries,capturedAt,now:clock()}));
        await Promise.resolve(onCapture?.('ESPN depth chart',depthUrl(team),json,capturedAt)).catch(()=>{});
      }catch(error){issues.push(team+': '+error.message);}
    }));
    let officialStatus='Official NBA confirmation is checked on game day.';
    const official=(async()=>{
      if(date!==day(start)||!officialParser)return;
      const source=officialUrl(date);
      try{
        let json,capturedAt,transport='direct NBA';
        try{json=await request(source);capturedAt=new Date(clock()).toISOString();}
        catch(error){const saved=await request(BRIDGE+'live-lineups.json?capture='+Math.floor(start/300000));if(saved.schemaVersion!==1||saved.date!==date||saved.source!==source||!fresh(saved.capturedAt,clock(),OFFICIAL_AGE))throw Error('NBA cloud capture unavailable or older than five minutes');json=saved.payload;capturedAt=saved.capturedAt;transport='NBA cloud capture';}
        const parsed=officialParser(json,{date,fixtures:eligible,rosters,capturedAt,now:clock()});
        await Promise.resolve(onCapture?.('NBA lineups',source,json,capturedAt)).catch(()=>{});
        const active=new Set((json.games||[]).flatMap(g=>['homeTeam','awayTeam'].flatMap(side=>(g[side]?.players||[]).filter(p=>p.rosterStatus==='Active'&&['Confirmed','Expected'].includes(p.lineupStatus)).map(p=>String(p.personId)))));
        Object.assign(confirmed,parsed.confirmed);
        const expected=Object.values(parsed.projected).filter(p=>active.has(p.nbaId)&&!['OUT','DOUBTFUL'].includes(injuries[p.id]?.status)).map(p=>({...p,availability:injuries[p.id]?.status||'Unconfirmed'}));
        await depth;
        for(const team of teams){
          const records=expected.filter(p=>p.team===team);
          const complete=records.length===5&&new Set(records.map(p=>p.position)).size===5;
          if(Object.values(confirmed).some(p=>p.team===team)||complete){for(const [id,p]of Object.entries(projected))if(p.team===team)delete projected[id];}
          if(complete&&!Object.values(confirmed).some(p=>p.team===team))for(const p of records)projected[p.id]={...p,origin:'nba-expected'};
        }
        issues.push(...parsed.issues);officialStatus=`NBA checked ${capturedAt} · ${transport} · ${Object.keys(confirmed).length} confirmed starters. Confirmations expire after five minutes.`;
      }catch(error){officialStatus='NBA confirmation unavailable: '+error.message+'. Projected starters remain unconfirmed.';}
    })();
    await Promise.all([depth,official]);
    return {date,checkedAt:new Date(clock()).toISOString(),confirmed,projected,issues,officialStatus};
  }
  function startRefresh(refresh,{setTimer=setInterval,clearTimer=clearInterval,target=typeof document==='object'?document:null}={}){
    let busy=false,stopped=false;
    const tick=async()=>{if(stopped||busy||target?.visibilityState==='hidden')return;busy=true;try{await refresh();}catch(_){}finally{busy=false;}};
    const visible=()=>{if(!target||target.visibilityState==='visible')tick();};
    const timer=setTimer(tick,300000);target?.addEventListener('visibilitychange',visible);
    return ()=>{stopped=true;clearTimer(timer);target?.removeEventListener('visibilitychange',visible);};
  }
  return {POS,TEAM_IDS,MAX_AGE,OFFICIAL_AGE,LOOKAHEAD,BRIDGE,day,depthUrl,officialUrl,withinHorizon,validProjection,injuryStatus,parseDepth,teamView,playerView,load,startRefresh};
});
