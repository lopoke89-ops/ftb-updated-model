/* Descriptive scopes and grades. Prior archive and grade outputs do not feed forecasts. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.FTBScoutingHistory=factory();
})(typeof window!=='undefined'?window:this,function(){
  'use strict';
  const PHASES={
    'regular-and-playoffs':'Regular season + Playoffs',
    'regular-season':'Regular season',playoffs:'Playoffs',
    all:'All competitions · includes Play-in & Cup final',
    'play-in':'Play-in','nba-cup-final':'NBA Cup final'
  };
  const GRADE_POLICY={minimumStarts:5,priorStarts:20,smallSampleStarts:20,
    bands:[['S',.25,'#FFD700'],['A',.18,'#4ADE80'],['B',.12,'#60A5FA'],['C',.06,'#FB923C'],['D',0,'#94a3b8']]};
  function snapshotForScope(A,data,options={}){
    const headToHead=Array.isArray(options.historyMatchups),phase=options.phase||'all';
    const pairKey=g=>[g.home,g.away].sort().join('|');
    const pairs=new Map((options.historyMatchups||[]).filter(g=>g.home&&g.away&&g.home!==g.away).map(g=>[pairKey(g),[g.home,g.away].sort()]));
    const eligible=g=>(phase==='all'||(phase==='regular-and-playoffs'?['regular-season','playoffs'].includes(g.phase):g.phase===phase))&&(!headToHead||pairs.has(pairKey(g)));
    // The core still sees every dated fixture for membership and previous-lineup
    // chronology. Only its statistics phase predicate is narrowed to exact pairs.
    const original=new Map(data.games.map(g=>[g.id,g]));
    const synthetic=headToHead||phase==='regular-and-playoffs',tag='__scouting_scope__';
    const scoped=synthetic?{...data,games:data.games.map(g=>eligible(g)?{...g,phase:tag}:g)}:data;
    const result=A.snapshot(scoped,{...options,phase:synthetic?tag:phase});
    const included=result.games.map(g=>original.get(g.id)),gameTeams={};
    const window=Number(options.window)||0,counts={};
    for(let i=included.length-1;i>=0;i--){const g=included[i];gameTeams[g.id]=[g.home,g.away].filter(t=>{counts[t]=(counts[t]||0)+1;return !window||counts[t]<=window;});}
    const games=included.filter(g=>gameTeams[g.id].length);
    const meta={...result.meta,phase,totalGames:games.length,statsThrough:games.at(-1)?.date||null,lineupsThrough:result.meta.statsThrough,headToHead,historyMatchups:[...pairs.values()]};
    const teamPlayerStats={};
    if(headToHead)for(const g of games)for(const team of gameTeams[g.id])for(const p of g.teams[team].players){
      if(!p.played)continue;
      const players=teamPlayerStats[team]||(teamPlayerStats[team]={});
      const stats=players[p.id]||(players[p.id]={gp:0,points:0,threeMade:0,threeAttempted:0});
      stats.gp++;stats.points+=p.points||0;stats.threeMade+=p.threeMade||0;stats.threeAttempted+=p.threeAttempted||0;
    }
    return {...result,meta,games,gameTeams,teamPlayerStats};
  }
  function selectEvidence(A,current,archive,options={}){
    const {season,mode,date,basis='auto',archiveTrusted=false,...scope}=options;
    const eligible=mode==='upcoming'&&archiveTrusted&&archive?.meta?.season<season&&/^\d{4}-\d{2}-\d{2}$/.test(date||'');
    const useArchive=eligible&&(basis==='archive'||basis==='auto'&&!current.games.length);
    if(!useArchive)return {snapshot:current,season,isArchive:false,blocked:basis==='archive'&&!eligible};
    // A fully completed earlier archive can use its verified season roles. Earlier dates
    // retain the strict pregame cutoff, so a future result cannot enter this display.
    const snapshot=snapshotForScope(A,archive,{...scope,date,mode:date>archive.meta.asOfDate?'review':'pregame'});
    return {snapshot,season:archive.meta.season,isArchive:true,blocked:false};
  }
  function playerEvidence(snapshot,id,team,acrossStints=false){
    let p=snapshot.players[String(id)]||{id:String(id),gp:0,ftbByTeam:{},ppg:null,threePm:null,threePa:null};
    if(snapshot.meta?.headToHead){
      acrossStints=false;
      const s=snapshot.teamPlayerStats[team]?.[String(id)]||{gp:0,points:0,threeMade:0,threeAttempted:0};
      p={...p,...s,ppg:s.gp?s.points/s.gp:null,threePm:s.gp?s.threeMade/s.gp:null,threePa:s.gp?s.threeAttempted/s.gp:null};
    }
    const historyTeams=Object.entries(p.ftbByTeam||{}).filter(([t,d])=>d.gp>0&&(!snapshot.meta?.headToHead||t===team)).map(([t])=>t);
    let detail=p.ftbByTeam?.[team]||{};
    if(acrossStints){
      detail={shots:{},positions:{}};
      for(const d of Object.values(p.ftbByTeam||{})){
        for(const key of ['gp','starts','ftbMade','starterWins','openingAttempts','openingSample','openingMade','openingFreeThrowAttempts','firstFgAttempts','firstFgSample'])detail[key]=(detail[key]||0)+(d[key]||0);
        for(const key of ['shots','positions'])for(const [k,n] of Object.entries(d[key]||{}))detail[key][k]=(detail[key][k]||0)+n;
      }
      // Adding old teams' full-season game counts is not a player's denominator.
      detail.unknownShots=p.unknownShots||0;
    }
    const gp=detail.gp||0,starts=detail.starts||0,wins=detail.ftbMade||0,teamGames=snapshot.teamStats[team]?.games||0;
    return {...p,scoutingDetail:detail,historyTeams,hasHistory:gp>0,
      teamFtbMade:gp?wins:null,teamGames:acrossStints?null:teamGames,
      firstBasketRate:acrossStints?(gp?wins/gp:null):(gp&&teamGames?wins/teamGames:null),
      appearanceRate:gp?wins/gp:null,startRate:starts?(detail.starterWins||0)/starts:null,
      openingAttemptRate:detail.openingSample?(detail.openingAttempts||0)/detail.openingSample:null};
  }
  function gradeContext(snapshot,trusted=true){
    const players=Object.values(snapshot.players||{});
    const starts=players.reduce((n,p)=>n+(p.starts||0),0),wins=players.reduce((n,p)=>n+(p.starterWins||0),0);
    return {trusted,target:snapshot.meta.target,starts,wins,baseline:starts&&wins>=0&&wins<=starts?wins/starts:null};
  }
  function historicalGrade(player,context){
    const d=player.scoutingDetail||{},starts=d.starts||0,wins=d.starterWins||0;
    const unrated=reason=>({rated:false,letter:'NR',color:'#64748b',score:null,starts,wins,reason});
    if(!context?.trusted)return unrated('History not verified');
    if(context.target!=='first-team-score-including-free-throws')return unrated('Target not graded');
    if(!Number.isFinite(context.baseline))return unrated('No starter sample');
    if(!Number.isInteger(starts)||!Number.isInteger(wins)||wins<0||wins>starts)return unrated('Invalid starter sample');
    if(starts<GRADE_POLICY.minimumStarts)return unrated(`Needs ${GRADE_POLICY.minimumStarts} starts · has ${starts}`);
    const score=(wins+GRADE_POLICY.priorStarts*context.baseline)/(starts+GRADE_POLICY.priorStarts);
    const [letter,,color]=GRADE_POLICY.bands.find(([,minimum])=>score>=minimum);
    return {rated:true,letter,color,score,starts,wins,rawRate:wins/starts,baseline:context.baseline,
      priorStarts:GRADE_POLICY.priorStarts,smallSample:starts<GRADE_POLICY.smallSampleStarts,
      reason:`Historical grade · ${starts} starts${starts<GRADE_POLICY.smallSampleStarts?' · small sample':''}`};
  }
  function sortPlayers(players,key){
    const descriptive=key==='probability'&&players.every(p=>p.forecastWithheld||!Number.isFinite(p.probability));
    const field=descriptive||key==='firstscores'?'teamFtbMade':key==='starts'?'startRate':key==='ppg'?'ppg':'probability';
    return [...players].sort((a,b)=>{
      const av=key==='grade'?a.historicalGrade?.score:a[field],bv=key==='grade'?b.historicalGrade?.score:b[field];
      if(Number.isFinite(av)!==Number.isFinite(bv))return Number.isFinite(av)?-1:1;
      return (Number.isFinite(bv)?bv-av:0)||(b.teamFtbMade||0)-(a.teamFtbMade||0)||a.name.localeCompare(b.name);
    });
  }
  function injuryPlayerId(athlete){
    if(/^\d+$/.test(String(athlete?.id||'')))return String(athlete.id);
    const ids=new Set((athlete?.links||[]).map(l=>String(l.href||'').match(/\/id\/(\d+)(?:\/|$|\?)/)?.[1]).filter(Boolean));
    return ids.size===1?[...ids][0]:null;
  }
  function parseInjuries(json,capturedAt){
    if(!Array.isArray(json?.injuries))throw Error('Injury response unavailable');
    const entries={};let unresolved=0,total=0;
    for(const t of json.injuries)for(const p of t.injuries||[]){
      total++;const id=injuryPlayerId(p.athlete);if(!id){unresolved++;continue;}
      const status=String(p.status||'UNKNOWN').toUpperCase();
      entries[id]={id,name:p.athlete?.displayName,status:status.includes('OUT')||status.includes('SUSP')?'OUT':status.includes('DOUBT')?'DOUBTFUL':status.includes('QUESTION')?'QUESTIONABLE':status.includes('PROBABLE')?'PROBABLE':status,reason:p.shortComment||p.longComment||'',capturedAt};
    }
    return {entries,unresolved,total};
  }
  return {PHASES,GRADE_POLICY,snapshotForScope,gradeContext,historicalGrade,selectEvidence,playerEvidence,sortPlayers,injuryPlayerId,parseInjuries};
});
