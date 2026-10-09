/* Dated basketball evidence. No network access or writes in this module. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBAnalyst=api;})(typeof window==='object'?window:globalThis,function(){
  'use strict';
  const POS=['PG','SG','SF','PF','C'],SHOTS=['layup','dunk','mid','threeP','ft','tip','hook'];
  const DEFAULT_TARGET='first-team-score-including-free-throws';
  const TARGETS={
    [DEFAULT_TARGET]:'First team score · free throws included',
    'first-game-score-including-free-throws':'First game score · free throws included',
    'first-team-made-field-goal':'First team made field goal',
    'first-game-made-field-goal':'First game made field goal'
  };
  const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const date=s=>String(s||'').replace(/^(\d{4})(\d{2})(\d{2})$/,'$1-$2-$3');
  function positionRecord(raw,reference=null){
    const u=String(raw||'').toUpperCase().trim();
    const exact={'1':'PG','2':'SG','3':'SF','4':'PF','5':'C','CENTER':'C','POINT GUARD':'PG','SHOOTING GUARD':'SG','SMALL FORWARD':'SF','POWER FORWARD':'PF'};
    const primary=POS.includes(u)?u:exact[u]||null;
    const broad=u==='G'||u==='GUARD'?'G':u==='F'||u==='FORWARD'?'F':u.includes('-')?u:null;
    const known=reference&&POS.includes(reference.position)?reference.position:null;
    const compatible=!broad||broad==='G'&&['PG','SG'].includes(known)||broad==='F'&&['SF','PF'].includes(known)||broad.includes('-')&&broad.split('-').some(x=>x==='C'&&known==='C'||x==='G'&&['PG','SG'].includes(known)||x==='F'&&['SF','PF'].includes(known));
    return {rawPosition:u,broadPosition:broad,position:primary||known||'?',
      positionSource:primary?'specific-source-position':known?(reference.source||'verified-role-reference'):'unavailable',
      positionConflict:!!(primary&&known&&primary!==known||!primary&&known&&!compatible),referencePosition:known};
  }
  function wilson(wins,n){if(!n)return null;const z=1.959963984540054,p=wins/n,d=1+z*z/n,c=(p+z*z/(2*n))/d,r=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [Math.max(0,c-r),Math.min(1,c+r)];}
  function clockSeconds(s){const m=String(s??'').match(/^(?:(\d+):)?(\d+(?:\.\d+)?)$/);return m?Number(m[1]||0)*60+Number(m[2]):NaN;}
  function order(s){return [Number(s.period||99),-clockSeconds(s.clock),Number(s.sequence||0)];}
  function compare(a,b){const x=order(a),y=order(b);for(let i=0;i<3;i++){if(!Number.isFinite(x[i])||!Number.isFinite(y[i]))return null;if(x[i]!==y[i])return x[i]-y[i];}return 0;}
  function targetScores(g,target){
    const source=target.includes('field-goal')?g.firstFieldGoals:g.firstScores;
    if(!target.startsWith('first-game'))return source;
    const entries=Object.entries(source||{});if(entries.length!==2)return {};
    const c=compare(entries[0][1],entries[1][1]);return c===null||c===0?{}:{[entries[c<0?0:1][0]]:entries[c<0?0:1][1]};
  }
  function emptyPlayer(p){return {id:p.id,sourcePlayerId:p.id,name:p.name,team:'',position:'?',rawPosition:p.rawPosition,
    gp:0,points:0,threeMade:0,threeAttempted:0,starts:0,ftbMade:0,ftbByTeam:{},shots:Object.fromEntries(SHOTS.map(k=>[k,0])),unknownShots:0,starterWins:0,latestDate:'',latestTeam:'',provenance:{}};}
  function teamDetail(){return {ftbMade:0,teamGames:0,gp:0,starts:0,starterWins:0,openingAttempts:0,openingSample:0,openingMade:0,openingFreeThrowAttempts:0,firstFgAttempts:0,firstFgSample:0,shots:Object.fromEntries(SHOTS.map(k=>[k,0])),positions:Object.fromEntries([...POS,'unknown'].map(k=>[k,0]))};}
  function snapshot(data,options={}){
    if(!data||!data.meta||!Array.isArray(data.games))throw Error('Dated evidence unavailable');
    const selectedDate=date(options.date||data.meta.asOfDate),mode=options.mode||'pregame',phase=options.phase||'all',windowSize=Number(options.window)||0,target=options.target||DEFAULT_TARGET;
    if(!TARGETS[target])throw Error('Unsupported scoring target');
    const chronology=data.games.filter(g=>mode==='review'?g.date<=data.meta.asOfDate:g.date<selectedDate).sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id));
    let included=chronology.filter(g=>phase==='all'||g.phase===phase);
    if(windowSize){const keep=new Set();const perTeam={};for(let i=included.length-1;i>=0;i--){const g=included[i];for(const t of [g.home,g.away]){perTeam[t]=(perTeam[t]||0)+1;if(perTeam[t]<=windowSize)keep.add(g.id+'|'+t);}}options={...options,_teamKeep:keep};}
    const players={},teamStats={},rosters={},lastLineups={},latestMembership={};
    // Membership and last-lineup references are always dated, independent of a statistics phase filter.
    for(const g of chronology)for(const [team,box] of Object.entries(g.teams)){
      rosters[team]=box.players.map(p=>({...p,team,observedDate:g.date}));lastLineups[team]={ids:box.starters,date:g.date,source:'previous postgame lineup; unconfirmed'};
      for(const p of box.players)latestMembership[p.id]={team,date:g.date,rawPosition:p.rawPosition,name:p.name};
    }
    for(const g of included){const scores=targetScores(g,target);
      const gameWinner=targetScores(g,'first-game-score-including-free-throws');
      for(const [team,box] of Object.entries(g.teams)){
        if(options._teamKeep&&!options._teamKeep.has(g.id+'|'+team))continue;
        const ts=teamStats[team]||(teamStats[team]={games:0,firstPointWins:0,firstPointUnknown:0,tipWins:0,tipSample:0,openingSample:0,openingAttempts:{},allowedCounts:Object.fromEntries([...POS,'unknown'].map(k=>[k,0])),scoringCounts:Object.fromEntries([...POS,'unknown'].map(k=>[k,0])),firstScoreCount:0});
        ts.games++;if(Object.keys(gameWinner).length===0)ts.firstPointUnknown++;else if(gameWinner[team])ts.firstPointWins++;
        const opening=g.opening&&!g.opening.error?g.opening:null;
        if(opening&&opening.firstPossessionTeam){ts.tipSample++;if(opening.firstPossessionTeam===team)ts.tipWins++;}
        const attempt=opening&&opening.firstAttempts&&opening.firstAttempts[team];
        if(attempt){ts.openingSample++;const aid=attempt.athleteIds[0];ts.openingAttempts[aid]=(ts.openingAttempts[aid]||0)+1;}
        const score=scores&&scores[team]; const opp=team===g.home?g.away:g.home;const allowed=scores&&scores[opp];
        function role(s,t){if(!s)return 'unknown';if(mode==='review')return POS.includes(s.position)?s.position:'unknown';const actor=g.teams[t].players.find(p=>p.id===s.id);return positionRecord(actor?.rawPosition).position;}
        if(score){ts.firstScoreCount++;const r=role(score,team);ts.scoringCounts[POS.includes(r)?r:'unknown']++;}
        if(allowed){const r=role(allowed,opp);ts.allowedCounts[POS.includes(r)?r:'unknown']++;}
        for(const p of box.players){const pr=players[p.id]||(players[p.id]=emptyPlayer(p));const dt=pr.ftbByTeam[team]||(pr.ftbByTeam[team]=teamDetail());
          pr.latestDate=g.date;pr.latestTeam=team;pr.rawPosition=p.rawPosition;dt.teamGames++;
          if(p.played){pr.gp++;dt.gp++;pr.points+=p.points||0;pr.threeMade+=p.threeMade||0;pr.threeAttempted+=p.threeAttempted||0;}
          if(p.starter){pr.starts++;dt.starts++;}
          if(score&&score.id===p.id){pr.ftbMade++;dt.ftbMade++;if(p.starter){pr.starterWins++;dt.starterWins++;}const shot=score.shot||(score.points===3?'threeP':score.points===1?'ft':'mid');if(SHOTS.includes(shot)){pr.shots[shot]++;dt.shots[shot]++;}else pr.unknownShots++;const r=role(score,team);dt.positions[POS.includes(r)?r:'unknown']++;}
          if(attempt&&p.played){dt.openingSample++;if(attempt.athleteIds[0]===p.id){dt.openingAttempts++;if(attempt.scoringPlay&&attempt.points>0)dt.openingMade++;if(/free throw/i.test(attempt.text))dt.openingFreeThrowAttempts++;}}
          const fga=opening&&opening.firstFieldGoalAttempts&&opening.firstFieldGoalAttempts[team];if(fga&&p.played){dt.firstFgSample++;if(fga.athleteIds[0]===p.id)dt.firstFgAttempts++;}
        }
      }
    }
    for(const pr of Object.values(players)){
      const membership=latestMembership[pr.id];pr.team=membership?membership.team:pr.latestTeam;pr.rawPosition=membership?membership.rawPosition:pr.rawPosition;
      const datedRole=(data.datedRoleEvidence||[]).filter(r=>r.playerId===pr.id&&(mode==='review'?r.effectiveGameDate<=data.meta.asOfDate:r.effectiveGameDate<selectedDate)).sort((a,b)=>b.effectiveGameDate.localeCompare(a.effectiveGameDate))[0];
      const ref=mode==='review'&&options.positionReferences?options.positionReferences[pr.id]:datedRole?{position:datedRole.position,source:`dated NBA gamebook (${datedRole.effectiveGameDate}); retrospective publication history unavailable`}:null;
      Object.assign(pr,positionRecord(pr.rawPosition,ref));pr.pos=pr.position;pr.ppg=pr.gp?pr.points/pr.gp:null;pr.threePm=pr.gp?pr.threeMade/pr.gp:null;pr.threePa=pr.gp?pr.threeAttempted/pr.gp:null;
      // Team-game share uses all team games in scope, even games before a player's first appearance.
      for(const [team,d] of Object.entries(pr.ftbByTeam)){d.teamGames=teamStats[team].games;d.firstBasketRate=d.teamGames?d.ftbMade/d.teamGames:null;}
      const td=pr.ftbByTeam[pr.team]||teamDetail();pr.teamGames=teamStats[pr.team]?teamStats[pr.team].games:0;
      pr.firstBasketRate=pr.teamGames?td.ftbMade/pr.teamGames:null;pr.appearanceRate=td.gp?td.ftbMade/td.gp:null;pr.startRate=td.starts?td.starterWins/td.starts:null;
      pr.startInterval=wilson(td.starterWins,td.starts);pr.appearanceInterval=wilson(td.ftbMade,td.gp);
      pr.teamFtbMade=td.ftbMade;pr.teamGp=td.gp;pr.teamStarts=td.starts;pr.teamStarterWins=td.starterWins;
      pr.openingAttemptRate=td.openingSample?td.openingAttempts/td.openingSample:null;pr.openingSample=td.openingSample;
      pr.starterConfirmed=false;pr.isStarter=false;const ll=lastLineups[pr.team];pr.starterRank=ll&&ll.ids.includes(pr.id)?ll.ids.indexOf(pr.id)+1:null;
      pr.lastLineupRank=pr.starterRank;pr.lastLineupTeam=pr.team;pr.lineupDate=ll?ll.date:null;pr.identityResolved=true;
      pr.viewType='derived-analysis';pr.scoringDefinition=target;pr.asOfDate=chronology.length?chronology.at(-1).date:null;
    }
    // Players known in the earlier roster with no appearances in the selected phase/window remain eligible candidates.
    for(const [team,roster] of Object.entries(rosters))for(const p of roster)if(!players[p.id]){
      const pr=emptyPlayer(p);pr.team=team;Object.assign(pr,positionRecord(p.rawPosition));pr.pos=pr.position;pr.ppg=null;pr.threePm=null;pr.threePa=null;pr.teamGames=teamStats[team]?.games||0;pr.teamFtbMade=0;pr.teamGp=0;pr.teamStarts=0;pr.teamStarterWins=0;pr.starterRank=lastLineups[team].ids.includes(p.id)?lastLineups[team].ids.indexOf(p.id)+1:null;pr.lastLineupRank=pr.starterRank;pr.lastLineupTeam=team;pr.lineupDate=lastLineups[team].date;pr.starterConfirmed=false;pr.isStarter=false;pr.identityResolved=true;players[p.id]=pr;
    }
    for(const t of Object.values(teamStats)){t.firstPointPct=t.games-t.firstPointUnknown?100*t.firstPointWins/(t.games-t.firstPointUnknown):null;t.firstPointSample=t.games-t.firstPointUnknown;t.firstPointSource='ordered-first-score-evidence';t.tipPct=t.tipSample?100*t.tipWins/t.tipSample:null;t.tipSource=t.tipSample?'explicit-opening-possession':'unavailable';t.source='dated-evidence';}
    return {meta:{parentDatasetId:data.meta.parentDatasetId,viewType:'dated-analysis',mode,target,phase,window:windowSize,selectedDate,
      statsThrough:chronology.length?chronology.at(-1).date:null,totalGames:included.length,
      historicalAvailability:'unavailable',publicationHistory:'unavailable; corrected-data retrospective research',
      lineupStatus:'previous-game reference; unconfirmed'},players,teamStats,rosters,lastLineups,games:included};
  }
  function distribution(snap,team,options={}){
    if(snap.meta.target.startsWith('first-game'))return {withheld:true,reason:'Whole-game race model not validated',probabilities:{}};
    const roster=snap.rosters[team]||[],excluded=new Set(options.excludeIds||[]),candidateIds=new Set(roster.map(p=>p.id));
    const ids=[...candidateIds].filter(id=>!excluded.has(id));if(!ids.length)return {withheld:true,reason:'Dated eligible roster unavailable',probabilities:{}};
    const games=snap.teamStats[team]?.games||0,counts={};let knownWins=0;
    for(const id of candidateIds){const wins=snap.players[id]?.ftbByTeam[team]?.ftbMade||0;knownWins+=wins;if(!excluded.has(id))counts[id]=wins+1;}
    const other=Math.max(0,games-knownWins)+1;counts.OTHER=other;
    if(options.model==='opportunity'){
      const starters=new Set(options.starterIds||snap.lastLineups[team]?.ids||[]);
      for(const id of ids){const d=snap.players[id]?.ftbByTeam[team]||teamDetail();counts[id]=starters.has(id)?(d.starterWins+1)/(d.starts+5):(d.ftbMade+1)/(d.gp+20);}
      counts.OTHER=other/(games+candidateIds.size+1);
    }
    const temp=Number(options.temperature)||1;
    const weights=Object.fromEntries(Object.entries(counts).map(([k,v])=>[k,Math.pow(v,1/temp)])),sum=Object.values(weights).reduce((a,b)=>a+b,0);
    const probabilities=Object.fromEntries(Object.entries(weights).map(([k,v])=>[k,v/sum]));
    return {withheld:false,target:snap.meta.target,team,probabilities,model:options.model||'share',temperature:temp,
      status:'retrospective-research-baseline',lineupAssumption:'prior lineup reference; not confirmed',sample:games,
      unknownProbability:probabilities.OTHER,excludedIds:[...excluded]};
  }
  function positionCharts(snap){const scoring={},allowed={};for(const [team,s] of Object.entries(snap.teamStats)){
    const n=s.firstScoreCount,na=Object.values(s.allowedCounts).reduce((a,b)=>a+b,0);
    scoring[team]={totalGames:n,unknownCount:s.scoringCounts.unknown,pct:Object.fromEntries(POS.map(p=>[p,n?100*s.scoringCounts[p]/n:0])),unknownPct:n?100*s.scoringCounts.unknown/n:0};
    allowed[team]={totalGames:na,unknownCount:s.allowedCounts.unknown,pct:Object.fromEntries(POS.map(p=>[p,na?100*s.allowedCounts[p]/na:0])),unknownPct:na?100*s.allowedCounts.unknown/na:0};
  }return {scoring,allowed};}
  function validateDistribution(d){if(d.withheld)return true;const vs=Object.values(d.probabilities);return vs.length>0&&vs.every(v=>Number.isFinite(v)&&v>=0&&v<=1)&&Math.abs(vs.reduce((a,b)=>a+b,0)-1)<1e-8;}
  return {POS,SHOTS,DEFAULT_TARGET,TARGETS,norm,date,clockSeconds,positionRecord,wilson,compare,targetScores,snapshot,distribution,positionCharts,validateDistribution};
});
