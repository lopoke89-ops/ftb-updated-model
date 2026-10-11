/* Descriptive scopes and grades. Prior archive and grade outputs do not feed forecasts. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory(require('./readiness_policy.json'));
  else root.FTBScoutingHistory=factory(root.__FTB_READINESS__);
})(typeof window!=='undefined'?window:this,function(READINESS){
  'use strict';
  const PHASES={
    'regular-and-playoffs':'Regular season + Playoffs',
    'regular-season':'Regular season',playoffs:'Playoffs',
    all:'All competitions · includes Play-in & Cup final',
    'play-in':'Play-in','nba-cup-final':'NBA Cup final'
  };
  const GRADE_POLICY={minimumStarts:5,priorStarts:20,smallSampleStarts:20,shareCap:true,
    bands:[['S',.25,'#FFD700'],['A',.18,'#4ADE80'],['B',.12,'#60A5FA'],['C',.06,'#FB923C'],['D',0,'#94a3b8']]};
  function readiness(snapshot,team,opponent,market='first-team-basket'){
    const rule=READINESS?.thresholds?.[market];
    const teamGames=snapshot.teamStats?.[team]?.games||0,opponentGames=snapshot.teamStats?.[opponent]?.games||0;
    const playerReady=market!=='first-team-basket'||(snapshot.rosters?.[team]||[]).some(p=>{
      const e=playerEvidence(snapshot,p.id,team),q=firstBasketQuality(e,gradeContext(snapshot));
      return e.scoutingDetail.gp>=rule?.playerGames&&q.rated&&q.factor>0;
    });
    const ready=!!rule&&teamGames>=rule.teamGames&&opponentGames>=rule.teamGames&&playerReady;
    return {ready,teamGames,opponentGames,requiredTeamGames:rule?.teamGames??null,requiredPlayerGames:rule?.playerGames??5,
      reason:ready?'Team and opponent samples ready':`Needs ${rule?.teamGames??'evaluated'} games for both teams and an eligible player; ${team||'team'} ${teamGames}, ${opponent||'opponent'} ${opponentGames}`};
  }
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
    const gradeBaseline=headToHead?gradeContext(snapshotForScope(A,data,{...options,historyMatchups:undefined})):null;
    return {...result,meta,games,gameTeams,teamPlayerStats,gradeBaseline};
  }
  function selectEvidence(A,current,archive,options={}){
    const {season,mode,date,basis='auto',archiveTrusted=false,team,opponent,market='first-team-basket',...scope}=options;
    const eligible=mode==='upcoming'&&archiveTrusted&&archive?.meta?.season<season&&/^\d{4}-\d{2}-\d{2}$/.test(date||'');
    const state=readiness(current,team,opponent,market);
    const useArchive=eligible&&(basis==='archive'||basis==='auto'&&!state.ready);
    if(!useArchive)return {snapshot:current,season,isArchive:false,readiness:state,blocked:basis==='archive'&&!eligible};
    // A fully completed earlier archive can use its verified season roles. Earlier dates
    // retain the strict pregame cutoff, so a future result cannot enter this display.
    const snapshot=snapshotForScope(A,archive,{...scope,date,mode:date>archive.meta.asOfDate?'review':'pregame'});
    return {snapshot,season:archive.meta.season,isArchive:true,readiness:state,blocked:false};
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
    if(snapshot.gradeBaseline)return {...snapshot.gradeBaseline,trusted,target:snapshot.meta.target};
    const players=Object.values(snapshot.players||{});
    const starts=players.reduce((n,p)=>n+(p.starts||0),0),wins=players.reduce((n,p)=>n+(p.starterWins||0),0);
    return {trusted,target:snapshot.meta.target,starts,wins,baseline:starts&&wins>=0&&wins<=starts?wins/starts:null};
  }
  function historicalGrade(player,context){
    const d=player.scoutingDetail||{},starts=d.starts||0,wins=d.starterWins||0;
    const unrated=reason=>({rated:false,letter:'NR',color:'#64748b',score:null,starts,wins,reason});
    if(!context?.trusted)return unrated('History not verified');
    if(!['first-team-score-including-free-throws','first-team-made-field-goal'].includes(context.target))return unrated('Target not graded');
    if(!Number.isFinite(context.baseline))return unrated('No starter sample');
    if(!Number.isInteger(starts)||!Number.isInteger(wins)||wins<0||wins>starts)return unrated('Invalid starter sample');
    if(starts<GRADE_POLICY.minimumStarts)return unrated(`Needs ${GRADE_POLICY.minimumStarts} starts · has ${starts}`);
    // A conditional success rate from a few starts cannot establish an elite
    // full-sample record. Cap the grade at observed scoring share in that same
    // scope. Prior history across trades uses appearances, not old-team totals.
    const gp=d.gp,totalScores=d.ftbMade,shareBasis=player.teamGames===null?'appearance':'team-game';
    const shareDenominator=shareBasis==='appearance'?gp:player.teamGames;
    if(!Number.isInteger(gp)||gp<starts||!Number.isInteger(totalScores)||totalScores<wins||totalScores>gp||
       !Number.isInteger(shareDenominator)||shareDenominator<gp||shareDenominator<=0)return unrated('Complete scoring-share sample unavailable');
    const share=totalScores/shareDenominator;
    const adjustedStartRate=(wins+GRADE_POLICY.priorStarts*context.baseline)/(starts+GRADE_POLICY.priorStarts);
    const score=Math.min(adjustedStartRate,share),shareLimited=share<adjustedStartRate;
    const [letter,,color]=GRADE_POLICY.bands.find(([,minimum])=>score>=minimum);
    return {rated:true,letter,color,score,starts,wins,rawRate:wins/starts,baseline:context.baseline,
      adjustedStartRate,share,shareBasis,shareDenominator,shareNumerator:totalScores,shareLimited,
      priorStarts:GRADE_POLICY.priorStarts,smallSample:starts<GRADE_POLICY.smallSampleStarts,
      reason:`Historical grade · ${starts} starts${shareLimited?' · scoring-share cap':''}${starts<GRADE_POLICY.smallSampleStarts?' · small sample':''}`};
  }
  function firstBasketQuality(player,context){
    const grade=historicalGrade(player,context);
    return {...grade,factor:grade.rated&&context.baseline>0?Math.min(1,grade.score/context.baseline):0};
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
  const LIVE_REFRESH_MILLIS=5*60*1000;
  function validateCollectedSeason(d){
    if(d?.meta?.season!=='2026-27'||d.meta.parentDatasetId!=='nba-2026-27-canonical'||!Array.isArray(d.games)||d.meta.totalGames!==d.games.length||new Set(d.games.map(g=>g.id)).size!==d.games.length)throw Error('Invalid collected season snapshot');
    if(d.games.length&&(!d.parlay||d.parlay.meta.parentEvidenceContentHash!==d.meta.evidenceContentHash||d.parlay.openingEvidence?.meta?.parentEvidenceContentHash!==d.meta.evidenceContentHash))throw Error('Collected shooting/opening evidence does not match');
    for(const g of d.games){
      if(g.boxScoreSource!=='NBA official final box'||!g.sourceHash||d.parlay.openingEvidence.games[g.id]?.sourceHash!==g.sourceHash)throw Error('Unverified NBA gamebook evidence');
      for(const box of Object.values(g.teams)){
        const played=box.players.filter(p=>p.played);
        if(played.reduce((n,p)=>n+p.points,0)!==box.points||played.filter(p=>p.starter).length!==5||played.some(p=>p.statsSourceHash!==g.sourceHash||2*p.fgm+p.threeMade+p.ftm!==p.points))throw Error('Collected NBA stat lines do not reconcile');
      }
    }
    return true;
  }
  function startLiveRefresh(refresh,{setTimer=setInterval,clearTimer=clearInterval}={}){
    let busy=false,stopped=false;
    const tick=async()=>{if(stopped||busy)return;busy=true;try{await refresh();}finally{busy=false;}};
    const timer=setTimer(()=>{tick().catch(()=>{});},LIVE_REFRESH_MILLIS);
    return ()=>{stopped=true;clearTimer(timer);};
  }
  function mergeInjuries(previous,incoming){
    const merged={...incoming};
    // Omission from a later report is not an explicit clearance of a known restriction.
    for(const [id,p] of Object.entries(previous))if((!merged[id]&&['OUT','DOUBTFUL','QUESTIONABLE'].includes(p.status))||(p.status==='QUESTIONABLE'&&merged[id]&&!['AVAILABLE','ACTIVE','CLEARED','WILL PLAY','WILLPLAY','OUT','DOUBTFUL','QUESTIONABLE'].includes(merged[id].status)))merged[id]={...p,carriedForward:true,reportedStatus:merged[id]?.status};
    return merged;
  }
  function pickEligibility(id,context){
    if(!context?.upcoming)return {excluded:false,provisional:false,reason:'Historical evidence'};
    const injury=context.injuries?.[id],status=injury?.status;
    if(['OUT','DOUBTFUL'].includes(status))return {excluded:true,provisional:false,reason:status+(injury.carriedForward?' · awaiting explicit clearance':'')};
    if(status==='QUESTIONABLE')return {excluded:false,provisional:true,reason:'Questionable · availability unconfirmed'};
    if(status&&!['AVAILABLE','ACTIVE','CLEARED','WILL PLAY','WILLPLAY','PROBABLE'].includes(status))return {excluded:false,provisional:true,reason:'Availability status unresolved'};
    if(!context.fresh||context.date!==context.today||injury?.carriedForward)return {excluded:false,provisional:true,reason:'Current availability evidence unavailable or stale'};
    return {excluded:false,provisional:false,reason:status||'No injury listed in current report'};
  }
  return {PHASES,GRADE_POLICY,READINESS,readiness,firstBasketQuality,snapshotForScope,gradeContext,historicalGrade,selectEvidence,playerEvidence,sortPlayers,injuryPlayerId,parseInjuries,LIVE_REFRESH_MILLIS,startLiveRefresh,mergeInjuries,pickEligibility,validateCollectedSeason};
});
