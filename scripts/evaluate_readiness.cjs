'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const app=path.resolve(__dirname,'../nba ftb shi'),A=require(app+'/analyst.js'),H=require(app+'/scouting_history.js'),P=require(app+'/parlay.js');
const read=n=>JSON.parse(fs.readFileSync(app+'/'+n,'utf8')),hash=n=>crypto.createHash('sha256').update(fs.readFileSync(app+'/'+n)).digest('hex');
const data=read('analyst_data.json'),extra=read('parlay_data.json'),protocol=read('readiness_evaluation_protocol.json');
const records=[],models=new Map(),days=[...new Set(data.games.map(g=>g.date))].sort();
function pickBy(rows,key){return [...rows].sort((a,b)=>(key(b)||0)-(key(a)||0)||b.stats.gp-a.stats.gp||a.id.localeCompare(b.id))[0]||null;}
function settle(g,team,market,p,target){
  if(!p)return null;
  const actual=g.teams[team].players.find(r=>String(r.id)===p.id),played=!!actual?.played;
  const threshold=market==='first-team-basket'?null:Math.ceil((market==='points'?p.seasonStats.ppg:p.seasonStats.threePm)-1e-10);
  const scorer=(target===P.FIRST_TARGETS[1]?g.firstFieldGoals:g.firstScores)?.[team]?.id;
  const hit=market==='first-team-basket'?scorer===p.id:played&&actual[market==='points'?'points':'threeMade']>=threshold;
  return {id:p.id,hit:!!hit,played,threshold,score:p.score,qualityFactor:p.qualityFactor,statsThrough:p.rows.at(-1)?.date,playerGames:p.stats.gp,
    tradedHistory:!!p.hasTradeHistory};
}
let done=0;
for(const day of days){
  models.clear();
  for(const g of data.games.filter(g=>g.date===day&&['regular-season','playoffs'].includes(g.phase))){
    for(const target of P.FIRST_TARGETS){
      const key=g.phase+'|'+target;
      if(!models.has(key))models.set(key,Object.fromEntries(['specific','broad'].map(positionScope=>[positionScope,P.build(A,H,data,extra,{date:day,mode:'pregame',phase:g.phase,firstBasketTarget:target,positionScope})])));
      const pair=models.get(key),model=pair.specific;
      for(const team of [g.home,g.away]){
        const opponent=team===g.home?g.away:g.home,options={team,opponent,roster:model.snapshot.rosters[team]||[],snapshot:model.snapshot,sample:model.scope};
        const variants=Object.fromEntries(protocol.playerGameCandidates.map(minimumGames=>[minimumGames,{full:P.rankPositionVariants(pair,{...options,minimumGames}),noCorrelation:P.rankPositionVariants(pair,{...options,minimumGames,variant:'no-correlation'})}]));
        const full=variants[5].full;
        for(const slot of full){
          if(target===P.FIRST_TARGETS[1]&&slot.market!=='first-team-basket')continue;
          const market=slot.market,candidates=variants[5].noCorrelation.find(s=>s.market===market).ranked;
          const seasonKey=market==='threes'?'threePm':'ppg',volumeKey=market==='threes'?'threePa':'fga';
          const base=market==='first-team-basket'?pickBy(slot.ranked,p=>p.firstQuality.share):pickBy(candidates,p=>p.stats[volumeKey]);
          const meanBase=market==='first-team-basket'?pickBy(slot.ranked,p=>p.rawScore):pickBy(candidates,p=>p.seasonStats[seasonKey]);
          const withoutPosition=pickBy(slot.ranked,p=>p.components.opportunity*p.qualityFactor);
          const actualStarters=new Set(g.teams[team].starters.map(String));
          const conditional=market==='first-team-basket'?slot.ranked.find(p=>actualStarters.has(p.id)):null;
          const rankingsByMinimum=Object.fromEntries(protocol.playerGameCandidates.map(minimum=>{
            const fullSlot=variants[minimum].full.find(s=>s.market===market),pool=variants[minimum].noCorrelation.find(s=>s.market===market).ranked;
            return [minimum,{positionScope:fullSlot.positionScope,selectionCoverageReady:P.applySelectionPolicy(fullSlot,{scope:fullSlot.evidenceModel.scope}).selectionReview.coverageReady,ranked:fullSlot.ranked.map(p=>settle(g,team,market,p,target)),
              baseline:settle(g,team,market,market==='first-team-basket'?pickBy(fullSlot.ranked,p=>p.firstQuality.share):pickBy(pool,p=>p.stats[volumeKey]),target),
              meanBaseline:settle(g,team,market,market==='first-team-basket'?pickBy(fullSlot.ranked,p=>p.rawScore):pickBy(pool,p=>p.seasonStats[seasonKey]),target),
              noPosition:settle(g,team,market,pickBy(fullSlot.ranked,p=>p.components.opportunity*p.qualityFactor),target),
              noCorrelation:settle(g,team,market,pool[0],target),conditional:settle(g,team,market,market==='first-team-basket'?fullSlot.ranked.find(p=>actualStarters.has(p.id)):null,target)}];
          }));
          records.push({gameId:g.id,date:day,phase:g.phase,team,opponent,market,target,
            rankingsByMinimum,
            positionScope:slot.positionScope,positionFallbackReason:slot.positionFallbackReason,
            selectionCoverageReady:P.applySelectionPolicy(slot,{scope:slot.evidenceModel.scope}).selectionReview.coverageReady,
            positionCoverage:{roster:(model.snapshot.rosters[team]||[]).length,known:(model.snapshot.rosters[team]||[]).filter(p=>P.positionGroup(model.snapshot.players[p.id]||p)!=='unknown').length,unknownPointsFraction:(model.scope.byTeam[team]?.points.unknown||0)/(model.scope.byTeam[team]?.totals.points||1)},
            teamGames:model.scope.byTeam[team]?.games||0,opponentGames:model.scope.byTeam[opponent]?.games||0,
            rosterCoverage:(model.snapshot.rosters[team]||[]).some(p=>p.id===(g.firstScores?.[team]?.id)),
            ranked:slot.ranked.map(p=>settle(g,team,market,p,target)),
            baseline:settle(g,team,market,base,target),meanBaseline:settle(g,team,market,meanBase,target),
            noPosition:settle(g,team,market,withoutPosition,target),noCorrelation:settle(g,team,market,candidates[0],target),
            conditional:settle(g,team,market,conditional,target)});
        }
      }
    }
  }
  if(++done%25===0)console.log('Evaluated',done,'of',days.length,'dates');
}
function choose(r,rule){return r.teamGames>=rule.teamGames&&r.opponentGames>=rule.teamGames?(r.rankingsByMinimum?.[rule.playerGames]||r).ranked.find(p=>p.playerGames>=rule.playerGames)||null:null;}
function baselineChoice(r,rule,key){return r.teamGames>=rule.teamGames&&r.opponentGames>=rule.teamGames?(r.rankingsByMinimum?.[rule.playerGames]||r)[key]||null:null;}
function metrics(rows,selector){
  const picks=rows.map(selector).filter(Boolean),hits=picks.filter(p=>p.hit).length,played=picks.filter(p=>p.played),n=picks.length;
  return {opportunities:rows.length,selections:n,coverage:rows.length?n/rows.length:0,hits,hitRate:n?hits/n:null,
    descriptive95Interval:A.wilson(hits,n),didNotPlay:picks.filter(p=>!p.played).length,
    participatingSelections:played.length,participatingHitRate:played.length?played.filter(p=>p.hit).length/played.length:null};
}
let seed=protocol.bootstrapSeed;function random(){seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;}
function paired(rows,rule,baseline){
  const grouped=new Map(),weeks=new Map();
  for(const r of rows){const p=choose(r,rule),b=baselineChoice(r,rule,baseline);if(!p||!b)continue;
    const difference=Number(p.hit)-Number(b.hit),v=grouped.get(r.gameId)||[];v.push(difference);grouped.set(r.gameId,v);
    const week=Math.floor(Date.parse(r.date)/604800000),w=weeks.get(week)||[];w.push(difference);weeks.set(week,w);}
  const blocks=[...grouped.values()].map(v=>v.reduce((a,b)=>a+b,0)/v.length);
  if(!blocks.length)return {fixtures:0,meanDifference:null,fixtureBootstrap95Interval:null};
  const draws=[];for(let i=0;i<protocol.bootstrapReplicates;i++){let n=0;for(let j=0;j<blocks.length;j++)n+=blocks[Math.floor(random()*blocks.length)];draws.push(n/blocks.length);}
  draws.sort((a,b)=>a-b);
  const weekly=[...weeks.values()],weeklyDraws=[];
  for(let i=0;i<protocol.bootstrapReplicates;i++){let hits=0,n=0;for(let j=0;j<weekly.length;j++){const block=weekly[Math.floor(random()*weekly.length)];hits+=block.reduce((a,b)=>a+b,0);n+=block.length;}weeklyDraws.push(hits/n);}weeklyDraws.sort((a,b)=>a-b);
  return {fixtures:blocks.length,meanDifference:blocks.reduce((a,b)=>a+b,0)/blocks.length,
    fixtureBootstrap95Interval:[draws[Math.floor(draws.length*.025)],draws[Math.floor(draws.length*.975)]],
    weeklyBlock95Interval:[weeklyDraws[Math.floor(weeklyDraws.length*.025)],weeklyDraws[Math.floor(weeklyDraws.length*.975)]]};
}
const thresholds={},development={};
for(const market of P.MARKETS){
  const rows=records.filter(r=>r.market===market&&r.target===P.FIRST_TARGETS[0]&&r.phase==='regular-season'&&r.date<=protocol.developmentEnd);
  const base=metrics(rows,r=>choose(r,{teamGames:5,playerGames:5})),grid=[];
  for(const teamGames of protocol.teamGameCandidates)for(const playerGames of protocol.playerGameCandidates){
    const rule={teamGames,playerGames},m=metrics(rows,r=>choose(r,rule));grid.push({rule,...m,qualifies:m.selections>=protocol.minimumDevelopmentCoverageFraction*base.selections});
  }
  const selected=grid.filter(x=>x.qualifies&&x.selections).sort((a,b)=>b.descriptive95Interval[0]-a.descriptive95Interval[0]||a.rule.teamGames-b.rule.teamGames||a.rule.playerGames-b.rule.playerGames)[0];
  if(!selected)throw Error('No supported development threshold for '+market);
  thresholds[market]=selected.rule;development[market]={selected,grid};
}
const test={};
for(const phase of ['regular-season','playoffs'])for(const market of P.MARKETS)for(const target of market==='first-team-basket'?P.FIRST_TARGETS:[P.FIRST_TARGETS[0]]){
  const rows=records.filter(r=>r.market===market&&r.phase===phase&&r.target===target&&r.date>=protocol.testStart),rule=thresholds[market];
  test[phase+'|'+market+'|'+target]={policy:metrics(rows,r=>choose(r,rule)),baseline:metrics(rows,r=>baselineChoice(r,rule,'baseline')),
    issuedPolicy:metrics(rows,r=>(r.rankingsByMinimum?.[rule.playerGames]||r).selectionCoverageReady?choose(r,rule):null),
    seasonAverageOrLegacyBaseline:metrics(rows,r=>baselineChoice(r,rule,'meanBaseline')),withoutPosition:metrics(rows,r=>baselineChoice(r,rule,'noPosition')),withoutCorrelation:metrics(rows,r=>baselineChoice(r,rule,'noCorrelation')),
    pairedVsBaseline:paired(rows,rule,'baseline'),pairedVsNoPosition:paired(rows,rule,'noPosition'),pairedVsNoCorrelation:paired(rows,rule,'noCorrelation'),
    tradeHistorySelections:metrics(rows.filter(r=>choose(r,rule)?.tradedHistory),r=>choose(r,rule)),
    ...(market==='first-team-basket'?{conditionalKnownEventualStarters:metrics(rows,r=>baselineChoice(r,rule,'conditional'))}:{})};
}
const early={};for(const market of P.MARKETS){const rows=records.filter(r=>r.market===market&&r.target===P.FIRST_TARGETS[0]&&r.phase==='regular-season'&&Math.min(r.teamGames,r.opponentGames)<20);
  early[market]={policy:metrics(rows,r=>choose(r,thresholds[market])),atFiveGames:metrics(rows,r=>choose(r,{teamGames:5,playerGames:5})),priorSeasonFallbackPerformance:'Unavailable: no verified 2024-25 archive. Fallback is labeled descriptive history, not a validated cross-season forecast.'};}
const report={version:protocol.version,generatedAt:new Date().toISOString(),protocol,thresholds,development,test,early,
  selectionQualityPolicy:P.SELECTION_POLICY,positionScopePolicy:'Automatic: specific positions where supported; otherwise G/F/C for both teams in that market.',
  evaluationScope:'Historical policy and baseline rows are conditional ranking diagnostics before the 80% positional completeness safeguard. issuedPolicy reports selections that pass the safeguard. Historical injury and starter-confirmation limitations remain; these are not prospectively issued forecasts.',
  positionEvidence:{limitation:'Pregame tests exclude later canonical season-role references. Specific roles are dated postgame NBA observations matched to all five PDF starters; the latest earlier observation can support later games but does not prove an exact bench role or a historical pregame announcement. Automatic comparisons fall back to gamebook G/F/C groups for both teams when specific coverage is incomplete. Cross-season performance is unvalidated.',datedRoleRecords:data.datedRoleEvidence.length+(extra.datedRoleEvidence?.length||0),
    broadComparisonRecords:records.filter(r=>r.positionScope==='broad').length,totalComparisonRecords:records.length,
    meanKnownRosterFraction:records.reduce((n,r)=>n+(r.positionCoverage.roster?r.positionCoverage.known/r.positionCoverage.roster:0),0)/records.length,
    meanUnknownPointsFraction:records.reduce((n,r)=>n+r.positionCoverage.unknownPointsFraction,0)/records.length},
  sourceHashes:Object.fromEntries(['analyst_data.json','parlay_data.json','analyst.js','scouting_history.js','parlay.js','readiness_evaluation_protocol.json'].map(n=>[n,hash(n)])),
  evaluatorHash:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
  conclusion:'Readiness thresholds describe retrospective sample adequacy. Equal market weights retained; no calibrated matchup or joint probabilities claimed. Non-positive/constant correlations remain excluded by the user requirement even if ablations do not show an improvement.'};
const raw=JSON.stringify(report,null,2)+'\n';fs.writeFileSync(app+'/readiness_evaluation.json',raw);fs.writeFileSync(app+'/readiness_evaluation.js','window.__FTB_READINESS_REPORT__ = '+JSON.stringify(report)+';\n');
const policy={version:'opening-readiness-v1',status:'retrospective-selected',thresholds,evaluationHash:crypto.createHash('sha256').update(raw).digest('hex'),
  interpretation:'2025-26 chronological retrospective selection; cross-season transfer unvalidated. Prior seasons stay separate.'};
fs.writeFileSync(app+'/readiness_policy.json',JSON.stringify(policy,null,2)+'\n');fs.writeFileSync(app+'/readiness_policy.js','window.__FTB_READINESS__ = '+JSON.stringify(policy)+';\n');
const fmt=v=>Number.isFinite(v)?(100*v).toFixed(1)+'%':'Unavailable';
const lines=['# Opening-night readiness evaluation','',report.evaluationScope,'','## Selected sample minimums','',
  '| Market | Games for each team | Player appearances |','|---|---:|---:|',...P.MARKETS.map(m=>`| ${m} | ${thresholds[m].teamGames} | ${thresholds[m].playerGames} |`),'',
  'First Basket also requires five starts and the shared capped scoring-share grade. Points and Threes require positive attempts/makes correlation. All production selections require at least 80% known positional production on both sides at the displayed resolution. Automatic mode uses specific roles where supported and otherwise compares G/F/C for both teams; strict five-position mode remains available. That completeness safeguard is operational, not a fitted predictive threshold.','',
  '## Chronological later-date results','',`Development ends ${protocol.developmentEnd}; later evaluation starts ${protocol.testStart}. Each sample-minimum variant recomputes normalization using its own eligible candidates. Baselines use the same team/player sample minimums. Historical DNPs count as misses; participating-player results are retained separately.`,'',
  '| Competition / market / target | Conditional rankings | Hit rate | Baseline rate | Rankings passing positional coverage |','|---|---:|---:|---:|---:|',
  ...Object.entries(test).map(([k,r])=>`| ${k.replaceAll('|',' / ')} | ${r.policy.selections} / ${r.policy.opportunities} | ${fmt(r.policy.hitRate)} | ${fmt(r.baseline.hitRate)} | ${r.issuedPolicy.selections} |`),'',
  'Aggregate baseline coverage can differ. The paired fixture and weekly-block comparisons in the JSON report assess improvement on common games. The same corrected archive was already inspected; these are retrospective diagnostics and do not establish an unseen live advantage.','',
  '## Position evidence','',`The archive now contains ${report.positionEvidence.datedRoleRecords} dated role records. NBA role files matched 2,642 of 2,644 PDF team starting fives. The two unmatched team lineups are retained as unresolved. Mean known candidate-roster fraction in the test is ${fmt(report.positionEvidence.meanKnownRosterFraction)}; mean unknown specific-position points production is ${fmt(report.positionEvidence.meanUnknownPointsFraction)}. Automatic G/F/C comparisons account for ${report.positionEvidence.broadComparisonRecords} of ${report.positionEvidence.totalComparisonRecords} market records.`, '',report.positionEvidence.limitation,'',
  'PDF final statistics and opening events remain authoritative. Exact PDF positions take precedence. Earlier NBA role observations may be carried forward to later appearances; they do not establish exact bench roles.','',
  '## Remaining limits','',
  '- Historical injury and pregame lineup announcements are unavailable. Eventual actual starters appear only in a separately labeled conditional analysis.',
  '- A verified 2024–25 archive is unavailable; cross-season fallback performance is unvalidated.',
  '- The equal one-third components and positive-correlation requirement remain. Evidence scores do not estimate the probability of reaching a season-average target.',
  '- Prospective timestamped selections are needed to assess the deployed workflow.','',
  '## Reproduce','', '```sh','node scripts/evaluate_readiness.cjs','node "nba ftb shi/tests/test_parlay.cjs"','python scripts/build_pages.py','```','',
  'Full results, development grids, ablations, coverage and uncertainty are in `nba ftb shi/readiness_evaluation.json`.',''];
fs.writeFileSync(path.resolve(app,'../READINESS_EVALUATION.md'),lines.join('\n'));
const output=process.argv[2];if(output){fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'event_results.json'),JSON.stringify(records));}
console.log(JSON.stringify({thresholds,test,early},null,2));
