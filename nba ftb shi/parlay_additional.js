/* New descriptive Parlay markets; original three-market rankings remain frozen. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./parlay.js'):root.FTBParlay,typeof module==='object'&&module.exports?require('./lineups.js'):root.FTBLineups);if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBParlayAdditional=api;})(typeof window==='object'?window:this,function(P,L){
 'use strict';
 const VERSION='parlay-assists-rebounds-v1',MARKETS=['assists','rebounds'],MIN_GAMES=5,cache=new WeakMap();
 const valid=(p,m)=>p.played===true&&Number.isInteger(p[m])&&p[m]>=0&&Number.isFinite(p.minutes)&&p.minutes>=0&&(m!=='rebounds'||Number.isInteger(p.offensiveRebounds)&&p.offensiveRebounds>=0&&Number.isInteger(p.defensiveRebounds)&&p.defensiveRebounds>=0&&p.offensiveRebounds+p.defensiveRebounds===p.rebounds);
 function sample(model){
  if(cache.has(model))return cache.get(model);const data={teams:{},players:{}},snap=model.snapshot;
  const role=(p,g)=>{const direct=P.positionGroup(p,model.positionScope);return direct==='unknown'?P.positionGroup({position:g.positionRoles?.[p.id]},model.positionScope):direct;};
  for(const g of snap.games)for(const team of snap.gameTeams[g.id]||[]){
   const t=data.teams[team]||(data.teams[team]={}),opp=team===g.home?g.away:g.home;
   for(const market of MARKETS){
    const a=t[market]||(t[market]={games:0,own:{},allowed:{},total:0,allowedTotal:0,missing:0});
    const played=side=>g.teams[side].players.filter(p=>p.played);
    if(g.boxScoreSource!=='NBA official final box'||[team,opp].some(side=>played(side).some(p=>!valid(p,market)||p.statsSourceHash!==g.sourceHash))){a.missing++;continue;}
    a.games++;
    for(const side of [team,opp])for(const p of played(side)){
     const k=role(p,g),target=side===team?a.own:a.allowed;target[k]=(target[k]||0)+p[market];a[side===team?'total':'allowedTotal']+=p[market];
    }
   }
   for(const p of g.teams[team].players.filter(p=>p.played&&p.statsSourceHash===g.sourceHash)){
    const all=data.players[String(p.id)]||(data.players[String(p.id)]=[]);all.push({...p,team,date:g.date,gameId:g.id,source:g.source,sourceHash:g.sourceHash});
   }
  }
  cache.set(model,data);return data;
 }
 function rank({model,seasonModel,team,opponent,roster=[],eligibility={},excludedIds=[],acrossStints=false,trusted=true,upcoming=false,fixture,confirmedStarters={},now=Date.now()}){
  const scope=sample(model),season=sample(seasonModel||model),excluded=new Set(excludedIds.map(String));
  return MARKETS.map(market=>{
   const own=scope.teams[team]?.[market],allowed=scope.teams[opponent]?.[market],known=(counts,total)=>total>0?1-(counts.unknown||0)/total:null;
   const ownKnown=own?known(own.own,own.total):null,opponentKnown=allowed?known(allowed.allowed,allowed.allowedTotal):null;
   let reason=!trusted?'History verification failed':!opponent?'Select a matchup':!own||!allowed?'No team/opponent history':own.missing||allowed.missing?'Incomplete official credited-stat history':own.games<5||allowed.games<5?'Needs 5 games for each team':!(ownKnown>=.8&&opponentKnown>=.8)?'Needs at least 80% known positional production for both teams':null;
   const audit=[],eligible=[];
   if(!reason)for(const p of roster){
    const source=scope.players[String(p.id)]||[],rows=(acrossStints?source:source.filter(r=>r.team===team));
    const confirmation=confirmedStarters[p.id],confirmed=L.validConfirmation(confirmation,fixture,now)&&confirmation.team===team;
    const role={...model.snapshot.players[p.id],...p,position:confirmed?confirmation.position:model.snapshot.players[p.id]?.position,rawPosition:confirmed?confirmation.position:model.snapshot.players[p.id]?.rawPosition||p.rawPosition};
    const group=P.positionGroup(role,model.positionScope),available=eligibility[p.id]||{provisional:upcoming,reason:'Availability unconfirmed'};
    const why=excluded.has(String(p.id))?'Excluded scenario':available.excluded?available.reason:group==='unknown'?'Position unavailable':rows.length<MIN_GAMES?'Needs 5 complete appearances':rows.some(r=>!valid(r,market))?'Missing credited-stat history':null;
    if(why){audit.push({id:String(p.id),name:p.name,reason:why});continue;}
    const total=rows.reduce((n,r)=>n+r[market],0),minutes=rows.reduce((n,r)=>n+r.minutes,0);
    if(!(minutes>0&&total>0)){audit.push({id:String(p.id),name:p.name,reason:'No positive recorded exposure/production'});continue;}
    const seasonRows=season.players[String(p.id)]||[],average=seasonRows.length&&seasonRows.every(r=>valid(r,market))?seasonRows.reduce((n,r)=>n+r[market],0)/seasonRows.length:null,threshold=Number.isFinite(average)?Math.ceil(average-1e-10):null,hits=threshold===null?null:rows.filter(r=>r[market]>=threshold).length;
    eligible.push({id:String(p.id),name:p.name,team,group,rows,gp:rows.length,average:total/rows.length,mpg:minutes/rows.length,rate:total/minutes,historyTeams:[...new Set(rows.map(r=>r.team))],through:rows.at(-1).date,
     oreb:market==='rebounds'?rows.reduce((n,r)=>n+r.offensiveRebounds,0)/rows.length:null,dreb:market==='rebounds'?rows.reduce((n,r)=>n+r.defensiveRebounds,0)/rows.length:null,
     seasonTarget:{average,threshold,n:rows.length,hits,rate:hits===null?null:hits/rows.length},
     provisional:upcoming&&available.provisional,confirmation:confirmed?confirmation:null,availability:available.reason});
   }
   const maxMinutes=Math.max(1,...eligible.map(p=>p.mpg)),maxRate=Math.max(.001,...eligible.map(p=>p.rate));
   const ranked=eligible.map(p=>{const offense=(own.own[p.group]||0)/own.total,defense=(allowed.allowed[p.group]||0)/allowed.allowedTotal,opportunity=.5*p.mpg/maxMinutes+.5*p.rate/maxRate;
    return {...p,components:{offense,defense,opportunity},score:100*(offense+defense+opportunity)/3};}).sort((a,b)=>b.score-a.score||b.gp-a.gp||a.name.localeCompare(b.name));
   return {market,team,opponent,ranked,audit,pick:ranked.find(p=>!p.provisional)||ranked[0]||null,reason:reason||(ranked.length?null:'No eligible player with 5 complete appearances'),ownKnown,opponentKnown,teamGames:own?.games||0,opponentGames:allowed?.games||0,evidenceSeason:model.season,evidenceThrough:model.through,positionScope:model.positionScope,modelVersion:VERSION};
  });
 }
 function rankPositionVariants({specific,broad},args,resolution='auto'){
  const fine=resolution==='broad'?null:rank({...args,model:specific}),coarse=resolution==='specific'?null:rank({...args,model:broad});
  if(resolution==='specific')return fine;if(resolution==='broad')return coarse;
  return fine.map((s,i)=>s.ownKnown>=.8&&s.opponentKnown>=.8&&!s.audit.some(a=>a.reason==='Position unavailable')?s:{...coarse[i],positionFallbackReason:'Specific roles incomplete; compares recorded G/F/C for both teams.'});
 }
 function selectEvidence(current,archive,basis='auto'){if(basis==='archive')return archive?{...archive,isArchive:true}:{...current,pick:null,reason:'Prior-season evidence unavailable'};if(current.pick)return {...current,isArchive:false};if(basis==='auto'&&archive)return {...archive,isArchive:true,fallbackReason:current.reason};return {...current,isArchive:false};}
 function receipt(slots){return {modelVersion:VERSION,prospectiveEvaluationEligible:false,evidenceStatus:'Additional descriptive export; excluded from the original three-market prospective cohort',minimumAppearances:MIN_GAMES,weights:{offense:1/3,defense:1/3,opportunity:1/3},interpretation:'Descriptive ranks, not probabilities or combined-parlay EV',selections:slots.map(s=>({...s,ranked:undefined,pick:s.pick?{...s.pick,rows:s.pick.rows.map(r=>({gameId:r.gameId,date:r.date,team:r.team,value:r[s.market],minutes:r.minutes,offensiveRebounds:r.offensiveRebounds,defensiveRebounds:r.defensiveRebounds,source:r.source,sourceHash:r.sourceHash}))}:null}))};}
 return {VERSION,MARKETS,MIN_GAMES,valid,sample,rank,rankPositionVariants,selectEvidence,receipt};
});
