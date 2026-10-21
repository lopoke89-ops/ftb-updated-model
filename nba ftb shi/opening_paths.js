/* Descriptive opening paths from source-linked events. Never changes pick rankings. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.FTBOpeningPaths=api;})(typeof window==='object'?window:null,function(){
 'use strict';
 const VERSION='opening-paths-v1',fieldTarget=target=>/field.goal|field-goal/.test(target||''),name=(g,team,id)=>g.teams?.[team]?.players?.find(p=>String(p.id)===String(id))?.name||'Unresolved player';
 function summarize(games,team,target,datasets=[],positionScope='broad'){
  const expected=games.filter(g=>g.home===team||g.away===team),key=fieldTarget(target)?'first-field-goal':'first-score',players={},eligible=[],excluded=[];
  for(const g of expected){
   const source=datasets.filter(Boolean).map(d=>d.games?.[g.id]).find(r=>r?.sourceHash===g.sourceHash),path=source?.teams?.[team]?.[key];
   if(!path?.available){excluded.push({id:g.id,reason:path?.reason||source?.reason||'Source-linked opening path unavailable'});continue;}
   const add=id=>{if(!players[id])players[id]={id,name:name(g,team,id),appearances:0,initialAttempts:0,initialMakes:0,firstScores:0,offensiveRebounds:0,putbackFinishes:0,directSecondChanceFinishes:0,positions:[]};return players[id];};
   for(const p of g.teams[team].players.filter(p=>p.played)){const r=add(String(p.id)),raw=g.positionRoles?.[p.id]||p.verifiedFivePosition||p.officialPosition||p.rawPosition||'unknown',pos=positionScope==='strict'||positionScope==='specific'?(['PG','SG','SF','PF','C'].includes(raw)?raw:'unknown'):(['PG','SG','G'].includes(raw)?'G':['SF','PF','F'].includes(raw)?'F':raw==='C'?'C':'unknown');r.appearances++;if(!r.positions.includes(pos))r.positions.push(pos);}
   const initial=path.initialAttempt;if(initial?.playerId){const p=add(initial.playerId);p.initialAttempts++;p.initialMakes+=Number(initial.made);}
   const scorer=add(path.firstScore.playerId);scorer.firstScores++;scorer.putbackFinishes+=Number(path.explicitPutbackFinish);scorer.directSecondChanceFinishes+=Number(path.directOffensiveReboundFinish);
   for(const r of path.offensiveRebounds)add(r.playerId).offensiveRebounds++;
   eligible.push({id:g.id,date:g.date,game:g,path,source:source.source});
  }
  return {version:VERSION,team,target:key,expected:expected.length,eligible:eligible.length,excluded,through:eligible.map(r=>r.date).sort().at(-1)||null,players:Object.values(players).sort((a,b)=>b.initialAttempts-a.initialAttempts||b.offensiveRebounds-a.offensiveRebounds||a.name.localeCompare(b.name)),games:eligible};
 }
 function install(root){
  if(!root?.React)return;const h=root.React.createElement;
  root.FTBOpeningPathsPanel=function OpeningPathsPanel({games=[],team,target,dataset,playerId,positionScope='broad'}){
   const s=summarize(games,team,target,[dataset,root.__FTB_OPENING_PATHS__],positionScope),rows=playerId?s.players.filter(p=>p.id===String(playerId)):s.players.filter(p=>p.initialAttempts||p.firstScores||p.offensiveRebounds);
   const eText=(g,e)=>e?`${e.clock} ${e.playerId?name(g,e.team,e.playerId):e.team+(e.teamRebound?' team/dead-ball':' unresolved actor')} · ${e.text}`:'unavailable';
   const sourceEvent=(entry,e)=>e?h('a',{href:entry.source+'#page='+e.page,target:'_blank',rel:'noreferrer'},eText(entry.game,e)):null;
   return h('details',{className:'opening-paths','data-team':team},h('summary',null,`${team} opening attempts, rebounds & putbacks`),
    h('p',null,`${s.eligible} / ${s.expected} scoped team games with verified paths · through ${s.through||'unavailable'}. ${s.target==='first-score'?'First team score includes free throws.':'First made field goal; opening free throws can precede it.'} Player counts use actual appearances for this historical team. Tables show players with a credited opening event; narrow tables scroll horizontally.`),
    h('p',null,'First attempts measure initial opportunity. Offensive rebounds count player credits before the selected team first score. Printed putbacks and direct offensive-rebound finishes are separate; a rebound alone does not prove a putback or defender assignment. Team/dead-ball rebounds are not player credits.'),
    !s.eligible?h('p',{role:'status'},'Opening paths unavailable for this scope. Verified box scores remain usable.'):h('div',{style:{overflowX:'auto'}},h('table',{style:{minWidth:700}},h('caption',null,team+' · opening path comparison'),h('thead',null,h('tr',null,['Player · recorded roles','Initial attempts / appearances','Made initial attempts',s.target==='first-field-goal'?'First made FGs':'First scores',s.target==='first-field-goal'?'OREB before first FG':'OREB before first score','Printed putback finishes','Direct second-chance finishes'].map(label=>h('th',{key:label},label)))),h('tbody',null,rows.map(p=>h('tr',{key:p.id},h('th',{scope:'row'},p.name+' · '+p.positions.join('/')),h('td',null,p.initialAttempts+' / '+p.appearances),h('td',null,p.initialAttempts?p.initialMakes+' / '+p.initialAttempts:'Unavailable · no initial attempts'),h('td',null,p.firstScores),h('td',null,p.offensiveRebounds),h('td',null,p.putbackFinishes),h('td',null,p.directSecondChanceFinishes)))))),
    s.excluded.length>0&&h('p',null,`${s.excluded.length} games excluded: `+s.excluded.map(e=>e.id+' ('+e.reason+')').join('; ')),
    h('details',null,h('summary',null,'Miss → rebound → next attempt · source paths'),h('p',null,'Only events before this team’s selected opening score enter these paths. A missed nonfinal free throw may have no rebound. The next recorded attempt can belong to either team; turnovers end a direct path. Showing up to 20 most recent eligible games; use the period/opponent controls to narrow the sample.'),
     s.games.slice(-20).reverse().map(entry=>h('details',{key:entry.id},h('summary',null,`${entry.date} · ${entry.id} · first scorer ${name(entry.game,team,entry.path.firstScore.playerId)}${entry.path.explicitPutbackFinish?' · printed putback':''}`),h('p',null,'Initial attempt: ',sourceEvent(entry,entry.path.initialAttempt)),entry.path.misses.length?h('ul',null,entry.path.misses.map(m=>h('li',{key:m.attempt.sequence},sourceEvent(entry,m.attempt),' → ',m.rebound?sourceEvent(entry,m.rebound):m.reboundStatus,' → ',m.nextAttempt?sourceEvent(entry,m.nextAttempt):m.terminalTurnover?sourceEvent(entry,m.terminalTurnover):'no next attempt before opening score',h('small',{style:{display:'block'}},m.rebounderScoredNext===null?(m.terminalTurnover?'Turnover ended this path before another attempt.':'Rebounder scoring next: unavailable.'):m.rebounderScoredNext?'Same rebounder made the next recorded attempt.':'The rebounder did not make the next recorded attempt.'),m.teamRebounds.length>0&&h('small',null,` ${m.teamRebounds.length} team/dead-ball rebound records retained separately.`)))):h('p',null,'No missed selected-type attempts before this team first score.'),h('p',null,'First score: ',sourceEvent(entry,entry.path.firstScore))))));
  };
 }
 return {VERSION,summarize,install};
});
if(typeof window==='object')window.FTBOpeningPaths.install(window);
