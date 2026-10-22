/* Source-bound descriptive context. Never predicts, ranks, places bets or writes. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVContext=api;})(typeof window==='object'?window:this,function(){
 'use strict';
 const VERSION='ev-context-v1',POSITIONS=['PG','SG','SF','PF','C'],MARKETS=['points','threes','assists','rebounds'];
 const finite=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0,hash=v=>/^[a-f0-9]{64}$/.test(v||''),key=m=>m==='threes'?'threeMade':m;
 const group=v=>['PG','SG','G'].includes(v)?'G':['SF','PF','F'].includes(v)?'F':v==='C'?'C':null;
 const freeze=v=>{if(v&&typeof v==='object'&&!Object.isFrozen(v)){Object.values(v).forEach(freeze);Object.freeze(v);}return v;};
 const authority=(g,p)=>hash(g.sourceHash)&&p.statsSourceHash===g.sourceHash&&/^https:\/\/(?:[a-z0-9-]+\.)*nba\.com\/.+\.pdf(?:\?.*)?$/i.test(p.statsSource||'');
 const metric=(p,m)=>{const v=p[key(m)];return Number.isInteger(v)&&v>=0&&(m!=='rebounds'||Number.isInteger(p.offensiveRebounds)&&Number.isInteger(p.defensiveRebounds)&&p.offensiveRebounds>=0&&p.defensiveRebounds>=0&&p.offensiveRebounds+p.defensiveRebounds===v)?v:null;};
 function prepare(data,supplement){
  if(!data?.meta?.season||!Array.isArray(data.games))return null;
  const evidence=supplement?.meta?.parentEvidenceContentHash&&supplement.meta.parentEvidenceContentHash===data.meta.evidenceContentHash?supplement.datedRoleEvidence||[]:
   Array.isArray(data.roleEvidence)?data.roleEvidence:Array.isArray(data.datedRoleEvidence)&&data.datedRoleEvidence.length?data.datedRoleEvidence:data.games.flatMap(g=>(g.roleEvidence||[]).map(r=>({...r,gameId:g.id,gamebookSourceHash:r.gamebookSourceHash||g.sourceHash})));
  const roles=new Map(),seen=new Set();
  for(const r of evidence){const k=r.gameId+'|'+r.team;if(!roles.has(k))roles.set(k,[]);roles.get(k).push(r);}
  const games=[...data.games].sort((a,b)=>a.date.localeCompare(b.date)||String(a.id).localeCompare(String(b.id))).map(g=>{
   if(seen.has(String(g.id)))throw Error('Duplicate context fixture');seen.add(String(g.id));
   const sides={};
   for(const team of [g.home,g.away]){
    const ps=g.teams?.[team]?.players;if(!Array.isArray(ps))throw Error('Missing context box');
    const ids=new Set();for(const p of ps){if(!p.id||ids.has(String(p.id)))throw Error('Duplicate context player');ids.add(String(p.id));}
    const starters=ps.filter(p=>p.played===true&&p.starter===true),rs=roles.get(g.id+'|'+team)||[];
    const valid=starters.length===5&&rs.length===5&&new Set(rs.map(r=>String(r.playerId))).size===5&&new Set(rs.map(r=>r.position)).size===5&&rs.every(r=>POSITIONS.includes(r.position)&&r.effectiveGameDate===g.date&&r.gamebookSourceHash===g.sourceHash&&hash(r.sourceHash)&&r.source==='https://stats.nba.com/js/data/leaders/00_daily_lineups_'+g.date.replaceAll('-','')+'.json'&&starters.some(p=>String(p.id)===String(r.playerId)));
    const byId=new Map(valid?rs.map(r=>[String(r.playerId),r]):[]);
    sides[team]=ps.filter(p=>p.played===true).map(p=>({player:{...p},role:byId.has(String(p.id))?{...byId.get(String(p.id))}:null}));
   }
   return {game:{id:g.id,date:g.date,home:g.home,away:g.away,phase:g.phase,source:g.source,sourceHash:g.sourceHash},sides};
  });
  return {season:data.meta.season,evidenceHash:data.meta.evidenceContentHash||null,roleEvidenceHash:supplement?.roleEvidenceMeta&&supplement.roleEvidenceMeta.parentEvidenceContentHash===data.meta.evidenceContentHash?supplement.roleEvidenceMeta.contentHash:null,games};
 }
 function empty(){return {expectedGames:0,games:0,appearances:0,total:0,seconds:0,missingRows:0,unassignedAppearances:0,unassignedSeconds:0,through:null,gameIds:[],sources:[]};}
 function summarize(games,defender,role,market,baseline=false){
  const out=empty();
  for(const {game:g,sides} of games)for(const team of [g.home,g.away]){
   if(baseline?team===defender:team!==defender)continue;
   out.expectedGames++;const opposing=team===g.home?g.away:g.home,rows=sides[opposing],eligible=role.resolution==='five-position'?rows.filter(r=>r.player.starter===true):rows;
   let found=false;
   for(const r of eligible){
    const p=r.player,position=role.resolution==='five-position'?r.role?.position:group(p.officialPosition||p.rawPosition);
    if(!position){out.unassignedAppearances++;if(finite(p.minutesSeconds))out.unassignedSeconds+=p.minutesSeconds;continue;}
    if(position!==role.position)continue;
    if(!authority(g,p)||!finite(p.minutesSeconds)||metric(p,market)===null){out.missingRows++;continue;}
    found=true;out.appearances++;out.total+=metric(p,market);out.seconds+=p.minutesSeconds;
   }
   if(found){out.games++;out.through=g.date;if(!baseline)out.gameIds.push(g.id+'|'+team);if(!baseline)out.sources.push({gameId:g.id,date:g.date,url:g.source,sourceHash:g.sourceHash});}
  }
  out.per48=out.seconds>0?out.total*2880/out.seconds:null;
  return out;
 }
 function historicalTarget(f,q){
  const h=f.histograms?.[q.market];if(!h||!Number.isFinite(q.line))return null;
  let wins=0,losses=0,pushes=0;for(const [v,n] of Object.entries(h)){const y=Number(v);if(!Number.isInteger(n)||n<0)return null;
   if(q.side==='at-least')y>=q.line?wins+=n:losses+=n;else if(y===q.line)pushes+=n;else if(q.side==='over'?y>q.line:y<q.line)wins+=n;else losses+=n;
  }
  return {wins,losses,pushes,n:wins+losses+pushes};
 }
 function create({archive,current,supplement,trusted}){
  if(!trusted)return {describe:()=>({version:VERSION,status:'unavailable',reason:'Verified context history unavailable'})};
  const sources=[prepare(archive,supplement),current?.meta?.season!==archive?.meta?.season?prepare(current,current?.parlay):null].filter(Boolean),cache=new Map(),historyCache=new Map();
  function prior(s,before){return s.games.filter(r=>r.game.phase==='regular-season'&&r.game.date<before);}
  function history(id,team,before){const k=id+'|'+team+'|'+before;if(!historyCache.has(k))historyCache.set(k,sources.flatMap(s=>prior(s,before).flatMap(r=>(r.sides[team]||[]).filter(x=>String(x.player.id)===String(id)&&authority(r.game,x.player)).map(x=>({...x,game:r.game})))).sort((a,b)=>a.game.date.localeCompare(b.game.date)||String(a.game.id).localeCompare(String(b.game.id))));return historyCache.get(k);}
  function describe(row,fixture,view={},config={}){
   const q=row.quote,f=row.features||{};if(!MARKETS.includes(q?.market))return {version:VERSION,status:'unavailable',reason:'FTB uses separate opening research; no count-prop matchup estimate'};
   if(!fixture||![fixture.home,fixture.away].includes(q.team))return {version:VERSION,status:'unavailable',reason:'Context fixture identity unavailable'};
   const opponent=fixture.home===q.team?fixture.away:fixture.home,hist=history(q.playerId,q.team,fixture.date),last=hist.at(-1);
   const currentRole=POSITIONS.includes(view.record?.position)?view.record.position:null;
   const exact=currentRole||(last?.player.starter&&last?.role?.position),broad=group(f.role||last?.player.officialPosition||last?.player.rawPosition);
   const role=exact?{position:exact,resolution:'five-position',cohort:'Recorded starters',source:currentRole?view.label:'Latest historical starting role',sourceUrl:currentRole?view.record.source:last.role.source,capturedAt:currentRole?view.record.capturedAt:last.role.capturedAt,effectiveDate:currentRole?fixture.date:last.game.date}:
    {position:broad,resolution:'broad',cohort:'Played appearances with known G/F/C',source:'Historical G/F/C group; exact current position unavailable'};
   const source=[...sources].reverse().find(s=>prior(s,fixture.date).some(r=>[r.game.home,r.game.away].includes(opponent)));
   const packet={version:VERSION,status:'unavailable',market:q.market,team:q.team,opponent,cutoff:fixture.date,role,modelOpponent:{group:f.role||null,power:Number.isFinite(config.defensePower)?config.defensePower:null,alreadyIncluded:config.defensePower>0},
    opportunity:{historicalMinutes:finite(f.minutes)?f.minutes:null,appearances:f.n??null,recentStarterRate:finite(f.recentStarterRate)?f.recentStarterRate:null,through:f.through||null,lineup:view.label||'Starter status unconfirmed',roleConfirmed:view.teamStatus==='confirmed'&&!!view.record,availability:row.availability||'Availability unconfirmed',provisional:!!row.provisional},
    historicalTarget:historicalTarget(f,q),limitations:[],mainConcern:'Historical minutes are a proxy; tonight’s workload is not forecast.'};
   if(!currentRole)packet.limitations.push('Current exact role unconfirmed; historical role/group used.');
   if(row.provisional)packet.limitations.push('Participation or role remains provisional.');
   if(q.side==='at-least')packet.limitations.push('Average allowance does not establish this ladder’s tail probability.');
   packet.limitations.push('Observed allowance is unadjusted for pace, schedule quality and actual defensive assignments.');
   if(!source||!role.position){packet.reason=!source?'No prior opponent context in accepted seasons':'Position evidence unavailable';packet.mainConcern=packet.reason;return packet;}
   packet.dataset={season:source.season,evidenceHash:source.evidenceHash,roleEvidenceHash:source.roleEvidenceHash,priorSeason:source.season<fixture.season};
   if(packet.dataset.priorSeason)packet.limitations.unshift('Prior-season opponent profile; roster and rotation transfer is uncertain.');
   function profile(r){const k=[source.evidenceHash,fixture.date,opponent,r.resolution,r.position,q.market].join('|');if(!cache.has(k)){const games=prior(source,fixture.date),opposing=summarize(games,opponent,r,q.market),baseline=summarize(games,opponent,r,q.market,true);cache.set(k,freeze({id:k,opposing,baseline,baselineRule:'Same season/cohort; all prior regular-season defending-team observations except '+opponent}));}return cache.get(k);}
   packet.profile=profile(role);
   if(role.resolution==='five-position'&&(packet.profile.opposing.per48===null||!(packet.profile.baseline.per48>0))){
    const fallback={...role,requestedPosition:role.position,position:group(role.position),resolution:'broad',cohort:'Played appearances with known G/F/C',source:'Five-position sample unavailable; broader historical G/F/C comparison shown'};
    const p=profile(fallback);if(p.opposing.per48!==null&&p.baseline.per48>0){packet.role=fallback;packet.profile=p;packet.limitations.unshift('Exact-position profile is unavailable; the displayed broader group is not an exact-position comparison.');packet.mainConcern='Exact-position evidence is unavailable; only a broader role comparison is shown.';}
   }
   const a=packet.profile.opposing,b=packet.profile.baseline;
   if(a.per48!==null&&b.per48>0){packet.status='observed';packet.ratio=a.per48/b.per48;packet.direction=packet.ratio>1?'Higher observed allowance':packet.ratio<1?'Lower observed allowance':'At comparison rate';}
   else packet.reason='Matched role production/minute comparison unavailable';
   if(a.missingRows||a.unassignedAppearances||a.games<a.expectedGames)packet.limitations.push('Role or paired-stat coverage is incomplete; excluded observations are reported.');
   if(packet.status!=='observed')packet.mainConcern=packet.reason;
   else if(packet.role.requestedPosition)packet.mainConcern='Exact-position evidence is unavailable; only a broader role comparison is shown.';
   else if(row.provisional)packet.mainConcern='Availability or current role is provisional; check the lineup before using the estimate.';
   else if(q.side==='at-least')packet.mainConcern='This ladder requires tail accuracy; a favorable role average cannot confirm it.';
   else if(!currentRole)packet.mainConcern='Current exact role is unconfirmed; the comparison uses historical role evidence.';
   else if(packet.dataset.priorSeason)packet.mainConcern='Opponent evidence is from the prior season; today’s personnel may differ.';
   if(currentRole&&f.role&&group(currentRole)!==f.role){packet.mainConcern='Current lineup role differs from the model’s historical group; role transfer is uncertain.';packet.limitations.unshift(packet.mainConcern);}
   if(!packet.dataset.priorSeason&&a.games<10)packet.mainConcern=`Current-season opponent sample: ${a.games} team-game${a.games===1?'':'s'}. `+packet.mainConcern;
   return freeze(packet);
  }
  return {describe};
 }
 return {VERSION,POSITIONS,create,historicalTarget};
});
