/* Operational contract/availability guards, independent of the frozen probability models. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVService=api;})(typeof window==='object'?window:this,function(){
 'use strict';
 const VERSION='ev-service-v1',INJURY_AGE=900000,PRICE_AGE=300000;
 const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,''),base=s=>norm(String(s||'').replace(/\s+(?:jr|sr|ii|iii|iv)\.?$/i,''));
 function validateFeed(s){
  if(!s||s.schemaVersion!==1||s.region!=='TN'||s.bookmaker!=='fanduel'||!s.fixtures||Array.isArray(s.fixtures)||typeof s.fixtures!=='object'||!Number.isFinite(Date.parse(s.checkedAt))||s.errors!==undefined&&!Array.isArray(s.errors))return false;
  return Object.values(s.fixtures).every(e=>e&&typeof e==='object'&&e.fixture&&Array.isArray(e.quotes)&&(!e.issues||Array.isArray(e.issues)));
 }
 function offerError(q,f,now){
  if(!q||typeof q!=='object'||!f)return 'Missing offer or fixture';
  if(q.region!=='TN'||q.fixtureId!==f.id||f.phase!=='regular-season'||![f.home,f.away].includes(q.team)||!/^\d+$/.test(q.fanduelEventId||'')||!/^\d+(?:\.\d+)?$/.test(q.marketId||'')||!/^\d+$/.test(q.selectionId||'')||!/^\d+$/.test(q.playerId||'')||!q.player)return 'Incomplete exact offer identity';
  const first=q.market==='first-team-basket',count=['points','threes','assists','rebounds'].includes(q.market),ou=['over','under'].includes(q.side),milestone=q.side==='at-least',suffix=({points:' - Points',threes:' - Made Threes',assists:' - Assists',rebounds:' - Rebounds'})[q.market];
  if(first){if(q.marketType!=='FIRST_TEAM_BASKET_SCORER'||q.marketName!=='First Team Basket Scorer'||q.period!=='team-first-score'||q.side!=='yes'||q.line!==null||q.scoringDefinition!=='first-team-score-including-free-throws'||q.settlement!=='starter-required')return 'Unsupported First Team Basket contract';}
  else if(!count||q.period!=='full-game'||!Number.isFinite(q.line)||q.line<0||!Number.isInteger(q.line*2)||(!ou&&!milestone))return 'Unsupported exact count contract';
  else if(ou){const type=({points:/^PLAYER_[A-Z]+_TOTAL_POINTS$/,threes:/^PLAYER_[A-Z]+_TOTAL_MADE_3_POINT_FIELD_GOALS$/,assists:/^PLAYER_[A-Z]+_TOTAL_ASSISTS$/,rebounds:/^PLAYER_[A-Z]+_TOTAL_REBOUNDS$/})[q.market];if(!type.test(q.marketType||'')||!String(q.marketName||'').endsWith(suffix)||base(q.marketName.slice(0,-suffix.length))!==base(q.player))return 'Count market type/player label mismatch';}
  else {const type=q.market==='points'?'TO_SCORE_'+q.line+'+_POINTS':q.market==='threes'?q.line+'+_MADE_THREES':'TO_RECORD_'+q.line+'+_'+q.market.toUpperCase(),name=q.market==='points'?'To Score '+q.line+'+ Points':q.market==='threes'?q.line+'+ Made Threes':'To Record '+q.line+'+ '+q.market[0].toUpperCase()+q.market.slice(1);if(!Number.isInteger(q.line)||q.marketType!==type||String(q.marketName||'').toLowerCase()!==name.toLowerCase())return 'Milestone type/threshold mismatch';}
  const parts=String(q.key||'').split('|');if(parts.length!==5||parts[0]!==q.fanduelEventId||parts[1]!==q.marketId||parts[2]!==q.selectionId||parts[4]!==q.side||(first?parts[3]!=='None':parts[3].trim()===''||Number(parts[3])!==q.line))return 'Selection key differs from exact offer';
  let url;try{url=new URL(q.source);}catch(error){return 'Invalid quote source';}const tab=first?'quick-bets':({points:'player-points',threes:'player-threes',assists:'player-assists',rebounds:'player-rebounds'})[q.market];
  if(url.origin!=='https://sportsbook.fanduel.com'||!url.pathname.startsWith('/basketball/nba/')||!url.pathname.endsWith('-'+q.fanduelEventId)||url.searchParams.get('tab')!==tab)return 'Quote source/event/tab mismatch';
  const age=now-Date.parse(q.capturedAt),tip=Math.min(Date.parse(f.scheduledTipoff),Date.parse(q.fanduelTipoff));
  if(!Number.isFinite(tip)||Math.abs(Date.parse(f.scheduledTipoff)-Date.parse(q.fanduelTipoff))>900000||f.status!=='pre'||now>=tip)return 'Offer closed or fixture tipoff mismatch';
  if(!Number.isFinite(age)||age<0||age>PRICE_AGE)return 'Quote stale';
  if(q.captureState!=='fresh')return 'Quote '+(q.captureState||'capture state unavailable');
  if(q.marketStatus!=='OPEN'||q.runnerStatus!=='ACTIVE')return 'Quote suspended';
  if(!Number.isInteger(q.american)||Math.abs(q.american)<100||!Number.isFinite(q.decimal)||q.decimal<=1||Math.abs(q.decimal-(q.american>0?1+q.american/100:1+100/Math.abs(q.american)))>1e-6)return 'Price formats disagree';
  return null;
 }
 function screenSnapshot(snapshot,fixtures,now){
  const audit=[];if(!snapshot)return {snapshot:null,audit};if(!validateFeed(snapshot))return {snapshot:null,audit:[{reason:'Invalid odds snapshot schema',status:'invalid'}]};
  const entries={...snapshot.fixtures};for(const f of fixtures){const e=entries[f.id];if(!e)continue;const quotes=[];for(const q of e.quotes){const reason=offerError(q,f,now);if(reason)audit.push({key:q?.key,player:q?.player,market:q?.market,fixtureId:f.id,reason,status:'invalid',quote:q});else quotes.push(q);}entries[f.id]={...e,quotes};}
  return {snapshot:{...snapshot,fixtures:entries},audit};
 }
 function availability(id,fixture,context,view,confirmed,H,L,now){
  const official=L.validConfirmation(confirmed?.[id],fixture,now),injuries=L.availableInjuries(context.injuries||{},confirmed||{},fixture,now),projection=view?.record;
  // A depth-chart warning is evidence even when the central injury feed omits the player.
  if(projection&&['OUT','DOUBTFUL','QUESTIONABLE'].includes(projection.availability)&&!['OUT','DOUBTFUL'].includes(injuries[id]?.status)&&!(official&&projection.availability==='QUESTIONABLE'))injuries[id]={...injuries[id],status:projection.availability,capturedAt:projection.capturedAt,source:projection.source};
  const source=context.availabilitySource,age=now-Date.parse(source?.lastSuccess),fresh=!!context.fresh&&(!source||source.status==='fresh'&&age>=0&&age<INJURY_AGE);
  return H.pickEligibility(String(id),{...context,injuries,fresh:fresh||official});
 }
 return {VERSION,INJURY_AGE,PRICE_AGE,validateFeed,offerError,screenSnapshot,availability};
});
