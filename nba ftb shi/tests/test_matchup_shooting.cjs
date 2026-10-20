const assert=require('node:assert/strict'),M=require('../matchup.js');
const p=(id,stats)=>({id,rawPosition:'G',played:true,minutesSeconds:600,statsSource:'https://stats.nba.com/pdfs/a.pdf',statsSourceHash:'a'.repeat(64),points:0,threes:0,...stats});
const game={id:'g',date:'2026-01-01',phase:'regular-season',home:'A',away:'B',teams:{A:{players:[p('1',{fgm:1,fga:2,threeMade:1,threeAttempted:1,ftm:0,fta:0}),p('2',{fgm:9,fga:18,threeMade:0,threeAttempted:9,ftm:2,fta:3})]},B:{players:[p('3',{fgm:0,fga:0,threeMade:0,threeAttempted:0,ftm:0,fta:0})]}}};
const a=M.aggregate([game],'A',{positions:'broad'}),b=M.aggregate([game],'B',{positions:'broad'}),d={production:a,allowance:b,positions:'broad'};
const r=M.shootingRows(d)[0];assert.equal(r.production['3P'].percentage,10);assert.equal(r.production.FG.percentage,50);assert.equal(r.production.FT.percentage,200/3);assert.equal(M.shootingRows({production:b,allowance:a,positions:"broad"})[0].production.FG.percentage,null);assert.equal(a.own.threes.total,1);
game.teams.A.players[0].fga=null;const missing=M.aggregate([game],'A',{positions:'broad'});assert.equal(M.shootingRows({...d,production:missing})[0].production.FG.percentage,null);assert.equal(missing.own.points.total,0);
const changed={...game,id:'later',date:'2026-01-03'};assert.deepEqual(M.eligibleGames({meta:{season:'2025-26'},games:[game,changed]},{date:'2026-01-03',mode:'pregame',phase:'all'}).map(g=>g.id),['g']);
console.log('PASS pooled shooting, zero attempts, paired missing counts, box independence, pregame cutoff');
