/* Assists/rebounds descriptive cards inside Parlay; inherits its selected scope. */
(function(){
 'use strict';const h=React.createElement,pct=v=>Number.isFinite(v)?(v*100).toFixed(1)+'%':'Unavailable',num=v=>Number.isFinite(v)?v.toFixed(2):'Unavailable';
 window.FTBAdditionalParlayPanel=function({slots=[],teamColors={}}){
  return h('section',{'aria-label':'Assists and Rebounds research'},h('h3',null,'Assists & Rebounds'),h('p',{className:'analyst-notice'},'Separate descriptive research · 5 complete player appearances and 5 games per team. These cards share the competition, date, period, opponent, position and history controls above. Scores are not win probabilities.'),
   [...new Set(slots.map(s=>s.team))].map(team=>h('section',{key:team},h('h4',null,team),h('div',{className:'analyst-grid parlay-grid'},slots.filter(s=>s.team===team).map(s=>{
    const p=s.pick;return h('article',{key:s.market,className:'player-card parlay-card','data-market':s.market,'data-team':team,style:{'--team-color':teamColors[team]||'#64748b'}},
     h('h4',{className:'parlay-market'},s.market==='assists'?'Assists':'Rebounds'),p?h(React.Fragment,null,h('strong',{className:'player-name'},p.name),h('p',null,p.group+' · '+(p.provisional?'Provisional research':'Research eligible')),h('p',null,'Historical average '+num(p.average)+' · '+p.gp+' appearances · '+num(p.mpg)+' recorded MPG'),s.market==='rebounds'&&h('p',null,num(p.oreb)+' offensive + '+num(p.dreb)+' defensive rebounds per appearance; team rebounds excluded.'),
     h('p',null,'Full selected-competition season average '+num(p.seasonTarget.average)+'; reaching that average means '+p.seasonTarget.threshold+'+. Observed '+p.seasonTarget.hits+'/'+p.seasonTarget.n+' ('+pct(p.seasonTarget.rate)+') in the selected sample. This is not a forecast probability.'),
     h('p',null,'Evidence score '+num(p.score)+' · offense '+pct(p.components.offense)+' · opponent allowance '+pct(p.components.defense)+' · historical opportunity proxy '+pct(p.components.opportunity)),
     h('p',null,'History teams: '+p.historyTeams.join(', ')+' · '+(p.availability||'Availability unconfirmed')),
     h('details',null,h('summary',null,'Other eligible candidates'),h('ol',null,s.ranked.slice(0,5).map(r=>h('li',{key:r.id},r.name+' · '+num(r.score)+' score · '+num(r.average)+' historical average')))))
     :h('p',null,'Selection unavailable · '+s.reason),
     h('p',{className:'analyst-notice'},s.evidenceSeason+' · '+(s.isArchive?'prior-season':'selected-season')+' evidence through '+(s.evidenceThrough||'no eligible games')+' · '+s.teamGames+' own / '+s.opponentGames+' opponent games. '+(s.positionFallbackReason||'')),
     h('details',null,h('summary',null,'Evidence and exclusions'),h('p',null,'Known positional production: '+pct(s.ownKnown)+' own / '+pct(s.opponentKnown)+' opponent. Historical minutes and credited-stat rate form the opportunity proxy; potential assists, rebound chances and conversion are not observed. Position is not a defender assignment.'),h('ul',null,s.audit.map((a,i)=>h('li',{key:i},a.name+': '+a.reason)))),h('div',{className:'card-accent'}));
   })))));
 };
})();
