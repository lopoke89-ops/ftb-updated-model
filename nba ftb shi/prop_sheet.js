/* Descriptive roster research beside EV; no price fetching or probability adjustment. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBPropSheet=api;})(typeof window==='object'?window:this,function(){
 'use strict';
 const VERSION='prop-sheet-v1',MARKETS=['points','threes','assists','rebounds'],names={points:'Points',threes:'Made threes',assists:'Assists',rebounds:'Rebounds'};
 const number=v=>Number.isFinite(v)?v.toFixed(1):'unavailable',pct=v=>Number.isFinite(v)?(100*v).toFixed(1)+'%':'unavailable';
 const ordinal=n=>n+(n%100>=11&&n%100<=13?'th':({1:'st',2:'nd',3:'rd'})[n%10]||'th');
 function rankText(r){return r?.status==='ranked'?`${r.tiedTeams>1?'Tied ':''}${ordinal(r.mostRank)}-most allowed of ${r.eligibleTeams}`:'Rank unavailable';}
 function build({context,fixtures=[],rosters={},viewPlayer,eligibility={},predictions={},additionalPredictions={},rows=[]}){
  if(!context?.describe)return [];
  const best=new Map();for(const r of rows){if(!MARKETS.includes(r.quote.market))continue;const k=[r.quote.fixtureId,r.quote.team,r.quote.playerId,r.quote.market].join('|');if(!best.has(k)||r.ev>best.get(k).ev)best.set(k,r);}
  return fixtures.map(fixture=>({fixture,teams:[fixture.away,fixture.home].map(team=>{
   const opponent=team===fixture.home?fixture.away:fixture.home;
   const players=(rosters[team]||[]).map(p=>{
    const view=viewPlayer(p.id,team,fixture),available=eligibility[p.id]||{provisional:true,reason:'Availability unconfirmed'};
    const cells=MARKETS.map(market=>{
     const k=[fixture.id,team,p.id,market].join('|'),r=best.get(k),prediction=(['assists','rebounds'].includes(market)?additionalPredictions:predictions)[k];
     const candidate=r||{quote:{fixtureId:fixture.id,playerId:String(p.id),team,market},features:prediction?.features||{},provisional:!!available.provisional||!!available.excluded,availability:available.reason};
     let c;try{c=r?.researchContext||context.describe(candidate,fixture,view);}catch(_){c={status:'unavailable',reason:'Source-bound context unavailable'};}
     return {market,context:c,offer:r?{quote:r.quote,probabilities:r.probabilities,ev:r.ev,breakEven:r.breakEven,provisional:r.provisional,historicalTarget:c.historicalTarget}:null,reason:available.excluded?available.reason:prediction?.reason||'No current supported price / estimate'};
    });
    return {id:String(p.id),name:p.name,team,position:view.record?.position||null,lineup:view.label||'Starter status unavailable',listedStarter:!!view.record,excluded:!!available.excluded,availability:available.reason||'Availability unconfirmed',provisional:!!available.provisional,cells};
   }).sort((a,b)=>Number(b.listedStarter)-Number(a.listedStarter)||a.name.localeCompare(b.name));
   return {team,opponent,players,opening:context.opening?.(fixture,opponent)||{status:'unavailable',reason:'Opening research unavailable'}};
  })}));
 }
 function render(sheet,h){
  const profile=(p,season,prior,compact=false)=>{
   if(!p)return null;const a=p.opposing,b=p.baseline,r=p.ranking,ratio=b?.per48>0?a.per48/b.per48-1:null;
   if(compact)return h('details',{className:'prop-early'},h('summary',null,`${season}: rank unavailable · ${a.games}/${a.expectedGames} matched games`),profile(p,season,prior));
   return h('div',{className:'prop-profile'},h('strong',null,`${season}${prior?' · prior season':''}: ${rankText(r)}`),
    h('span',null,`${number(a.per48)} per 48 player-min · other-team reference ${number(b.per48)}${ratio===null?'':` (${ratio>0?'+':''}${pct(ratio)})`}`),
    h('small',null,`${a.games}/${a.expectedGames} matched team-games · ${a.from||'unknown'} to ${a.through||'unknown'}`),
    r?.status!=='ranked'&&h('small',{className:'prop-concern'},r?.reason||'Rank evidence unavailable'));
  };
  const cell=c=>{
   const x=c.context,p=x.playerSample,r=c.offer;
   return h('div',{key:c.market,className:'prop-cell'},h('h6',null,names[c.market]),
    x.role&&h('small',null,`${x.opponent} vs ${x.role.position||'unknown'} · ${x.role.cohort}`),
    x.profile?profile(x.profile,x.dataset.season,x.dataset.priorSeason,!!x.priorSeason&&x.profile.ranking.status!=='ranked'):h('p',null,x.reason||'Context unavailable'),
    x.priorSeason&&h('small',null,`Prior-season cohort: ${x.priorSeason.role.position} · ${x.priorSeason.role.cohort}`),
    x.priorSeason&&profile(x.priorSeason.profile,x.priorSeason.season,true),
    p&&h('small',null,`Player: ${number(p.average)} / appearance · ${p.season} · ${p.n} same-team games · ${number(p.minutes)} historical min · through ${p.through}`),
    r?h('p',{className:'prop-offer'},`${r.quote.side==='at-least'?r.quote.line+'+':r.quote.side+' '+r.quote.line} · ${r.quote.american>0?'+':''}${r.quote.american} · model win ${pct(r.probabilities.win)} · push ${pct(r.probabilities.push)} · EV ${r.ev>0?'+':''}${pct(r.ev)}`,
     h('small',null,`Quote ${new Date(r.quote.capturedAt).toISOString()}${r.provisional?' · provisional':''}`),
     r.historicalTarget&&h('small',null,`Exact target history: ${r.historicalTarget.wins} wins / ${r.historicalTarget.losses} losses / ${r.historicalTarget.pushes} pushes; descriptive.`)):
     h('p',{className:'prop-concern'},'EV unavailable · '+c.reason),
    h('details',null,h('summary',null,'Main concern & evidence'),h('p',null,x.mainConcern||x.reason||'Evidence unavailable'),
     x.profile?.opposing&&h('p',null,`Largest game supplied ${pct(x.profile.opposing.largestGameShare)} of observed production. This is a concentration check, not an outlier adjustment.`),
     x.profile?.ranking?.status==='ranked'&&h('p',null,`Fewest-allowed rank ${x.profile.ranking.fewestRank} of ${x.profile.ranking.eligibleTeams}. ${30-x.profile.ranking.eligibleTeams} NBA teams do not qualify.`),
     (x.limitations||[]).map((s,i)=>h('p',{key:i},s)),
     (x.profile?.opposing?.sources||[]).slice(-2).map(s=>h('a',{key:s.gameId,href:s.url,target:'_blank',rel:'noreferrer'},s.date+' NBA box '))));
  };
  const player=p=>h('article',{key:p.id,className:'prop-player'},h('header',null,h('strong',null,p.name),h('span',null,`${p.position||'Role unconfirmed'} · ${p.lineup}`),h('span',{className:p.excluded?'prop-concern':''},p.availability)),h('div',{className:'prop-stats'},p.cells.map(cell)));
  const opening=(t,season)=>{const x=t.opening;return h('details',{className:'prop-opening'},h('summary',null,'FTB opening-score research'),h('p',null,x.definition||x.reason),...[x.profile,x.priorSeason].filter(Boolean).map(p=>h('section',{key:p.season},h('strong',null,`${p.season}${p.season<season?' · prior-season research':' · current season'} · ${t.opponent} allowed opponent first team scores`),h('p',null,`${p.games}/${p.expectedGames} matched opening games · through ${p.through||'unavailable'} · ${p.other} bench/other scorers`),h('ul',null,p.positions.map(r=>h('li',{key:r.position},`${r.position}: ${r.count}/${p.games} (${pct(r.frequency)}) · ${rankText(r.ranking)}${r.ranking.status==='ranked'?'':' · '+r.ranking.reason}`))))),h('p',null,'Historical opening frequencies only. No individual FTB probability or EV; full-game allowance is not opening-sequence evidence.'));
  };
  return h('details',{className:'prop-sheet'},h('summary',null,'Matchup stat sheet · all five positions · four prop stats'),
   h('p',null,'PG, SG, SF, PF and C · points, made threes, assists and rebounds. Rank 1 means MOST allowed. Compare the matchup with the player’s opportunity and actual price; ranks alone do not establish an over or under edge.'),
   h('details',{className:'prop-method'},h('summary',null,'How ranks, samples and prices work'),h('p',null,'Roster research includes players without an EV estimate. Five-position comparisons cover recorded starters; broad G/F/C comparisons include played appearances and are labeled separately.'),h('p',null,'Ranks use the same season, regular-season cutoff and cohort: at least 20 matched team-games, 90% game coverage and 20 qualifying NBA teams. Ties use unrounded rates. These are display sufficiency rules, not proof of accuracy. Rates are per 48 credited player-minutes, not per-game projections or pace-adjusted defense. Current and prior seasons are never pooled.')),
   sheet.map(g=>h('section',{key:g.fixture.id,className:'prop-fixture'},h('h3',null,`${g.fixture.away} @ ${g.fixture.home}`),h('small',null,`Research cutoff: before ${g.fixture.date} · full-game props; overtime included · conditional on participation`),
    g.teams.map(t=>h('section',{key:t.team,className:'prop-team'},h('h4',null,`${t.team} players vs ${t.opponent}`),t.players.filter(p=>p.listedStarter).map(player),
     !t.players.some(p=>p.listedStarter)&&h('p',{className:'prop-concern'},'No fresh complete starting lineup. Roster research is below; no players are promoted to confirmed starters.'),
     h('details',null,h('summary',null,`Other roster research · ${t.players.filter(p=>!p.listedStarter).length} players`),t.players.filter(p=>!p.listedStarter).map(player)),opening(t,g.fixture.season))))),
   h('p',null,'Price shown: highest estimated EV among currently supported offers for that player/stat, before the EV table’s display filters. Unsupported or expired prices have no EV here. Research rows are not additional betting selections.'));
 }
 return {VERSION,MARKETS,rankText,build,render};
});
