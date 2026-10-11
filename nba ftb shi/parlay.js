/* Transparent market rankings. Scores are descriptive, never win probabilities. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory(require('./scouting_history.js'),require('./lineups.js'));else root.FTBParlay=factory(root.FTBScoutingHistory,root.FTBLineups);})(typeof window!=='undefined'?window:this,function(H,L){
  'use strict';
  const MARKETS=['first-team-basket','points','threes'];
  const LABELS={'first-team-basket':'First Team Basket',points:'Points',threes:'Three-Pointers Made'};
  const WEIGHTS={offense:1/3,defense:1/3,opportunity:1/3};
  const MIN_GAMES=5;
  // Operational completeness requirement, not a fitted predictive threshold.
  const SELECTION_POLICY={version:'parlay-selection-quality-v1',minimumKnownProduction:.8};
  const FIRST_TARGETS=['first-team-score-including-free-throws','first-team-made-field-goal'];
  const sum=(xs,key)=>xs.reduce((n,p)=>n+(Number.isFinite(p[key])?p[key]:0),0);
  function correlation(rows,x,y){
    const paired=rows.filter(r=>Number.isFinite(r[x])&&Number.isFinite(r[y]));
    if(paired.length<MIN_GAMES)return {n:paired.length,r:null,reason:`Needs ${MIN_GAMES} paired games`};
    const mx=sum(paired,x)/paired.length,my=sum(paired,y)/paired.length;
    let xx=0,yy=0,xy=0;for(const p of paired){const a=p[x]-mx,b=p[y]-my;xx+=a*a;yy+=b*b;xy+=a*b;}
    return {n:paired.length,r:xx&&yy?Math.max(-1,Math.min(1,xy/Math.sqrt(xx*yy))):null,reason:xx&&yy?null:'No variation in attempts or makes'};
  }
  // Specific roles stay separate. Coarse comparisons preserve explicit gamebook G/F/C groups.
  function positionGroup(p,resolution='specific'){const pos=p.position||p.rawPosition||'',raw=String(p.rawPosition||pos).toUpperCase();
    if(resolution==='broad'){
      const role=['G','F','C','GUARD','FORWARD','CENTER'].includes(raw)?raw:['PG','SG','SF','PF','C','G','F'].includes(pos)?pos:raw;
      if(['PG','SG','G','GUARD'].includes(role))return 'G';
      if(['SF','PF','F','FORWARD'].includes(role))return 'F';
      if(['C','CENTER'].includes(role))return 'C';
      return 'unknown';
    }
    if(['PG','SG','SF','PF','C'].includes(pos))return pos;
    return ['PG','SG','SF','PF','C'].includes(raw)?raw:raw==='CENTER'?'C':'unknown';
  }
  function shootingRow(game,team,p,supplement,valid){
    if(game.boxScoreSource==='NBA official final box'&&!valid)return null;
    const extra=valid?supplement.games?.[game.id]?.[team]?.[p.id]:null;
    // Newly collected seasons carry these fields directly. Older/mismatched supplements cannot fill them.
    const row={...p,...(extra||{})};
    for(const k of ['points','fga','fgm','threeMade','threeAttempted','ftm','fta'])if(!Number.isFinite(row[k])||row[k]<0)return null;
    if(row.fgm>row.fga||row.threeMade>row.threeAttempted||row.threeMade>row.fgm||row.threeAttempted>row.fga||row.ftm>row.fta||2*row.fgm+row.threeMade+row.ftm!==row.points)return null;
    return row;
  }
  function summarize(rows){
    const gp=rows.length,total=Object.fromEntries(['points','fga','fgm','threeMade','threeAttempted','ftm','fta'].map(k=>[k,sum(rows,k)]));
    for(const k of ['rebounds','assists','steals','blocks','turnovers','fouls','offensiveRebounds','defensiveRebounds','plusMinus'])total[k]=gp&&rows.every(r=>Number.isFinite(r[k]))?sum(rows,k):null;
    const minutes=rows.filter(r=>Number.isFinite(r.minutes));
    const exactMinutes=gp&&rows.every(r=>Number.isFinite(r.minutesSeconds))?sum(rows,'minutesSeconds')/60:null;
    const average=k=>gp&&Number.isFinite(total[k])?total[k]/gp:null;
    return {gp,total,ppg:gp?total.points/gp:null,fgm:gp?total.fgm/gp:null,fga:gp?total.fga/gp:null,
      threePm:gp?total.threeMade/gp:null,threePa:gp?total.threeAttempted/gp:null,ftm:gp?total.ftm/gp:null,
      fgPct:total.fga?total.fgm/total.fga:null,threePct:total.threeAttempted?total.threeMade/total.threeAttempted:null,
      fta:gp?total.fta/gp:null,ftPct:total.fta?total.ftm/total.fta:null,
      tsPct:total.fga+.44*total.fta?total.points/(2*(total.fga+.44*total.fta)):null,
      rpg:average('rebounds'),apg:average('assists'),spg:average('steals'),bpg:average('blocks'),
      tov:average('turnovers'),pf:average('fouls'),oreb:average('offensiveRebounds'),dreb:average('defensiveRebounds'),plusMinus:average('plusMinus'),
      mpg:exactMinutes!==null?exactMinutes/gp:minutes.length?sum(minutes,'minutes')/minutes.length:null,minutesGames:minutes.length,
      fgCorrelation:correlation(rows,'fga','fgm'),threeCorrelation:correlation(rows,'threeAttempted','threeMade')};
  }
  function sample(snapshot,supplement){
    const valid=supplement?.meta?.parentEvidenceContentHash===snapshot.evidenceHash;
    const positionScope=snapshot.meta.positionScope||'specific';
    const groupFor=(p,g)=>{const group=positionGroup(p,positionScope);return group==='unknown'?positionGroup({position:g.positionRoles?.[p.id]},positionScope):group;};
    const byPlayer={},byTeam={},positions={};
    for(const g of snapshot.games)for(const team of snapshot.gameTeams[g.id]||[]){
      const t=byTeam[team]||(byTeam[team]={games:0,points:{},threes:{},first:{},allowedPoints:{},allowedThrees:{},allowedFirst:{},totals:{points:0,threes:0,first:0,allowedPoints:0,allowedThrees:0,allowedFirst:0},missing:0});t.games++;
      const opp=team===g.home?g.away:g.home;
      for(const [side,box] of [[team,g.teams[team]],[opp,g.teams[opp]]]){
        const own=side===team;
        for(const p of box.players){if(!p.played)continue;
          const group=groupFor(p,g),row=shootingRow(g,side,p,supplement,valid);
          const prefix=own?'':'allowed';
          for(const [key,value] of [['points',p.points],['threes',p.threeMade]]){const field=own?key:prefix+key[0].toUpperCase()+key.slice(1);t[field][group]=(t[field][group]||0)+(value||0);t.totals[field]+=value||0;}
          if(own){const id=String(p.id),entry=byPlayer[id]||(byPlayer[id]={all:[],teams:{},appearances:0,missing:0,firstEvents:[],firstFieldGoalEvents:[]});entry.appearances++;if(row){entry.all.push({...row,team,date:g.date,gameId:g.id,starter:p.starter});(entry.teams[team]||(entry.teams[team]=[])).push({...row,team,date:g.date,gameId:g.id,starter:p.starter});}else{entry.missing++;t.missing++;}positions[id]=group;}
        }
        const first=(snapshot.meta.target==='first-team-made-field-goal'?g.firstFieldGoals:g.firstScores)?.[side];if(first){const actor=box.players.find(p=>String(p.id)===String(first.id));const group=groupFor(actor||{id:first.id},g),field=own?'first':'allowedFirst';t[field][group]=(t[field][group]||0)+1;t.totals[field]++;}
        if(own&&snapshot.openingVerified){const record=e=>({...e,team,date:g.date,gameId:g.id,source:g.opening.sourceUrl,sourceHash:g.opening.sourceHash});
          if(first&&byPlayer[first.id])byPlayer[first.id].firstEvents.push(record(first));
          const fg=g.firstFieldGoals?.[side];if(fg&&byPlayer[fg.id])byPlayer[fg.id].firstFieldGoalEvents.push(record(fg));}
      }
    }
    return {byPlayer,byTeam,positions,positionScope,supplementValid:valid,openingVerified:!!snapshot.openingVerified};
  }
  function lineDecision(rows,market,line){
    if(!Number.isFinite(line)||line<0)return {line:null,side:null,status:'Market line unavailable'};
    const key=market==='points'?'points':'threeMade',mean=sum(rows,key)/rows.length,side=mean>line?'Over':mean<line?'Under':null;
    return {line,side,status:side?'Historical mean comparison · price/value unassessed':'No directional edge at this line',
      over:rows.filter(r=>r[key]>line).length,under:rows.filter(r=>r[key]<line).length,push:rows.filter(r=>r[key]===line).length,n:rows.length};
  }
  function seasonDecision(rows,market,stats){
    const key=market==='points'?'points':'threeMade',average=market==='points'?stats.ppg:stats.threePm;
    if(!Number.isFinite(average)||!rows.length)return {average:null,threshold:null,n:0,hits:0,rate:null};
    const threshold=Math.ceil(average-1e-10),hits=rows.filter(r=>r[key]>=threshold).length;
    return {average,threshold,n:rows.length,hits,rate:hits/rows.length};
  }
  function rankTeam({team,opponent,roster=[],snapshot,sample:scope,seasonScope=scope,acrossStints=false,lines={},excludedIds=[],trusted=true,eligibility={},upcoming=false,confirmedStarters={},fixture=null,now=Date.now(),minimumGames=MIN_GAMES,variant='full'}){
    const t=scope.byTeam[team],def=opponent?scope.byTeam[opponent]:null,excluded=new Set(excludedIds.map(String));
    const rejected=roster.filter(p=>excluded.has(String(p.id))||eligibility[p.id]?.excluded).map(p=>({id:p.id,name:p.name,reason:eligibility[p.id]?.reason||'Excluded scenario'}));
    const qualityContext=H.gradeContext(snapshot,trusted);
    const candidates=roster.filter(p=>!excluded.has(String(p.id))&&!eligibility[p.id]?.excluded).map(p=>{
      const confirmation=confirmedStarters[p.id],confirmedRole=L.validConfirmation(confirmation,fixture,now)&&confirmation.id===String(p.id)&&confirmation.team===team;
      const source=scope.byPlayer[String(p.id)],rows=acrossStints?source?.all||[]:source?.teams[team]||[],stats=summarize(rows),role={...snapshot.players[p.id],...p,rawPosition:confirmedRole?confirmation.position:snapshot.players[p.id]?.rawPosition||p.rawPosition,position:confirmedRole?confirmation.position:snapshot.players[p.id]?.position},group=positionGroup(role,scope.positionScope);
      const detail=snapshot.players[p.id]?.ftbByTeam||{},details=acrossStints?Object.values(detail):[detail[team]||{}];
      const count=k=>details.reduce((n,d)=>n+(d[k]||0),0),starts=count('starts'),wins=count('starterWins'),openingSample=count('openingSample');
      const fieldGoalOnly=snapshot.meta.target==='first-team-made-field-goal',firstEvents=(source?.firstEvents||[]).filter(e=>acrossStints||e.team===team),firstFieldGoalEvents=(source?.firstFieldGoalEvents||[]).filter(e=>acrossStints||e.team===team);
      return {id:String(p.id),name:p.name,team,group,positionSource:confirmedRole?`Current NBA confirmed lineup · ${confirmation.source}`:scope.positionScope==='broad'&&['G','F','C'].includes(role.rawPosition)?`NBA gamebook group ${role.rawPosition} · latest historical appearance`:snapshot.players[p.id]?.positionSource||'Current-roster role',rows,stats,starts,wins,startRate:starts?wins/starts:null,
        seasonStats:summarize(seasonScope.byPlayer[String(p.id)]?.all||[]),firstEvents,firstFieldGoalEvents,
        firstQuality:H.firstBasketQuality(H.playerEvidence(snapshot,p.id,team,acrossStints),qualityContext),
        historyTeams:[...new Set(rows.map(r=>r.team))],hasTradeHistory:Object.keys(detail).length>1,
        openingRate:fieldGoalOnly?(count('firstFgSample')?count('firstFgAttempts')/count('firstFgSample'):null):openingSample?count('openingAttempts')/openingSample:null,openingSample:fieldGoalOnly?count('firstFgSample'):openingSample,
        missing:acrossStints?source?.missing||0:Math.max(0,(detail[team]?.gp||0)-rows.length),
        lineup:snapshot.lastLineups[team]?.ids?.includes(String(p.id))?'Previous lineup · unconfirmed':'Starter status unconfirmed'};
    });
    return MARKETS.map(market=>{
      const required=typeof minimumGames==='object'?minimumGames[market]||MIN_GAMES:minimumGames;
      let reason=!trusted?'History verification failed':!opponent?'Select a matchup to supply the opponent':!t||!def?'No team/opponent sample in selected competition':null;
      if(!reason&&market==='first-team-basket'&&!scope.openingVerified)reason='Verified NBA opening play-by-play unavailable for this sample';
      const ranked=[],audit=[...rejected];
      const eligible=[];
      if(!reason)for(const p of candidates){
        if(p.group==='unknown'||p.stats.gp<required||p.missing){audit.push({id:p.id,name:p.name,reason:p.group==='unknown'?'Specific position unavailable':p.missing?'Incomplete shooting records':`Needs ${required} appearances; has ${p.stats.gp}`});continue;}
        const first=market==='first-team-basket',three=market==='threes',corr=three?p.stats.threeCorrelation:p.stats.fgCorrelation;
        if(first&&(!p.firstQuality.rated||p.firstQuality.factor<=0)||!first&&variant!=='no-correlation'&&!(corr.r>0)||three&&!(p.stats.threePa>0)){audit.push({id:p.id,name:p.name,reason:first?p.firstQuality.reason:three&&!(p.stats.threePa>0)?'No observed three-point attempts':corr.reason||'Attempts/makes correlation is not positive'});continue;}
        eligible.push(p);
      }
      // Rejected players must not set the scale for the contenders in this market.
      const max=k=>Math.max(1,...eligible.map(p=>p.stats[k]||0));
      const maximum={fga:max('fga'),threePa:max('threePa'),mpg:max('mpg'),first:Math.max(.01,...eligible.map(p=>(p.wins+1)/(p.starts+5)))};
      for(const p of eligible){
        const first=market==='first-team-basket',three=market==='threes',corr=three?p.stats.threeCorrelation:p.stats.fgCorrelation;
        const key=first?'first':three?'threes':'points',allowed='allowed'+key[0].toUpperCase()+key.slice(1);
        if(!t.totals[key]||!def.totals[allowed])continue;
        const offense=(t[key][p.group]||0)/t.totals[key],defense=(def[allowed][p.group]||0)/def.totals[allowed];
        const opportunity=first?.5*((p.wins+1)/(p.starts+5))/maximum.first+.3*(p.openingRate||0)+.2*Math.min(1,p.starts/p.stats.gp):
          .4*((p.stats.mpg||0)/maximum.mpg)+.3*(p.stats[three?'threePa':'fga']/maximum[three?'threePa':'fga'])+.2*(p.stats[three?'threePct':'fgPct']||0)+.1*(variant==='no-correlation'?0:Math.max(0,corr.r));
        const rawScore=100*(WEIGHTS.offense*offense+WEIGHTS.defense*defense+WEIGHTS.opportunity*opportunity);
        const qualityFactor=first?p.firstQuality.factor:1;
        const score=(variant==='no-position'?100*opportunity:rawScore)*qualityFactor;
        const availability=eligibility[p.id]||{provisional:upcoming,reason:'Availability unconfirmed'};
        const confirmation=confirmedStarters[p.id],starterConfirmed=L.validConfirmation(confirmation,fixture,now)&&confirmation.id===p.id&&confirmation.team===team;
        const provisional=upcoming&&(availability.provisional||first&&!starterConfirmed);
        ranked.push({...p,score,rawScore,qualityFactor,confirmation:starterConfirmed?confirmation:null,components:{offense,defense,opportunity},correlation:first?null:corr,market,
          provisional,finalized:upcoming&&!provisional,eligibilityReason:first&&upcoming&&!starterConfirmed?'Starter confirmation unavailable':availability.reason,
          seasonTarget:first?null:seasonDecision(p.rows,market,p.seasonStats),
          decision:first?{line:null,side:null,status:snapshot.meta.target==='first-team-made-field-goal'?'First team made field goal · free throws excluded':'First team score · made free throws included'}:lineDecision(p.rows,market,lines[p.id+'|'+market]),
          sampleQuality:p.stats.gp<20?'Small sample':'20+ observed games',
          unknownOffense:(t[key].unknown||0)/t.totals[key],unknownDefense:(def[allowed].unknown||0)/def.totals[allowed]});
      }
      ranked.sort((a,b)=>b.score-a.score||b.stats.gp-a.stats.gp||a.name.localeCompare(b.name));
      return {team,opponent,market,label:market==='first-team-basket'?(snapshot.meta.target==='first-team-made-field-goal'?'First Team Basket · Field Goal':'First Team Score · Includes FT'):LABELS[market],pick:(upcoming?ranked.find(p=>p.finalized):null)||ranked[0]||null,candidates:ranked.length,ranked,audit,
        reason:ranked.length?null:reason||`No eligible player: needs ${required} complete appearances, known position${market==='first-team-basket'?` and ${MIN_GAMES} starts with supported scoring share`: ' and positive attempts/makes correlation'}`};
    });
  }
  function applySelectionPolicy(slot,{scope,minimumGames=MIN_GAMES,minimumTeamGames=0,rosterSize=0}={}){
    const key=slot.market==='first-team-basket'?'first':slot.market==='threes'?'threes':'points',allowed='allowed'+key[0].toUpperCase()+key.slice(1);
    const own=scope?.byTeam[slot.team],opponent=scope?.byTeam[slot.opponent];
    const known=(t,k)=>t?.totals[k]>0?1-(t[k].unknown||0)/t.totals[k]:null;
    const ownKnown=known(own,key),opponentKnown=known(opponent,allowed);
    const teamGames=own?.games||0,opponentGames=opponent?.games||0,sampleReady=teamGames>=minimumTeamGames&&opponentGames>=minimumTeamGames;
    const ranked=(slot.ranked||[]).filter(p=>p.stats.gp>=minimumGames),audit=[...(slot.audit||[]),...(slot.ranked||[]).filter(p=>p.stats.gp<minimumGames).map(p=>({id:p.id,name:p.name,reason:`Needs ${minimumGames} appearances; has ${p.stats.gp}`}))];
    const coverageReady=ownKnown!==null&&opponentKnown!==null&&ownKnown+1e-10>=SELECTION_POLICY.minimumKnownProduction&&opponentKnown+1e-10>=SELECTION_POLICY.minimumKnownProduction;
    const percent=v=>v===null?'unavailable':(100*v).toFixed(1)+'%';
    const coverageReason=`Insufficient positional coverage: ${slot.team} ${percent(ownKnown)} known ${key} production; ${slot.opponent} ${percent(opponentKnown)} known opponent allowance. At least 80% is required on both sides; broad G/F roles cannot identify PG/SG/SF/PF.`;
    const selected=slot.pick?(ranked.find(p=>p.id===slot.pick.id)||ranked.find(p=>p.finalized)||ranked[0]||null):null;
    return {...slot,ranked,audit,candidates:ranked.length,pick:coverageReady&&sampleReady?selected:null,reason:!coverageReady?slot.reason||coverageReason:!sampleReady?`Needs ${minimumTeamGames} games for both teams; ${slot.team} ${teamGames}, ${slot.opponent} ${opponentGames}`:selected?null:slot.reason||`No player has ${minimumGames} complete appearances`,
      selectionReview:{...SELECTION_POLICY,coverageReady,sampleReady,ownKnown,opponentKnown,minimumGames,minimumTeamGames,teamGames,opponentGames,rosterSize,eligibleCandidates:ranked.length,excludedCandidates:audit.length,conditionalLeader:ranked[0]?{id:ranked[0].id,name:ranked[0].name}:null}};
  }
  function build(A,H,data,supplement,{phase='regular-season',firstBasketTarget=FIRST_TARGETS[0],...options}={}){
    if(!['regular-season','playoffs'].includes(phase))throw Error('Choose regular season or playoffs; samples cannot be pooled');
    if(!FIRST_TARGETS.includes(firstBasketTarget))throw Error('Unsupported first team basket definition');
    const opening=supplement?.openingEvidence,openingVerified=!!opening&&opening.meta.parentEvidenceContentHash===data.meta.evidenceContentHash&&data.games.every(g=>opening.games[g.id]?.sourceHash===g.sourceHash);
    const knownAttempts=events=>Object.fromEntries(Object.entries(events).filter(([,e])=>e.athleteIds.length===1&&!e.identityUnresolved));
    const verifiedData=openingVerified?{...data,games:data.games.map(g=>{const o=opening.games[g.id];return {...g,firstScores:o.firstScores,firstFieldGoals:o.firstFieldGoals,opening:{eventId:g.id,firstAttempts:knownAttempts(o.firstAttempts),firstFieldGoalAttempts:knownAttempts(o.firstFieldGoalAttempts),orderedEvents:o.orderedEvents,source:opening.meta.source,sourceUrl:o.source,sourceHash:o.sourceHash}};})}:data;
    const gameById=new Map(data.games.map(g=>[g.id,g]));
    const extraRoles=supplement?.roleEvidenceMeta?.parentEvidenceContentHash===data.meta.evidenceContentHash?(supplement.datedRoleEvidence||[]).filter(r=>{
      const g=gameById.get(r.gameId);return g&&r.effectiveGameDate===g.date&&r.gamebookSourceHash===g.sourceHash&&['PG','SG','SF','PF','C'].includes(r.position)&&r.source===L.urlFor(g.date)&&/^\d+$/.test(r.nbaPlayerId)&&g.teams[r.team]?.players.some(p=>p.id===r.playerId&&p.played&&p.starter);
    }):[];
    const roles=[...(data.datedRoleEvidence||[]),...extraRoles].sort((a,b)=>a.effectiveGameDate.localeCompare(b.effectiveGameDate)),knownRoles={},latestRoles={};let roleIndex=0;
    const cutoff=options.date||data.meta.asOfDate;
    for(const r of roles)if(options.mode==='review'?r.effectiveGameDate<=data.meta.asOfDate:r.effectiveGameDate<cutoff)latestRoles[r.playerId]=r;
    const roleReferences=Object.fromEntries(Object.entries(latestRoles).map(([id,r])=>[id,{position:r.position,source:`dated NBA/PDF-matched role (${r.effectiveGameDate}); postgame observation`} ]));
    const scopedData={...verifiedData,datedRoleEvidence:Object.values(latestRoles),games:[...verifiedData.games].sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id)).map(g=>{
      while(roleIndex<roles.length&&roles[roleIndex].effectiveGameDate<=g.date){const r=roles[roleIndex++];if(['PG','SG','SF','PF','C'].includes(r.position))knownRoles[r.playerId]=r.position;}
      const reviewRoles=options.mode==='review'?options.positionReferences||{}:{};
      const teams=Object.fromEntries(Object.entries(g.teams).map(([team,box])=>[team,{...box,players:box.players.map(p=>({...p,rawPosition:p.officialPosition||p.rawPosition}))}]));
      return {...g,teams,positionRoles:Object.fromEntries(Object.values(teams).flatMap(b=>b.players).filter(p=>knownRoles[p.id]||['PG','SG','SF','PF','C'].includes(reviewRoles[p.id]?.position)).map(p=>[p.id,knownRoles[p.id]||reviewRoles[p.id]?.position]))};
    })};
    const snapshot=H.snapshotForScope(A,scopedData,{...options,positionReferences:{...options.positionReferences,...roleReferences},phase,target:firstBasketTarget});
    snapshot.meta.positionScope=options.positionScope==='broad'?'broad':'specific';
    snapshot.openingVerified=openingVerified;
    snapshot.roleRecords=roles.length;
    snapshot.evidenceHash=data.meta.evidenceContentHash;
    const scope=sample(snapshot,supplement);
    return {snapshot,scope,positionScope:snapshot.meta.positionScope,season:data.meta.season,phase,through:snapshot.meta.statsThrough,complete:!!data.meta.coverageComplete,
      allPlayerStats:acrossStints=>Object.fromEntries(Object.entries(scope.byPlayer).map(([id,p])=>[id,acrossStints?summarize(p.all):Object.fromEntries(Object.entries(p.teams).map(([t,rows])=>[t,summarize(rows)]))]))};
  }
  function rankPositionVariants({specific,broad},args,positionScope='auto'){
    if(!['auto','specific','broad'].includes(positionScope))throw Error('Unsupported positional comparison');
    const rank=m=>rankTeam({...args,snapshot:m.snapshot,sample:m.scope}).map(s=>({...s,positionScope:m.positionScope||'specific',evidenceModel:m}));
    if(positionScope==='broad')return rank(broad);
    const fine=rank(specific);if(positionScope==='specific')return fine;
    const coarse=rank(broad);
    return fine.map((slot,i)=>{
      const review=applySelectionPolicy(slot,{scope:specific.scope}).selectionReview;
      const unresolvedPool=!slot.ranked.length&&slot.audit.some(p=>p.reason==='Specific position unavailable');
      if(review.coverageReady&&!unresolvedPool)return slot;
      return {...coarse[i],positionFallbackReason:`Specific-position coverage ${Number.isFinite(review.ownKnown)?(100*review.ownKnown).toFixed(1)+'%':'unavailable'} offense / ${Number.isFinite(review.opponentKnown)?(100*review.opponentKnown).toFixed(1)+'%':'unavailable'} opponent allowance. This market compares G/F/C for both teams using the gamebook groups; G and F are not assigned a finer role.`};
    });
  }
  function selectMarketEvidence(current,archive,state,basis='auto'){
    const minimum=state.requiredPlayerGames||MIN_GAMES;
    if(current.pick&&current.pick.stats.gp<minimum){
      const eligible=(current.ranked||[]).filter(p=>p.stats.gp>=minimum);
      current={...current,pick:eligible.find(p=>p.finalized)||eligible[0]||null,reason:`Needs ${minimum} current-season player appearances`};
    }
    const usable=state.ready&&!!current.pick;
    if(basis==='archive')return archive?{...archive,isArchive:true,readiness:state}:{...current,pick:null,reason:'Verified prior-season evidence unavailable',isArchive:false,readiness:state};
    if(usable)return {...current,isArchive:false,readiness:state};
    if(basis==='auto'&&archive)return {...archive,isArchive:true,readiness:state,fallbackReason:state.ready?current.reason:state.reason};
    return {...current,pick:null,isArchive:false,readiness:state,reason:state.ready?current.reason:state.reason};
  }
  return {MARKETS,LABELS,WEIGHTS,MIN_GAMES,SELECTION_POLICY,FIRST_TARGETS,correlation,positionGroup,shootingRow,summarize,sample,lineDecision,seasonDecision,rankTeam,rankPositionVariants,selectMarketEvidence,applySelectionPolicy,build};
});
