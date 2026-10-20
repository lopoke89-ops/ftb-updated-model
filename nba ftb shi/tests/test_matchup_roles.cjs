const assert=require('node:assert/strict'),M=require('../matchup.js'),data=require('../analyst_data.json'),roles=require('../parlay_data.json').datedRoleEvidence;
const before=JSON.stringify(data),enriched=M.withHistoricalRoles({...data,roleEvidence:roles});let count=0;
for(const g of enriched.games)for(const [team,box] of Object.entries(g.teams))for(const p of box.players)if(p.verifiedFivePosition){count++;const old=data.games.find(x=>x.id===g.id).teams[team].players.find(x=>x.id===p.id);assert.equal(M.position(p,'broad'),M.position(old,'broad'));assert.equal(M.position(p,'strict'),p.verifiedFivePosition);assert(p.starter&&p.played);}
assert.equal(count,roles.length);assert.equal(JSON.stringify(data),before);
const one=roles[0],broken=roles.map(r=>r===one?{...r,gamebookSourceHash:'bad'}:r),bad=M.withHistoricalRoles({...data,roleEvidence:broken});assert(!bad.games.find(g=>g.id===one.gameId).teams[one.team].players.some(p=>p.verifiedFivePosition));
console.log('PASS '+count+' historical starter roles; broad totals preserved, invalid role set rejected, source unchanged');
