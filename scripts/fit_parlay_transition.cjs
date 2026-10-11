'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const base=path.resolve(__dirname,'../nba ftb shi'),A=require(base+'/analyst.js'),H=require(base+'/scouting_history.js'),P=require(base+'/parlay.js');
const data=require(base+'/analyst_data.json'),extra=require(base+'/parlay_data.json');
const models=P.FIRST_TARGETS.map(firstBasketTarget=>P.build(A,H,data,extra,{mode:'pregame',date:'2025-12-16',phase:'regular-season',positionScope:'broad',firstBasketTarget}));
const tasks={};
function add(key,history,current,next,unit='games',binomial=false){
  if(!history.n||!next.n)return;const t=tasks[key]||(tasks[key]={unit,binomial,observations:[]});
  t.observations.push({prior:history.y/history.n,currentY:current.y,currentN:current.n,nextY:next.y,nextN:next.n});
}
function totals(rows,fn){return rows.reduce((a,r)=>{const v=fn(r);if(v&&Number.isFinite(v.y)&&Number.isFinite(v.n)){a.y+=v.y;a.n+=v.n;}return a;},{y:0,n:0});}
for(let targetIndex=0;targetIndex<models.length;targetIndex++){
  const m=models[targetIndex],games=Object.fromEntries(m.snapshot.games.map(g=>[g.id,g]));
  const suffix=targetIndex?'fg':'inclusive';
  for(const [id,p] of Object.entries(m.scope.byPlayer)){
    const series=p.all,functions={
      ...(!targetIndex?{minutes:r=>({y:r.minutesSeconds/60,n:1}),fga:r=>({y:r.fga,n:1}),threePa:r=>({y:r.threeAttempted,n:1}),
        fgConversion:r=>({y:r.fgm,n:r.fga}),threeConversion:r=>({y:r.threeMade,n:r.threeAttempted}),starting:r=>({y:+r.starter,n:1})}:{}),
      ['firstRate-'+suffix]:r=>({y:+(r.starter&&games[r.gameId][targetIndex?'firstFieldGoals':'firstScores'][r.team]?.id===id),n:+r.starter}),
      ['opening-'+suffix]:r=>{const e=games[r.gameId].opening[targetIndex?'firstFieldGoalAttempts':'firstAttempts']?.[r.team];return e?.athleteIds?.length===1?{y:+(e.athleteIds[0]===id),n:1}:null;}
    };
    for(let i=11;i<series.length;i++)for(const [key,fn] of Object.entries(functions)){
      add(key,totals(series.slice(0,10),fn),totals(series.slice(10,i),fn),totals([series[i]],fn),key.includes('Conversion')?'attempts':key.startsWith('firstRate')?'starts':'games',key.includes('Conversion')||key==='starting'||key.startsWith('firstRate')||key.startsWith('opening'));
    }
  }
  for(const team of Object.keys(m.scope.byTeam)){
    const series=m.snapshot.games.filter(g=>g.home===team||g.away===team);
    for(const market of P.MARKETS){if(targetIndex&&market!=='first-team-basket')continue;
      const key=market==='first-team-basket'?'first':market==='points'?'points':'threes';
      for(const allowed of [false,true])for(const group of ['G','F','C']){
        const fn=g=>{const side=allowed?(g.home===team?g.away:g.home):team,box=g.teams[side];
          if(key==='first'){const scorer=g[targetIndex?'firstFieldGoals':'firstScores'][side]?.id,actor=box.players.find(p=>p.id===scorer);return {y:+(P.positionGroup(actor||{},'broad')===group),n:1};}
          return box.players.filter(p=>p.played).reduce((a,p)=>{const n=p[key==='points'?'points':'threeMade'];a.n+=n;a.y+=P.positionGroup(p,'broad')===group?n:0;return a;},{y:0,n:0});};
        for(let i=11;i<series.length;i++)add('position-'+(key==='first'?'first-'+suffix:key),totals(series.slice(0,10),fn),totals(series.slice(10,i),fn),totals([series[i]],fn),key==='points'?'points':key==='threes'?'made-threes':'opening-events');
      }
    }
  }
}
const fit={};
for(const [key,t] of Object.entries(tasks)){
  const grid=t.unit==='points'?[50,100,250,500,1000,2000]:t.unit==='made-threes'?[10,25,50,100,200,400]:t.unit==='attempts'?[5,10,20,40,80,160]:[1,3,5,10,20,40];
  const losses=grid.map(strength=>({strength,loss:t.observations.reduce((loss,r)=>{const p=(r.prior*strength+r.currentY)/(strength+r.currentN);
    if(t.binomial){const q=Math.max(1e-9,Math.min(1-1e-9,p));return loss-r.nextY*Math.log(q)-(r.nextN-r.nextY)*Math.log(1-q);}
    return loss+(p-r.nextY/r.nextN)**2;},0)/t.observations.length}));
  const best=[...losses].sort((a,b)=>a.loss-b.loss||a.strength-b.strength)[0];
  if(!best||!Number.isFinite(best.loss))throw Error('Insufficient fitting data for '+key);
  fit[key]={...best,unit:t.unit,observations:t.observations.length,losses};
}
const config={version:'parlay-adaptive-v1',defaultEnabled:false,phase:'regular-season',status:'development-fitted; season-transfer unvalidated',developmentEnd:'2025-12-15',
  evidenceHash:data.meta.evidenceContentHash,developmentContentHash:crypto.createHash('sha256').update(JSON.stringify(models.map(m=>m.snapshot.games))).digest('hex'),
  fitScriptHash:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),method:'within-season prefix-10 pseudo-transition; next-observation loss',strengths:fit};
config.configurationHash=crypto.createHash('sha256').update(JSON.stringify(config)).digest('hex');
fs.writeFileSync(base+'/parlay_research_config.json',JSON.stringify(config,null,2)+'\n');
fs.writeFileSync(base+'/parlay_research_config.js','window.__FTB_PARLAY_RESEARCH_CONFIG__ = '+JSON.stringify(config)+';\n');
console.log(JSON.stringify({configurationHash:config.configurationHash,parameters:Object.keys(fit).length,observations:Object.values(fit).reduce((n,p)=>n+p.observations,0)}));
