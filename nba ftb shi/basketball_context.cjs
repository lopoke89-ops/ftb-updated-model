/* Descriptive dated context. These additional features do not alter the frozen model. */
function context(data,fixture,team){
  const games=data.games.filter(g=>g.date<fixture.date&&(g.home===team||g.away===team)).sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id));
  const opponent=fixture.home===team?fixture.away:fixture.home,last=games.at(-1),previous=games.at(-2);
  const starters=last?.teams[team]?.starters||[],older=previous?.teams[team]?.starters||[];
  const opponentGames=data.games.filter(g=>g.date<fixture.date&&(g.home===opponent||g.away===opponent));
  const allowedShots={};for(const g of opponentGames){const other=g.home===opponent?g.away:g.home;const shot=g.firstScores[other]?.shot||'unknown';allowedShots[shot]=(allowedShots[shot]||0)+1;}
  const sameOpponent=games.filter(g=>g.home===opponent||g.away===opponent),series=sameOpponent.filter(g=>g.phase==='playoffs'&&fixture.phase==='playoffs');
  return {fixtureId:fixture.id,team,opponent,home:fixture.home===team,priorTeamGames:games.length,lastGameDate:last?.date||null,
    restDays:last?Math.max(0,(Date.parse(fixture.date)-Date.parse(last.date))/86400000-1):null,
    priorLineup:starters,priorLineupDate:last?.date||null,starterContinuity:older.length===5?starters.filter(id=>older.includes(id)).length/5:null,
    priorHeadToHeadGames:sameOpponent.length,priorPlayoffSeriesGames:series.length,
    opponentFirstScoreAllowedByShot:allowedShots,opponentAllowedSample:opponentGames.length,
    lineupConfirmation:'unavailable',historicalInjuries:'unavailable',coachChanges:'unavailable',travel:'unavailable',
    availability:'previous Chicago dates only; source publication history unavailable',modelUse:'descriptive research only'};
}
module.exports={context};
if(require.main===module){
  const fs=require('node:fs'),path=require('node:path'),A=require('./analyst.js'),data=JSON.parse(fs.readFileSync(path.join(__dirname,'analyst_data.json'))),canonical=JSON.parse(fs.readFileSync(path.join(__dirname,'merged_dataset.json'))),out=path.join(__dirname,'../implementation_2026-10-04');
  const rows=data.games.flatMap(g=>[g.home,g.away].map(t=>context(data,g,t)));
  fs.writeFileSync(path.join(out,'dated_basketball_context.jsonl'),rows.map(r=>JSON.stringify(r)).join('\n')+'\n');
  const conflicts=[];for(const g of data.games)for(const [team,b] of Object.entries(g.teams))for(const p of b.players){const ref=Object.values(canonical.players).find(c=>String(c.sourcePlayerId)===p.id);const role=A.positionRecord(p.rawPosition,ref);if(role.positionConflict)conflicts.push({fixtureId:g.id,date:g.date,team,playerId:p.id,name:p.name,raw:p.rawPosition,seasonReference:role.referencePosition,policy:'dated raw/source conflicts retained; no scoring identity change'});}
  const sourceCounts={teamEvents:2644,openingScoringAttempts:data.games.reduce((n,g)=>n+Object.keys(g.opening.firstAttempts).length,0),firstFieldGoalAttempts:data.games.reduce((n,g)=>n+Object.keys(g.opening.firstFieldGoalAttempts).length,0),explicitFirstPossessionGames:data.games.filter(g=>g.opening.firstPossessionTeam).length,openingLedgerSubstitutionGames:data.games.filter(g=>g.opening.substitutionsBeforeFirstScores.length).length,specialOpeningEventGames:data.games.filter(g=>g.opening.specialEvents.length).length,priorGameRestSamples:rows.filter(r=>r.restDays!==null).length,priorStarterContinuitySamples:rows.filter(r=>r.starterContinuity!==null).length};
  const drift={};for(const [label,start,end] of [['development','2025-10-21','2026-02-28'],['calibration','2026-03-01','2026-03-31'],['test','2026-04-01','2026-06-13']]){const gs=data.games.filter(g=>g.date>=start&&g.date<=end);const scores=gs.flatMap(g=>Object.values(g.firstScores));drift[label]={games:gs.length,teamEvents:scores.length,ftShare:scores.filter(s=>s.shot==='ft').length/scores.length,canonicalUnknownPositions:scores.filter(s=>!A.POS.includes(s.position)).length,explicitPossessionCoverage:gs.filter(g=>g.opening.firstPossessionTeam).length/gs.length};}
  fs.writeFileSync(path.join(out,'feature_coverage.json'),JSON.stringify({sourceCounts,drift,interpretation:'Descriptive source/feature drift; sparse phases and lineup combinations do not establish a causal or predictive effect'},null,2));
  fs.writeFileSync(path.join(out,'position_conflicts.json'),JSON.stringify({events:conflicts.length,players:new Set(conflicts.map(r=>r.playerId)).size,records:conflicts},null,2));
  console.log(JSON.stringify({sourceCounts,roleConflictRows:conflicts.length}));
}
