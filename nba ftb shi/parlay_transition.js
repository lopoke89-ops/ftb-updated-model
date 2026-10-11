/* Descriptive transition metadata. Never changes production selection. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory(require('./parlay.js'),require('./scouting_history.js'));else root.FTBParlayTransition=factory(root.FTBParlay,root.FTBScoutingHistory);})(typeof window!=='undefined'?window:this,function(P,H){
  'use strict';
  const VERSION='parlay-transition-v1';
  function detail(slot,current,model,full,acrossStints){
    const id=slot.pick?.id,entry=id?model.scope.byPlayer[id]:null;
    const rows=id?(acrossStints?entry?.all:entry?.teams[slot.team])||[]:[];
    const stats=id?P.summarize(rows):null,descriptive=id?P.summarize(full.scope.byPlayer[id]?.all||[]):null;
    const rule=H.READINESS.thresholds[slot.market],review=current.selectionReview||{};
    const actor=id?H.playerEvidence(model.snapshot,id,slot.team,acrossStints):null;
    return {version:VERSION,verified:!!model.snapshot.evidenceHash,playerId:id||null,currentSeason:model.season,currentThrough:full.through,
      descriptive,filtered:stats,recordedAppearances:id?(acrossStints?entry?.appearances:actor?.scoutingDetail?.gp)||0:null,
      starts:actor?.scoutingDetail?.starts??(id?0:null),paired:stats?(slot.market==='threes'?stats.threeCorrelation:stats.fgCorrelation):null,
      requiredTeamGames:rule.teamGames,requiredPlayerGames:rule.playerGames,requiredStarts:slot.market==='first-team-basket'?5:null,
      teamGames:review.teamGames??model.scope.byTeam[slot.team]?.games??0,opponentGames:review.opponentGames??model.scope.byTeam[slot.opponent]?.games??0,
      ownKnown:review.ownKnown??null,opponentKnown:review.opponentKnown??null,
      currentCandidate:current.pick?{id:current.pick.id,name:current.pick.name,provisional:current.pick.provisional}:null,
      currentReady:!!current.pick,currentReason:current.reason||null,
      targetBasis:slot.pick?.seasonTarget?{season:slot.evidenceSeason,competition:full.phase,average:slot.pick.seasonTarget.average,threshold:slot.pick.seasonTarget.threshold,scope:'full competition season across stints at cutoff'}:null};
  }
  function capture(slots,data,context,sources={}){
    return {context,hash:data.meta.evidenceContentHash||null,season:data.meta.season,
      games:Object.fromEntries(data.games.map(g=>[g.id,{hash:g.sourceHash,teams:[g.home,g.away]}])),
      sources,slots:Object.fromEntries(slots.map(s=>[s.team+'|'+s.market,{id:s.pick?.id||null,season:s.evidenceSeason,
        score:s.pick?.score??null,provisional:s.pick?.provisional??null,reason:s.reason,team:s.team,opponent:s.opponent,
        teamGames:s.transition?.teamGames,opponentGames:s.transition?.opponentGames}]))};
  }
  function changes(previous,next){
    const out={};for(const [key,s] of Object.entries(next.slots)){
      if(!previous||previous.context!==next.context){out[key]=previous?'Analysis context changed; showing the selected fixture and filters.':'Verified snapshot loaded; no earlier comparison in this session.';continue;}
      const old=previous.slots[key];if(!old){out[key]='Market loaded; no earlier comparison.';continue;}
      const relevant=g=>g.teams.includes(s.team)||g.teams.includes(s.opponent);
      const added=Object.entries(next.games).filter(([id,g])=>!previous.games[id]&&relevant(g)).length;
      const corrected=Object.entries(next.games).filter(([id,g])=>previous.games[id]&&previous.games[id].hash!==g.hash&&relevant(g)).length;
      const removed=Object.entries(previous.games).filter(([id,g])=>!next.games[id]&&relevant(g)).length;
      const evidence=[added&&`${added} verified matchup-team game(s) added`,corrected&&`${corrected} official gamebook correction(s) loaded`,removed&&`${removed} game(s) removed from the verified snapshot`].filter(Boolean).join('; ');
      const same=s.id===old.id&&s.season===old.season&&s.provisional===old.provisional;
      const sourceChanged=JSON.stringify(previous.sources)!==JSON.stringify(next.sources);
      out[key]=(evidence?evidence+'. ':next.hash!==previous.hash?'Dataset changed outside these teams; local sample counts are unchanged. ':sourceChanged?'Source check/availability state updated. ':'No new verified games for this matchup. ')+
        (!s.id?'Selection unavailable: '+(s.reason||'supporting requirements not met'):s.season!==old.season?'Selection evidence basis changed to '+s.season+'.':same?(s.score!==old.score?'The same player still leads; the evidence score changed (including possible shared-baseline effects).':'The same player remains selected; supporting basis retained.'):'Selection or eligibility changed; review current source and candidate details.');
    }return out;
  }
  function normalizeExport(record){
    if(!record||![2,3].includes(record.schemaVersion)||!Array.isArray(record.selections))throw Error('Unsupported Parlay export schema');
    return {...record,capturedAt:record.capturedAt||record.recordedAt||null,recordType:record.recordType||'research-snapshot',
      verifiedIssuedAt:null,schemaVersion:3,originalSchemaVersion:record.schemaVersion};
  }
  return {VERSION,detail,capture,changes,normalizeExport};
});
