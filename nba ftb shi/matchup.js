/* Descriptive positional comparisons. Never supplies probabilities or Parlay weights. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBMatchup=api;})(typeof window==='object'?window:globalThis,function(){
  'use strict';
  const VERSION='matchup-evidence-v1';
  const METRICS={points:'Points',blocks:'Blocks',rebounds:'Rebounds',offensiveRebounds:'Offensive rebounds',defensiveRebounds:'Defensive rebounds',assists:'Assists',firstTeam:'First Team Basket'};
  const POSITIONS={broad:['G','F','C','unknown'],strict:['PG','SG','SF','PF','C','unknown']};
  const PHASES=['all','regular-season','playoffs','regular-and-playoffs','play-in','nba-cup-final'];
  const finite=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
  const phaseOK=(g,phase)=>phase==='all'||(phase==='regular-and-playoffs'?['regular-season','playoffs'].includes(g.phase):g.phase===phase);
  function position(p,basis='broad'){
    // The role belongs to this appearance. Current rosters and season-wide role maps are deliberately absent.
    const raw=String(p?.officialPosition||p?.rawPosition||'').trim().toUpperCase();
    const role=({'POINT GUARD':'PG','SHOOTING GUARD':'SG','SMALL FORWARD':'SF','POWER FORWARD':'PF',CENTER:'C',GUARD:'G',FORWARD:'F'})[raw]||raw;
    if(basis==='strict')return POSITIONS.strict.includes(role)?role:'unknown';
    return ['PG','SG','G'].includes(role)?'G':['SF','PF','F'].includes(role)?'F':role==='C'?'C':'unknown';
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
      const value=metric==='firstTeam'?(firstScore===null?null:(String(firstScore.id)===String(p.id)?1:0)):p[metric];
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
  function aggregate(games,team,o){
    const own=Object.fromEntries(Object.keys(METRICS).map(k=>[k,emptySeries()]));
    const against=Object.fromEntries(Object.keys(METRICS).map(k=>[k,emptySeries()]));
    const sources=[];
    for(const g of games){
      const opponent=g.home===team?g.away:g.home,ownRows=playedBox(g,team),oppRows=playedBox(g,opponent);
      sources.push({id:String(g.id),date:g.date,opponent,url:ownRows.find(authority)?.statsSource||null});
      const ownFirst=firstScore(g,team,o.firstTarget,ownRows),oppFirst=firstScore(g,opponent,o.firstTarget,oppRows);
      for(const k of Object.keys(METRICS)){
        accumulate(own[k],ownRows,k,o.positions,ownFirst);
        // Against means the opposing stat recorder: blocker, rebounder, passer or scorer.
        accumulate(against[k],oppRows,k,o.positions,oppFirst);
      }
    }
    return {team,games:games.length,gameIds:games.map(g=>String(g.id)),sources,from:games[0]?.date||null,through:games.at(-1)?.date||null,own,against};
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
  function build(data,archive,fixtures,options){
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
        const reference=Object.fromEntries(Object.keys(METRICS).map(k=>[k,pool(leagueTeams.map(t=>t.own[k]))]));
        cache.set(key,{all,reference});
      }
      const {all,reference}=cache.get(key);
      const away=aggregate(teamGames(all,f.away,f.home,o),f.away,o),home=aggregate(teamGames(all,f.home,f.away,o),f.home,o);
      comparisons.push({fixture:f,season:source.meta.season,isArchive:fallback||source.meta.season<(f.season||data.meta.season),scopeMode,positions:o.positions,headToHead:!!o.headToHead,reference,
        directions:[{production:away,allowance:home,reference,positions:o.positions},{production:home,allowance:away,reference,positions:o.positions}],
        authority:source.meta.officialBoxscoreContentHash||null,evidenceHash:source.meta.evidenceContentHash||null});
    }
    return {version:VERSION,options:o,comparisons};
  }
  return {VERSION,METRICS,POSITIONS,position,eligibleGames,teamGames,aggregate,value,rows,build};
});
