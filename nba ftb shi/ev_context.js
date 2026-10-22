/* Source-bound descriptive matchup ranks. Never predicts, selects bets or writes. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVContext=api;})(typeof window==='object'?window:this,function(){
 'use strict';
 const VERSION='ev-context-v2',POSITIONS=['PG','SG','SF','PF','C'],MARKETS=['points','threes','assists','rebounds'];
 const TEAMS='ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS'.split(' ');
 // Descriptive display sufficiency, not a forecast-confidence or betting eligibility rule.
 const RANK_POLICY=Object.freeze({minimumGames:20,minimumCoverage:.9,minimumTeams:20,totalTeams:30});
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
  const opening=supplement?.openingEvidence&&supplement.meta?.parentEvidenceContentHash===data.meta.evidenceContentHash&&supplement.openingEvidence.meta?.parentEvidenceContentHash===data.meta.evidenceContentHash?supplement.openingEvidence:null;
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
   return {game:{id:g.id,date:g.date,season:data.meta.season,home:g.home,away:g.away,phase:g.phase,source:g.source,sourceHash:g.sourceHash,firstScores:g.firstScores?JSON.parse(JSON.stringify(g.firstScores)):null,opening:opening?.games?.[g.id]?JSON.parse(JSON.stringify(opening.games[g.id])):null},sides};
  });
  return {season:data.meta.season,evidenceHash:data.meta.evidenceContentHash||null,roleEvidenceHash:supplement?.roleEvidenceMeta&&supplement.roleEvidenceMeta.parentEvidenceContentHash===data.meta.evidenceContentHash?supplement.roleEvidenceMeta.contentHash:null,games};
 }
 function empty(){return {expectedGames:0,games:0,appearances:0,total:0,seconds:0,missingRows:0,unassignedAppearances:0,unassignedSeconds:0,from:null,through:null,gameIds:[],sources:[],largestGameShare:null};}
 function summarize(games,defender,role,market,baseline=false){
  const out=empty();let largest=0;
  for(const {game:g,sides} of games)for(const team of [g.home,g.away]){
   if(baseline?team===defender:team!==defender)continue;
   out.expectedGames++;const opposing=team===g.home?g.away:g.home,rows=sides[opposing],eligible=role.resolution==='five-position'?rows.filter(r=>r.player.starter===true):rows;
   let found=false,gameTotal=0;
   for(const r of eligible){
    const p=r.player,position=role.resolution==='five-position'?r.role?.position:group(p.officialPosition||p.rawPosition);
    if(!position){out.unassignedAppearances++;if(finite(p.minutesSeconds))out.unassignedSeconds+=p.minutesSeconds;continue;}
    if(position!==role.position)continue;
    if(!authority(g,p)||!finite(p.minutesSeconds)||p.minutesSeconds===0||metric(p,market)===null){out.missingRows++;continue;}
    found=true;out.appearances++;out.total+=metric(p,market);gameTotal+=metric(p,market);out.seconds+=p.minutesSeconds;
   }
   if(found){out.games++;out.from=out.from||g.date;out.through=g.date;largest=Math.max(largest,gameTotal);if(!baseline)out.gameIds.push(g.id+'|'+team);if(!baseline)out.sources.push({gameId:g.id,date:g.date,url:g.source,sourceHash:g.sourceHash});}
  }
  out.per48=out.seconds>0?out.total*2880/out.seconds:null;
  out.largestGameShare=out.total>0?largest/out.total:null;
  return out;
 }
 function rankEntries(entries,team){
  const peers=entries.map(e=>({...e,coverage:e.expectedGames?e.games/e.expectedGames:0,eligible:e.games>=RANK_POLICY.minimumGames&&e.games/e.expectedGames>=RANK_POLICY.minimumCoverage&&Number.isFinite(e.rate)&&e.denominator>0}));
  const qualified=peers.filter(e=>e.eligible),target=peers.find(e=>e.team===team),out={policy:RANK_POLICY,eligibleTeams:qualified.length,totalTeams:30,entries:peers,mostRank:null,fewestRank:null,tiedTeams:null,status:'unavailable'};
  if(!target?.eligible){out.reason=`Rank requires ${RANK_POLICY.minimumGames} matched team-games and ${100*RANK_POLICY.minimumCoverage}% game coverage for this cohort.`;return out;}
  if(qualified.length<RANK_POLICY.minimumTeams){out.reason=`Only ${qualified.length} teams qualify; ranks require at least ${RANK_POLICY.minimumTeams}.`;return out;}
  const compare=e=>e.numerator*target.denominator-target.numerator*e.denominator;
  return {...out,status:'ranked',mostRank:1+qualified.filter(e=>compare(e)>0).length,fewestRank:1+qualified.filter(e=>compare(e)<0).length,tiedTeams:qualified.filter(e=>compare(e)===0).length};
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
  const sources=[prepare(archive,supplement),current?.meta?.season!==archive?.meta?.season?prepare(current,current?.parlay):null].filter(Boolean),cache=new Map(),historyCache=new Map(),leagueCache=new Map(),openingCache=new Map();
  function prior(s,before){return s.games.filter(r=>r.game.phase==='regular-season'&&r.game.date<before);}
  function history(id,team,before){const k=id+'|'+team+'|'+before;if(!historyCache.has(k))historyCache.set(k,sources.flatMap(s=>prior(s,before).flatMap(r=>(r.sides[team]||[]).filter(x=>String(x.player.id)===String(id)&&authority(r.game,x.player)).map(x=>({...x,game:r.game})))).sort((a,b)=>a.game.date.localeCompare(b.game.date)||String(a.game.id).localeCompare(String(b.game.id))));return historyCache.get(k);}
  function league(s,before,role,market){
   const k=[s.evidenceHash,before,role.resolution,role.position,market].join('|');
   if(!leagueCache.has(k))leagueCache.set(k,TEAMS.map(team=>{const a=summarize(prior(s,before),team,role,market);return {team,numerator:a.total,denominator:a.seconds,rate:a.per48,games:a.games,expectedGames:a.expectedGames,from:a.from,through:a.through};}));
   return leagueCache.get(k);
  }
  function profile(s,before,opponent,role,market){
   const k=[VERSION,s.evidenceHash,before,opponent,role.resolution,role.position,market].join('|');
   if(!cache.has(k)){const games=prior(s,before),opposing=summarize(games,opponent,role,market),baseline=summarize(games,opponent,role,market,true);cache.set(k,freeze({id:k,opposing,baseline,ranking:rankEntries(league(s,before,role,market),opponent),baselineRule:'Same season/cohort; all prior regular-season defending-team observations except '+opponent}));}
   return cache.get(k);
  }
  function playerSample(hist,market){
   const rows=hist.filter(r=>finite(r.player.minutesSeconds)&&r.player.minutesSeconds>0&&metric(r.player,market)!==null),season=rows.at(-1)?.game.season,selected=rows.filter(r=>r.game.season===season);
   if(!selected.length)return null;const seconds=selected.reduce((s,r)=>s+r.player.minutesSeconds,0),total=selected.reduce((s,r)=>s+metric(r.player,market),0);
   return {season,n:selected.length,total,average:total/selected.length,minutes:seconds/60/selected.length,from:selected[0].game.date,through:selected.at(-1).game.date,interpretation:'Latest available season, same-team played appearances; descriptive, not a minutes forecast.'};
  }
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
    playerSample:playerSample(hist,q.market),historicalTarget:historicalTarget(f,q),limitations:[],mainConcern:'Historical minutes are a proxy; tonight’s workload is not forecast.'};
   if(!currentRole)packet.limitations.push('Current exact role unconfirmed; historical role/group used.');
   if(row.provisional)packet.limitations.push('Participation or role remains provisional.');
   if(q.side==='at-least')packet.limitations.push('Average allowance does not establish this ladder’s tail probability.');
   packet.limitations.push('Observed allowance is unadjusted for pace, schedule quality and actual defensive assignments.');
   packet.limitations.push('Historical positions are reconstructed from retained source records; they do not establish that role evidence was captured before those games.');
   if(!source||!role.position){packet.reason=!source?'No prior opponent context in accepted seasons':'Position evidence unavailable';packet.mainConcern=packet.reason;return packet;}
   packet.dataset={season:source.season,evidenceHash:source.evidenceHash,roleEvidenceHash:source.roleEvidenceHash,priorSeason:source.season<fixture.season};
   if(packet.dataset.priorSeason)packet.limitations.unshift('Prior-season opponent profile; roster and rotation transfer is uncertain.');
   packet.profile=profile(source,fixture.date,opponent,role,q.market);
   if(role.resolution==='five-position'&&(packet.profile.opposing.per48===null||!(packet.profile.baseline.per48>0))){
    const fallback={...role,requestedPosition:role.position,position:group(role.position),resolution:'broad',cohort:'Played appearances with known G/F/C',source:'Five-position sample unavailable; broader historical G/F/C comparison shown'};
    const p=profile(source,fixture.date,opponent,fallback,q.market);if(p.opposing.per48!==null&&p.baseline.per48>0){packet.role=fallback;packet.profile=p;packet.limitations.unshift('Exact-position profile is unavailable; the displayed broader group is not an exact-position comparison.');packet.mainConcern='Exact-position evidence is unavailable; only a broader role comparison is shown.';}
   }
   const older=sources.filter(s=>s.season<source.season&&prior(s,fixture.date).some(r=>[r.game.home,r.game.away].includes(opponent))).at(-1);
   if(older){let olderRole=role,olderProfile=profile(older,fixture.date,opponent,olderRole,q.market);
    if(olderRole.resolution==='five-position'&&olderProfile.opposing.per48===null){olderRole=packet.role;olderProfile=profile(older,fixture.date,opponent,olderRole,q.market);}
    packet.priorSeason={season:older.season,role:olderRole,profile:olderProfile,interpretation:'Separate prior-season research; each season labels its accepted cohort. Never pooled into current-season ranks or forecasts.'};
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
  function opening(fixture,opponent){
   if(!fixture||![fixture.home,fixture.away].includes(opponent))return {status:'unavailable',reason:'Opening fixture identity unavailable'};
   function seasonProfile(s){
    const k=s.evidenceHash+'|'+fixture.date+'|opening';
    if(!openingCache.has(k)){
     const all=Object.fromEntries(TEAMS.map(t=>[t,{expectedGames:0,games:0,from:null,through:null,other:0,counts:Object.fromEntries(POSITIONS.map(p=>[p,0]))}]));
     for(const {game:g,sides} of prior(s,fixture.date))for(const defending of [g.home,g.away]){
      if(!all[defending])continue;const a=all[defending];a.expectedGames++;
      const offensive=defending===g.home?g.away:g.home,rows=sides[offensive],starters=rows.filter(r=>r.player.starter===true),o=g.opening,e=o?.firstScores?.[offensive];
      const scorer=rows.find(r=>String(r.player.id)===String(e?.id));
      if(starters.length!==5||starters.some(r=>!r.role)||!/^https:\/\/(?:statsdmz|stats)\.nba\.com\/pdfs\//.test(g.source||'')||o?.source!==g.source||o?.sourceHash!==g.sourceHash||!e||e.team!==offensive||e.period!==1||![1,2,3].includes(e.points)||!Number.isInteger(e.sequence)||!(e.page>1)||!scorer||!authority(g,scorer.player)||String(g.firstScores?.[offensive]?.id)!==String(e.id))continue;
      a.games++;a.from=a.from||g.date;a.through=g.date;const position=scorer.role?.position;if(position)a.counts[position]++;else a.other++;
     }
     openingCache.set(k,freeze(all));
    }
    const all=openingCache.get(k),a=all[opponent];
    return freeze({season:s.season,evidenceHash:s.evidenceHash,opponent,...a,positions:POSITIONS.map(position=>({position,count:a.counts[position],frequency:a.games?a.counts[position]/a.games:null,ranking:rankEntries(TEAMS.map(team=>({team,numerator:all[team].counts[position],denominator:all[team].games,rate:all[team].games?all[team].counts[position]/all[team].games:null,games:all[team].games,expectedGames:all[team].expectedGames})),opponent)}))});
   }
   const available=sources.filter(s=>prior(s,fixture.date).some(r=>[r.game.home,r.game.away].includes(opponent))),source=available.at(-1);
   if(!source)return {status:'unavailable',reason:'Verified opening-score evidence unavailable'};
   const p=seasonProfile(source);return freeze({status:p.games?'observed':'unavailable',reason:p.games?null:'No accepted opening events with matched starting roles',definition:'Opponent first team score, free throws included; recorded starting position. Bench/other scorers remain separate. Not first game basket or a player probability.',cutoff:fixture.date,profile:p,priorSeason:available.length>1?seasonProfile(available.at(-2)):null});
  }
  return {describe,opening};
 }
 return {VERSION,POSITIONS,MARKETS,TEAMS,RANK_POLICY,create,historicalTarget};
});
