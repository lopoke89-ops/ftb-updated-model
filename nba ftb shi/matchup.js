/* Descriptive positional comparisons. Never supplies probabilities or Parlay weights. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBMatchup=api;})(typeof window==='object'?window:globalThis,function(){
  'use strict';
  const VERSION='matchup-evidence-v2';
  const METRICS={points:'Points',threes:'Threes',blocks:'Blocks',rebounds:'Rebounds',offensiveRebounds:'Offensive rebounds',defensiveRebounds:'Defensive rebounds',assists:'Assists',firstTeam:'First Team Basket'};
  const COUNTS=['fgm','fga','twoMade','twoAttempted','threeMade','threeAttempted','ftm','fta'];
  const ALL=[...Object.keys(METRICS),...COUNTS];
  const POSITIONS={broad:['G','F','C','unknown'],strict:['PG','SG','SF','PF','C','unknown']};
  const PHASES=['all','regular-season','playoffs','regular-and-playoffs','play-in','nba-cup-final'];
  const finite=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
  const phaseOK=(g,phase)=>phase==='all'||(phase==='regular-and-playoffs'?['regular-season','playoffs'].includes(g.phase):g.phase===phase);
  function position(p,basis='broad'){
    // The role belongs to this appearance. Current rosters and season-wide role maps are deliberately absent.
    const raw=String(p?.officialPosition||p?.rawPosition||'').trim().toUpperCase();
    const role=({'POINT GUARD':'PG','SHOOTING GUARD':'SG','SMALL FORWARD':'SF','POWER FORWARD':'PF',CENTER:'C',GUARD:'G',FORWARD:'F'})[raw]||raw;
    if(basis==='strict'&&POSITIONS.strict.includes(p?.verifiedFivePosition)&&p.verifiedFivePosition!=='unknown')return p.verifiedFivePosition;
    if(basis==='strict')return POSITIONS.strict.includes(role)?role:'unknown';
    return ['PG','SG','G'].includes(role)?'G':['SF','PF','F'].includes(role)?'F':role==='C'?'C':'unknown';
  }
  function withHistoricalRoles(data){
    if(!data?.games)return data;
    const evidence=Array.isArray(data.roleEvidence)?data.roleEvidence:data.games.flatMap(g=>(g.roleEvidence||[]).map(r=>({...r,gameId:g.id,gamebookSourceHash:g.sourceHash})));
    if(!evidence.length)return data;
    const groups=new Map();
    for(const r of evidence){const key=r.gameId+'|'+r.team;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
    return {...data,games:data.games.map(g=>({...g,teams:Object.fromEntries(Object.entries(g.teams).map(([team,box])=>{
      const roles=groups.get(g.id+'|'+team)||[],starters=box.players.filter(p=>p.played&&p.starter),hash=box.players.find(p=>p.played)?.statsSourceHash;
      const valid=roles.length===5&&new Set(roles.map(r=>r.playerId)).size===5&&new Set(roles.map(r=>r.position)).size===5&&roles.every(r=>['PG','SG','SF','PF','C'].includes(r.position)&&r.effectiveGameDate===g.date&&r.gamebookSourceHash===hash&&/^[a-f0-9]{64}$/.test(r.sourceHash||'')&&r.source==='https://stats.nba.com/js/data/leaders/00_daily_lineups_'+g.date.replaceAll('-','')+'.json'&&starters.some(p=>String(p.id)===String(r.playerId)));
      const byId=new Map(valid?roles.map(r=>[String(r.playerId),r.position]):[]);
      return [team,{...box,players:box.players.map(p=>byId.has(String(p.id))?{...p,verifiedFivePosition:byId.get(String(p.id))}:p)}];
    }))}))};
  }
  function validateOptions(o){
    if(!PHASES.includes(o.phase||'all'))throw Error('Unsupported competition filter');
    if(!['0','5','10','20'].includes(String(o.window||0)))throw Error('Unsupported statistics period');
    if(!['review','pregame','upcoming'].includes(o.mode))throw Error('Unsupported analysis view');
    if(!/^\d{4}-\d{2}-\d{2}$/.test(o.date||''))throw Error('Choose a valid game date');
    if(!['broad','strict'].includes(o.positions||'broad'))throw Error('Unsupported position grouping');
    if(!['auto','current','archive'].includes(o.basis||'auto'))throw Error('Unsupported statistics history');
  }
  function eligibleGames(data,o){
    if(!data?.meta?.season||!Array.isArray(data.games))throw Error('Verified season records unavailable');
    const seen=new Set();
    return data.games.filter(g=>{
      if(seen.has(String(g.id)))throw Error('Duplicate game ID in season evidence: '+g.id);seen.add(String(g.id));
      if(!g.id||!g.date||!g.home||!g.away||g.home===g.away)throw Error('Invalid fixture in season evidence');
      return (o.mode==='review'?g.date<=(data.meta.asOfDate||''):g.date<o.date)&&phaseOK(g,o.phase||'all');
    }).sort((a,b)=>a.date.localeCompare(b.date)||String(a.id).localeCompare(String(b.id)));
  }
  function teamGames(games,team,opponent,o){
    const selected=games.filter(g=>(g.home===team||g.away===team)&&(!o.headToHead||(g.home===team?g.away:g.home)===opponent));
    return Number(o.window)?selected.slice(-Number(o.window)):selected;
  }
  function emptySeries(){return {games:0,appearances:0,missing:0,missingMinutes:0,seconds:0,total:0,knownTotal:0,buckets:{}};}
  function emptyBucket(){return {total:0,knownTotal:0,appearances:0,missing:0,missingMinutes:0,seconds:0,games:0};}
  function authority(p){return /^https:\/\/(?:[a-z0-9-]+\.)*nba\.com\/.+\.pdf(?:\?.*)?$/i.test(p.statsSource||'')&&/^[a-f0-9]{64}$/i.test(p.statsSourceHash||'');}
  function playedBox(g,team){
    const rows=g.teams?.[team]?.players;
    if(!Array.isArray(rows)||!rows.length)throw Error(`Missing box score for ${team} in ${g.id}`);
    const ids=new Set();
    for(const p of rows){if(!p.id||ids.has(String(p.id)))throw Error(`Duplicate or missing player ID in ${g.id} ${team}`);ids.add(String(p.id));if(typeof p.played!=='boolean')throw Error(`Unknown participation in ${g.id} ${team}`);}
    const played=rows.filter(p=>p.played);
    if(!played.length)throw Error(`No verified appearances for ${team} in ${g.id}`);
    return played;
  }
  function accumulate(series,players,metric,basis,firstScore){
    series.games++;
    const seen=new Set();
    for(const p of players){
      const pos=position(p,basis),b=series.buckets[pos]||(series.buckets[pos]=emptyBucket());
      if(!seen.has(pos)){b.games++;seen.add(pos);}b.appearances++;series.appearances++;
      let value=metric==='firstTeam'?(firstScore===null?null:(String(firstScore.id)===String(p.id)?1:0)):metric==='threes'?p.threeMade:p[metric];
      if(metric==='twoMade')value=finite(p.fgm)&&finite(p.threeMade)?p.fgm-p.threeMade:null;
      if(metric==='twoAttempted')value=finite(p.fga)&&finite(p.threeAttempted)?p.fga-p.threeAttempted:null;
      // Compact conversion counts always use the same valid observations on both sides.
      const pair=({fgm:'fga',fga:'fgm',threeMade:'threeAttempted',threeAttempted:'threeMade',ftm:'fta',fta:'ftm'})[metric];
      if(pair&&!finite(p[pair]))value=null;
      const valid=authority(p)&&finite(value);
      if(valid){b.knownTotal+=value;series.knownTotal+=value;}else{b.missing++;series.missing++;}
      const seconds=p.minutesSeconds;
      if(!authority(p)||!finite(seconds)){b.missingMinutes++;series.missingMinutes++;}
      else{b.seconds+=seconds;series.seconds+=seconds;}
    }
    for(const b of Object.values(series.buckets))b.total=b.missing?null:b.knownTotal;
    series.total=series.missing?null:series.knownTotal;
  }
  function firstScore(g,team,target,players){
    const scores=target==='field-goals'?g.firstFieldGoals:g.firstScores,s=scores?.[team];
    return s&&players.some(p=>String(p.id)===String(s.id))?s:null;
  }
  function eventHistory(games,team,o,opposing=false){
    const features=['assistedMakes','blockedAttempts','distancedAttempts'];
    const result={expected:games.length,fullyVerified:0,partial:0,unavailable:0,features:Object.fromEntries(features.map(k=>[k,{gameIds:[],through:null,buckets:{}}])),opening:{gameIds:[],firstAttemptMade:0,freeThrowScores:0,andOneAwarded:0,andOneAttempted:0,andOneMade:0}};
    for(const g of games){
      const r=o.playByPlay?.games?.[g.id],hash=playedBox(g,team).find(authority)?.statsSourceHash;
      if(!r||r.sourceHash!==hash){result.unavailable++;continue;}
      if(r.status==='verified')result.fullyVerified++;else if(r.status==='partial')result.partial++;else result.unavailable++;
      const side=opposing?(g.home===team?g.away:g.home):team,c=r.eventContext?.[side];
      for(const k of features){if(!c?.available?.[k])continue;const f=result.features[k];f.gameIds.push(String(g.id));f.through=g.date;if(c.playerCredits){for(const [pid,v] of Object.entries(c.playerCredits)){const player=g.teams[side].players.find(p=>String(p.id)===pid);const pos=position(player,o.positions);f.buckets[pos]=(f.buckets[pos]||0)+(v[k]||0);}}else for(const [pos,v] of Object.entries(c[o.positions]||{}))f.buckets[pos]=(f.buckets[pos]||0)+v[k];}
      const opening=c?.opening?.[o.firstTarget==='field-goals'?'firstFieldGoal':'firstScore'];
      if(opening){const f=result.opening;f.gameIds.push(String(g.id));f.firstAttemptMade+=Number(opening.firstAttemptMade);f.freeThrowScores+=Number(opening.freeThrow);f.andOneAwarded+=Number(opening.andOneAwarded);f.andOneAttempted+=opening.andOneAttempted;f.andOneMade+=opening.andOneMade;}
    }
    return result;
  }
  function aggregate(games,team,o){
    const own=Object.fromEntries(ALL.map(k=>[k,emptySeries()]));
    const against=Object.fromEntries(ALL.map(k=>[k,emptySeries()]));
    const sources=[],roleCoverage={gamebook:0,datedFallback:0,unknown:0,verifiedFive:0},againstRoleCoverage={gamebook:0,datedFallback:0,unknown:0,verifiedFive:0};
    for(const g of games){
      const opponent=g.home===team?g.away:g.home,ownRows=playedBox(g,team),oppRows=playedBox(g,opponent);
      for(const [players,coverage] of [[ownRows,roleCoverage],[oppRows,againstRoleCoverage]])for(const p of players){coverage[p.officialPosition?'gamebook':p.rawPosition?'datedFallback':'unknown']++;if(p.verifiedFivePosition)coverage.verifiedFive++;}
      sources.push({id:String(g.id),date:g.date,opponent,url:ownRows.find(authority)?.statsSource||null});
      const ownFirst=firstScore(g,team,o.firstTarget,ownRows),oppFirst=firstScore(g,opponent,o.firstTarget,oppRows);
      for(const k of ALL){
        accumulate(own[k],ownRows,k,o.positions,ownFirst);
        // Against means the opposing stat recorder: blocker, rebounder, passer or scorer.
        accumulate(against[k],oppRows,k,o.positions,oppFirst);
      }
    }
    return {openingPathGames:games,openingPaths:o.openingPaths,firstTarget:o.firstTarget,team,games:games.length,gameIds:games.map(g=>String(g.id)),sources,roleCoverage,againstRoleCoverage,events:{own:eventHistory(games,team,o),against:eventHistory(games,team,o,true)},from:games[0]?.date||null,through:games.at(-1)?.date||null,own,against};
  }
  function value(series,pos,rate='per48'){
    const b=series.buckets[pos];
    if(!series.games||!b||b.missing||b.total===null)return null;
    if(rate==='perGame')return b.total/series.games;
    if(rate==='share')return series.total>0?100*b.total/series.total:null;
    if(rate==='per48')return !b.missingMinutes&&b.seconds>0?b.total*2880/b.seconds:null;
    return null;
  }
  function pool(seriesList){
    const s=emptySeries();
    for(const x of seriesList){for(const k of ['games','appearances','missing','missingMinutes','seconds','knownTotal'])s[k]+=x[k];for(const [pos,b] of Object.entries(x.buckets)){const d=s.buckets[pos]||(s.buckets[pos]=emptyBucket());for(const k of ['appearances','missing','missingMinutes','seconds','knownTotal','games'])d[k]+=b[k];}}
    s.total=s.missing?null:s.knownTotal;for(const b of Object.values(s.buckets))b.total=b.missing?null:b.knownTotal;return s;
  }
  function rows(comparison,metric,rate){
    const own=comparison.production.own[metric],against=comparison.allowance.against[metric],reference=comparison.reference[metric];
    return POSITIONS[comparison.positions].map(pos=>{
      const production=value(own,pos,rate),allowance=value(against,pos,rate),baseline=value(reference,pos,rate);
      return {position:pos,production,allowance,baseline,productionAbove:baseline>0&&production!==null?100*(production/baseline-1):null,allowanceAbove:baseline>0&&allowance!==null?100*(allowance/baseline-1):null};
    });
  }
  function shootingRows(comparison){
    const summary=(series,pos)=>Object.fromEntries([['FG','fgm','fga'],['2P','twoMade','twoAttempted'],['3P','threeMade','threeAttempted'],['FT','ftm','fta']].map(([name,m,a])=>{
      const makes=series[m].buckets[pos],attempts=series[a].buckets[pos];
      const valid=!!makes&&!!attempts&&!makes.missing&&!attempts.missing;
      return [name,{made:valid?makes.total:null,attempted:valid?attempts.total:null,percentage:valid&&attempts.total>0?100*makes.total/attempts.total:null,games:series[a].games,appearances:attempts?.appearances||0}];
    }));
    return POSITIONS[comparison.positions].map(position=>({position,production:summary(comparison.production.own,position),allowance:summary(comparison.allowance.against,position)}));
  }
  function build(data,archive,fixtures,options){
    data=withHistoricalRoles(data);archive=withHistoricalRoles(archive);
    const o={phase:'all',window:'0',basis:'auto',positions:'broad',firstTarget:'including-free-throws',...options};
    validateOptions(o);
    if(o.trusted===false)throw Error('Verified evidence failed validation; positional comparisons unavailable');
    const current=eligibleGames(data,o),archiveAllowed=o.mode==='upcoming'&&archive?.meta?.season<data.meta.season&&o.date>archive.meta.asOfDate;
    const cache=new Map();
    const comparisons=[];
    for(const f of fixtures){
      if(!f.id||!f.home||!f.away||f.home===f.away||f.date!==o.date)throw Error('Selected matchup does not match the game date');
      const currentPair=[f.away,f.home].map((t,i)=>teamGames(current,t,i?f.away:f.home,o));
      const fallback=archiveAllowed&&(o.basis==='archive'||o.basis==='auto'&&currentPair.some(gs=>!gs.length));
      if(o.basis==='archive'&&o.mode==='upcoming'&&!archiveAllowed){comparisons.push({fixture:f,unavailable:'Prior-season archive unavailable for this selected season/date'});continue;}
      const source=fallback?archive:data,scopeMode=fallback?'review':o.mode;
      const key=source.meta.season+'|'+scopeMode;
      if(!cache.has(key)){
        const all=eligibleGames(source,{...o,mode:scopeMode});
        const teams=[...new Set(all.flatMap(g=>[g.home,g.away]))];
        const leagueTeams=teams.map(t=>aggregate(teamGames(all,t,null,{...o,headToHead:false}),t,o));
        const reference=Object.fromEntries(ALL.map(k=>[k,pool(leagueTeams.map(t=>t.own[k]))]));
        cache.set(key,{all,reference});
      }
      const {all,reference}=cache.get(key);
      const eventOptions={...o,openingPaths:source.openingPaths,playByPlay:source.playByPlay?.parentEvidenceContentHash===source.meta.evidenceContentHash?source.playByPlay:null};
      const away=aggregate(teamGames(all,f.away,f.home,o),f.away,eventOptions),home=aggregate(teamGames(all,f.home,f.away,o),f.home,eventOptions);
      comparisons.push({fixture:f,season:source.meta.season,isArchive:fallback||source.meta.season<(f.season||data.meta.season),scopeMode,positions:o.positions,headToHead:!!o.headToHead,reference,
        directions:[{production:away,allowance:home,reference,positions:o.positions},{production:home,allowance:away,reference,positions:o.positions}],
        authority:source.meta.officialBoxscoreContentHash||null,evidenceHash:source.meta.evidenceContentHash||null});
    }
    return {version:VERSION,options:o,comparisons};
  }
  return {VERSION,METRICS,POSITIONS,position,withHistoricalRoles,eligibleGames,teamGames,aggregate,value,rows,shootingRows,build};
});
