'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),base=path.resolve(__dirname,'../nba ftb shi'),P=require(path.join(base,'parlay.js'));
const data=JSON.parse(fs.readFileSync(path.join(base,'analyst_data.json'))),expected=JSON.parse(fs.readFileSync(process.argv[2])),groups=new Map();let comparisons=0;
for(const g of data.games)for(const box of Object.values(g.teams))for(const p of box.players)if(p.played){const key=g.phase+'|'+p.id,rows=groups.get(key)||[];rows.push(p);groups.set(key,rows);}
const near=(a,b,label)=>{comparisons++;if(a===null||b===null)assert.equal(a,b,label);else assert(Math.abs(a-b)<1e-9,label+': '+a+' vs '+b);};
for(const e of expected){const s=P.summarize(groups.get(e.phase+'|'+e.id)||[]);near(s.gp,e.gp,'GP');for(const key of Object.keys(s.total))near(s.total[key],e[key],key);
 for(const [key,total] of Object.entries({ppg:'points',fgm:'fgm',fga:'fga',threePm:'threeMade',threePa:'threeAttempted',ftm:'ftm',fta:'fta',rpg:'rebounds',apg:'assists',spg:'steals',bpg:'blocks',tov:'turnovers',pf:'fouls',oreb:'offensiveRebounds',dreb:'defensiveRebounds',plusMinus:'plusMinus'}))near(s[key],e[total]/e.gp,key);
 near(s.mpg,e.minutesSeconds/60/e.gp,'MPG');near(s.fgPct,e.fga?e.fgm/e.fga:null,'FG%');near(s.threePct,e.threeAttempted?e.threeMade/e.threeAttempted:null,'3P%');near(s.ftPct,e.fta?e.ftm/e.fta:null,'FT%');near(s.tsPct,e.fga+.44*e.fta?e.points/(2*(e.fga+.44*e.fta)):null,'TS%');
}
console.log(JSON.stringify({phasePlayerGroups:expected.length,statAggregateComparisons:comparisons,phases:[...new Set(expected.map(r=>r.phase))]}));
