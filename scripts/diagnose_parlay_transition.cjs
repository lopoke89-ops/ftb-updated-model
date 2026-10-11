/* Within-season diagnostic only. Does not validate genuine season transfer. */
'use strict';
const fs=require('node:fs'),path=require('node:path');
const base=path.resolve(__dirname,'../nba ftb shi'),A=require(base+'/analyst.js'),H=require(base+'/scouting_history.js'),P=require(base+'/parlay.js'),R=require(base+'/parlay_research.js');
const data=require(base+'/analyst_data.json'),extra=require(base+'/parlay_data.json'),config=require(base+'/parlay_research_config.json');
const split='2025-12-16',training={...data,games:data.games.filter(g=>g.date<split)},later={...data,games:data.games.filter(g=>g.date>=split)};
const days=[...new Set(later.games.filter(g=>g.phase==='regular-season').map(g=>g.date))].sort();
const rows=[];
function pair(d,date,target){return Object.fromEntries(['specific','broad'].map(positionScope=>[positionScope,P.build(A,H,d,extra,{mode:'pregame',date,phase:'regular-season',firstBasketTarget:target,positionScope})]));}
function rank(models,team,opponent,roster,resolution='auto',seasonScope){return P.rankPositionVariants(models,{team,opponent,roster,seasonScope:seasonScope||models.specific.scope,minimumGames:{'first-team-basket':5,points:10,threes:10}},resolution).map(s=>P.applySelectionPolicy(s,{scope:s.evidenceModel.scope,minimumGames:s.market==='first-team-basket'?5:10,minimumTeamGames:s.market==='threes'?10:5}));}
function outcome(game,team,market,p,target){if(!p)return null;const actor=game.teams[team].players.find(a=>a.id===p.id),played=!!actor?.played;
  return {id:p.id,played,threshold:p.seasonTarget?.threshold??null,hit:market==='first-team-basket'?game[target===P.FIRST_TARGETS[1]?'firstFieldGoals':'firstScores'][team].id===p.id:played&&actor[market==='points'?'points':'threeMade']>=p.seasonTarget.threshold};}
const historical=Object.fromEntries(P.FIRST_TARGETS.map(t=>[t,pair(training,split,t)]));
for(const [index,day] of days.entries()){
  for(const target of P.FIRST_TARGETS){const old=historical[target],now=pair(later,day,target),full=pair(data,day,target);
    for(const g of later.games.filter(g=>g.date===day&&g.phase==='regular-season'))for(const team of [g.home,g.away]){
      const opponent=g.home===team?g.away:g.home,roster=full.specific.snapshot.rosters[team]||[];
      const a=rank(old,team,opponent,roster),c=rank(now,team,opponent,roster,'auto',full.specific.scope);
      const oldCache={},currentCache={};
      for(let i=0;i<3;i++){if(target===P.FIRST_TARGETS[1]&&i)continue;
        const scope=a[i].positionScope==='broad'||c[i].positionScope==='broad'?'broad':'specific';
        const aa=(oldCache[scope]||(oldCache[scope]=rank(old,team,opponent,roster,scope)))[i],cc=(currentCache[scope]||(currentCache[scope]=rank(now,team,opponent,roster,scope,full[scope].scope)))[i];
        const state=H.readiness(now.specific.snapshot,team,opponent,cc.market),production=P.selectMarketEvidence(c[i],a[i],state);
        const adaptive=R.rank({archive:aa,current:cc,productionCurrent:c[i],model:now[scope],full:full[scope],config,competition:'regular-season',firstBasketTarget:target});
        // Current-season targets in this diagnostic use the actual full 2025-26
        // pregame average; prior fallback uses the frozen development-prefix average.
        rows.push({fixtureId:g.id,date:day,team,market:cc.market,target,teamGames:state.teamGames,
          production:outcome(g,team,cc.market,production.pick,target),adaptive:outcome(g,team,cc.market,adaptive.pick,target),
          ...Object.fromEntries(Object.entries(adaptive.baselines||{}).map(([k,p])=>[k,outcome(g,team,cc.market,p,target)]))});
      }
    }
  }
  if(index%20===0)process.stderr.write('Diagnostic '+(index+1)+'/'+days.length+' dates\n');
}
const summary={};
for(const r of rows){const key=r.market+'|'+(r.market==='first-team-basket'?r.target:'season-average'),s=summary[key]||(summary[key]={opportunities:0,models:{},paired:0,pairedDifference:0});s.opportunities++;
  for(const model of ['production','adaptive','volume','mean','no-position','no-correlation']){const m=s.models[model]||(s.models[model]={issued:0,hits:0,dnp:0});if(r[model]){m.issued++;m.hits+=+r[model].hit;m.dnp+=+!r[model].played;}}
  if(r.production&&r.adaptive){s.paired++;s.pairedDifference+=+r.adaptive.hit-+r.production.hit;}
}
for(const s of Object.values(summary)){for(const m of Object.values(s.models))m.rate=m.issued?m.hits/m.issued:null;s.pairedDifference=s.paired?s.pairedDifference/s.paired:null;}
const report={status:'conditional within-season diagnostic; not season-transfer evidence',developmentEnd:config.developmentEnd,configurationHash:config.configurationHash,
  history:'2025-26 games before 2025-12-16',current:'Later 2025-26 games at a strict pregame date cutoff',dates:days.length,summary,rows,
  limitations:['Historical injury and pregame confirmation captures are unavailable.','The same archive was previously inspected.','The two windows are not different seasons.','No default-model promotion is supported by this diagnostic.'],promotable:false};
fs.writeFileSync(path.resolve(__dirname,'../PARLAY_TRANSITION_DIAGNOSTIC.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({dates:days.length,summary,promotable:false}));
