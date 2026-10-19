/* Separate competing-outcome model. Historical grades never become probabilities. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./ev_probability.js'):root.FTBEV,typeof module==='object'&&module.exports?require('./lineups.js'):root.FTBLineups,typeof module==='object'&&module.exports?require('./lineup_projections.js'):root.FTBProjectedLineups);if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVFirstTeam=api;})(typeof window==='object'?window:this,function(E,L,Q){
 'use strict';
 const VERSION='ev-first-team-v1.1',TARGET='first-team-score-including-free-throws',clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function newState(){return {players:{},teams:{},league:{starts:0,wins:0,games:0,other:0,roles:{}},seen:new Set(),through:null};}
 const box=()=>({starts:0,wins:0});
 function verifiedGames(data,supplement){
  const o=supplement?.openingEvidence;if(!o||supplement.meta?.parentEvidenceContentHash!==data?.meta?.evidenceContentHash||o.meta?.parentEvidenceContentHash!==data.meta.evidenceContentHash)return [];
  return (data.games||[]).map(g=>({...g,season:data.meta.season,firstScoreEvidence:o.games?.[g.id]}));
 }
 function validGame(g){
  const o=g.firstScoreEvidence;if(g.phase!=='regular-season'||!o||o.source!==g.source||o.sourceHash!==g.sourceHash||!/^[a-f0-9]{64}$/.test(g.sourceHash||'')||!/^https:\/\/(?:statsdmz|stats)\.nba\.com\/pdfs\//.test(g.source||''))return false;
  return [g.home,g.away].every(t=>{const ps=g.teams?.[t]?.players||[],event=o.firstScores?.[t];return ps.filter(p=>p.played&&p.starter).length===5&&new Set(ps.map(p=>String(p.id))).size===ps.length&&event?.period===1&&[1,2,3].includes(event.points)&&event.page>1&&Number.isInteger(event.sequence)&&ps.some(p=>p.played&&String(p.id)===String(event.id))&&g.firstScores?.[t]?.id===event.id;});
 }
 function addGame(s,g){
  if(!validGame(g))throw Error('Verified NBA PDF opening evidence is unavailable');if(s.seen.has(g.id))throw Error('Duplicate First Team Basket game');s.seen.add(g.id);s.through=g.date;
  for(const team of [g.home,g.away]){
   const opponent=team===g.home?g.away:g.home,own=s.teams[team]||(s.teams[team]={games:0,other:0,own:{},allowed:{}}),def=s.teams[opponent]||(s.teams[opponent]={games:0,other:0,own:{},allowed:{}}),starters=g.teams[team].players.filter(p=>p.played&&p.starter),scorer=String(g.firstScoreEvidence.firstScores[team].id),starterScored=starters.some(p=>String(p.id)===scorer);
   own.games++;own.other+=Number(!starterScored);s.league.games++;s.league.other+=Number(!starterScored);
   for(const p of starters){const id=String(p.id),key=team+'|'+id,role=E.group(p.officialPosition||p.rawPosition),win=Number(id===scorer),r=s.players[key]||(s.players[key]={starts:0,wins:0,history:[]});r.starts++;r.wins+=win;r.history.push({gameId:g.id,date:g.date,season:g.season||'unknown',win,role,roleSource:p.officialPosition?'NBA printed starter position':'Stored historical position'});s.league.starts++;s.league.wins+=win;
    if(role)for(const target of [own.own,def.allowed,s.league.roles]){const b=target[role]||(target[role]=box());b.starts++;b.wins+=win;}
   }
  }
 }
 function buildState(games,{before}={}){const s=newState();for(const g of [...games].filter(g=>g.phase==='regular-season'&&(!before||g.date<before)).sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id)))addGame(s,g);return s;}
 function features(s,team,opponent,players){
  if(players.length!==5||new Set(players.map(p=>String(p.id))).size!==5)return {reason:'Needs five distinct starters'};
  const own=s.teams[team],def=s.teams[opponent];if(!(own?.games>=10&&def?.games>=10))return {reason:'Needs ten verified prior games for both teams'};
  const leagueRate=(s.league.wins+1)/(s.league.starts+5),other=(own.other+20*(s.league.other+1)/(s.league.games+200))/(own.games+20);
  const rows=players.map(p=>{const r=s.players[team+'|'+String(p.id)],last=r?.history.at(-1),role=last?.role,base=s.league.roles[role],rate=base?.starts?(base.wins+1)/(base.starts+5):leagueRate;
   const ratio=b=>b?.starts?Math.exp(clamp(Math.log(Math.max(.01,((b.wins+20*rate)/(b.starts+20))/rate)),-.7,.7)):1;
   return {id:String(p.id),name:p.name||String(p.id),team,n:r?.starts||0,wins:r?.wins||0,losses:r?r.starts-r.wins:0,history:r?.history||[],role,roleSource:last?.roleSource,through:last?.date,historySeasons:[...new Set((r?.history||[]).map(h=>h.season))],teams:[team],leagueRate,positionRate:rate,offenseRatio:ratio(own.own[role]),defenseRatio:ratio(def.allowed[role])};});
  const short=rows.find(p=>p.n<20);if(short)return {reason:`Each lineup player needs 20 prior starts with ${team}; ${short.name} has ${short.n}`};
  if(rows.some(p=>!p.role))return {reason:'Starter G/F/C history is unavailable'};
  return {players:rows,other,team,opponent,teamGames:own.games,opponentGames:def.games,through:s.through};
 }
 function distribution(f,c={}){
  if(f.reason)return {reason:f.reason};const weights=f.players.map(p=>{const prior=c.prior||20,recent=p.history.slice(-20),r=(p.wins+prior*p.leagueRate)/(p.n+prior),rr=(recent.reduce((n,h)=>n+h.win,0)+prior*p.leagueRate)/(recent.length+prior),rate=r*(1-(c.recentWeight||0))+rr*(c.recentWeight||0);return Math.pow(rate*Math.pow(p.offenseRatio,c.offensePower||0)*Math.pow(p.defenseRatio,c.defensePower||0),1/(c.temperature||1));}),total=weights.reduce((a,b)=>a+b,0),other=clamp(f.other,1e-6,.2),probabilities={};
  f.players.forEach((p,i)=>probabilities[p.id]=(1-other)*weights[i]/total);return {probabilities,other,features:f};
 }
 function predictTeam(s,team,opponent,players,model){if(model?.version!==VERSION||!model.config||!model.diagnostic)return {reason:'First Team Basket model unavailable'};return distribution(features(s,team,opponent,players),model.config);}
 function confirmedLineup(team,fixture,roster,confirmed,now){
  const players=Object.values(confirmed||{}).filter(p=>p.team===team&&L.validConfirmation(p,fixture,now));
  if(players.length!==5||new Set(players.map(p=>p.id)).size!==5||new Set(players.map(p=>p.position)).size!==5)return {reason:'Awaiting five fresh NBA confirmed starters for '+team};
  if(players.some(p=>roster.filter(r=>String(r.id)===p.id&&r.team===team).length!==1))return {reason:'Confirmed starters do not match the current roster'};
  return {players};
 }
 function lineupForEV(team,fixture,roster,lineupContext,confirmed,now=Date.now()){
  const view=Q.teamView(team,fixture,{...lineupContext,confirmed:confirmed??lineupContext?.confirmed??{}},now);
  if(view.kind==='unavailable')return {reason:'Awaiting a complete, fresh projected or NBA confirmed lineup for '+team};
  if(view.players.some(p=>roster.filter(r=>String(r.id)===String(p.id)&&r.team===team&&r.name===p.name).length!==1))return {reason:'Lineup players do not match the current roster'};
  return {players:view.players,kind:view.kind,provisional:view.kind==='projected',label:view.label};
 }
 function quoteState(q,fixture,now){
  if(q.market!=='first-team-basket'||q.marketType!=='FIRST_TEAM_BASKET_SCORER'||q.marketName!=='First Team Basket Scorer'||q.period!=='team-first-score'||q.side!=='yes'||q.line!==null||q.scoringDefinition!==TARGET||q.settlement!=='starter-required')return 'identity-mismatch';
  return E.quoteState({...q,market:'points',period:'full-game'},fixture,now);
 }
 function evaluateQuotes({snapshot,fixtures,rosters,state,model,confirmed,lineupContext,eligibility={},now=Date.now()}){
  const rows=[],audit=[],pending=[],seen=new Set();
  for(const fixture of fixtures){const entry=snapshot?.fixtures?.[fixture.id],predictions={};for(const q of entry?.quotes||[]){if(q.market!=='first-team-basket')continue;let reason=null;const status=quoteState(q,fixture,now),roster=rosters[q.team]||[],player=roster.filter(p=>String(p.id)===q.playerId&&p.team===q.team&&p.name===q.player);
   if(seen.has(q.key)){audit.push({player:q.player,market:q.market,reason:'Duplicate offered selection'});continue;}seen.add(q.key);
   if(snapshot.schemaVersion!==1||snapshot.region!=='TN'||snapshot.bookmaker!=='fanduel'||['id','home','away','date','phase','season'].some(k=>entry.fixture?.[k]!==fixture[k])||fixture.phase!=='regular-season'||Date.parse(entry.fixture?.scheduledTipoff)!==Date.parse(fixture.scheduledTipoff)||entry.fanduelEventId!==q.fanduelEventId)reason='Odds snapshot identity mismatch';
   else if(status!=='fresh')reason='Quote '+status;
   else if(player.length!==1)reason='Current-roster identity mismatch';
   else if(!/^https:\/\/sportsbook\.fanduel\.com\//.test(q.source||'')||!Number.isInteger(q.american)||Math.abs(q.american)<100||!Number.isFinite(q.decimal)||q.decimal<=1||Math.abs(q.decimal-(q.american>0?1+q.american/100:1+100/Math.abs(q.american)))>1e-6)reason='Offered price/source mismatch';
   else if(eligibility[q.playerId]?.excluded)reason=eligibility[q.playerId].reason||'Unavailable player';
   if(reason){audit.push({key:q.key,player:q.player,market:q.market,reason,status});continue;}
   if(!predictions[q.team]){const lineup=lineupForEV(q.team,fixture,roster,lineupContext,confirmed,now),blocked=lineup.players?.find(p=>eligibility[p.id]?.excluded||['OUT','DOUBTFUL'].includes(p.availability)||lineup.kind==='confirmed'&&eligibility[p.id]?.provisional);predictions[q.team]=lineup.reason?lineup:blocked?{reason:'Lineup availability is excluded or unresolved'+(eligibility[blocked.id]?.reason?': '+eligibility[blocked.id].reason:'')}:state?{...predictTeam(state,q.team,q.team===fixture.home?fixture.away:fixture.home,lineup.players,model),lineup:lineup.players,lineupBasis:lineup.kind,provisional:lineup.provisional}:{reason:'Verified First Team Basket history unavailable'};}
   const pred=predictions[q.team],f=pred.features?.players.find(p=>p.id===q.playerId);
   if(pred.reason)reason=pred.reason;else if(!f)reason='Player is not in the current '+pred.lineupBasis+' five';else if(f.wins<3||f.losses<5)reason='Needs three prior starter first-score wins and five losses';
   if(reason){audit.push({key:q.key,player:q.player,market:q.market,reason,status});pending.push({quote:q,reason});continue;}
   const win=pred.probabilities[q.playerId],p={win,loss:1-win,push:0};rows.push({quote:q,probabilities:p,ev:E.expectedValue(p,q.decimal),breakEven:1/q.decimal,conditionalWin:win,projection:null,features:{...f,history:undefined,otherFirstScorerProbability:pred.other,lineupProbabilities:pred.probabilities,teamGames:pred.features.teamGames,opponentGames:pred.features.opponentGames},lineupBasis:pred.lineupBasis,...(pred.provisional?{projectedLineup:pred.lineup}:{confirmedLineup:pred.lineup}),provisional:pred.provisional,availability:pred.provisional?'Projected lineup · provisional. Probability and EV assume these exact five start; their chance of starting is not modeled. Not a finalized First Team Basket pick.':'Five NBA confirmed starters; probability conditional on this lineup',status,modelVersion:model.version,modelHash:model.modelHash,engineHash:model.engineHash,protocolHash:model.protocolHash,forwardProtocolHash:model.forwardProtocolHash,rulesProfileHash:model.rulesProfileHash});
  }}rows.sort((a,b)=>b.ev-a.ev||a.quote.key.localeCompare(b.quote.key));return {rows,audit,pending};
 }
 return {VERSION,TARGET,newState,verifiedGames,validGame,addGame,buildState,features,distribution,predictTeam,confirmedLineup,lineupForEV,quoteState,evaluateQuotes};
});
