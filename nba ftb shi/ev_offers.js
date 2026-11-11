/* Website offer-label compatibility and research visibility; probability models unchanged. */
(function(root,factory){
  const api=factory(typeof module==='object'&&module.exports?require('./ev_service.js'):root.FTBEVService);
  if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVOffers=api;
})(typeof window==='object'?window:this,function(base){
  'use strict';
  const VERSION='ev-offers-v1';
  function forGuard(q){
    if(q?.side!=='at-least'||!Number.isInteger(q.line)||!['points','threes','assists','rebounds'].includes(q.market))return q;
    const short=q.line+'+ '+(q.market==='threes'?'Threes':q.market[0].toUpperCase()+q.market.slice(1));
    if(String(q.marketName||'').toLowerCase()!==short.toLowerCase())return q;
    const canonical=q.market==='points'?'To Score '+q.line+'+ Points':q.market==='threes'?q.line+'+ Made Threes':'To Record '+q.line+'+ '+q.market[0].toUpperCase()+q.market.slice(1);
    // Only the validation copy gets an accepted alias. Stored source labels and identities remain exact.
    return {...q,marketName:canonical};
  }
  const offerError=(q,f,now)=>base.offerError(forGuard(q),f,now);
  function screenSnapshot(snapshot,fixtures,now){
    const audit=[];
    if(!snapshot)return {snapshot:null,audit};
    if(!base.validateFeed(snapshot))return {snapshot:null,audit:[{reason:'Invalid odds snapshot schema',status:'invalid'}]};
    const entries={...snapshot.fixtures};
    for(const f of fixtures){
      const e=entries[f.id];if(!e)continue;
      const quotes=[];
      for(const q of e.quotes){
        const reason=offerError(q,f,now);
        if(reason)audit.push({key:q?.key,player:q?.player,market:q?.market,fixtureId:f.id,reason,status:'invalid',quote:q});
        else quotes.push(q);
      }
      entries[f.id]={...e,quotes};
    }
    return {snapshot:{...snapshot,fixtures:entries},audit};
  }
  function coverage(snapshot,fixtures,now,predicate){
    const offered=[],fresh=[];
    for(const f of fixtures)for(const q of snapshot?.fixtures?.[f.id]?.quotes||[]){
      if(!q||!predicate(q))continue;
      offered.push(q);if(!offerError(q,f,now))fresh.push(q);
    }
    return {offered,fresh};
  }
  function firstTeamHistory(state,q){
    const r=state?.players?.[q.team+'|'+q.playerId];
    if(!r||!r.starts)return {status:'unavailable',reason:'No retained prior same-team starts'};
    return {status:'descriptive',starts:r.starts,wins:r.wins,through:r.history.at(-1)?.date||null,
      seasons:[...new Set(r.history.map(h=>h.season))],interpretation:'Observed first-team scores including free throws; not a forecast probability or EV estimate.'};
  }
  return {...base,VERSION,offerError,screenSnapshot,coverage,firstTeamHistory};
});
