/* Transparent market rankings. Scores are descriptive, never win probabilities. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.FTBParlay=factory();})(typeof window!=='undefined'?window:this,function(){
  'use strict';
  const MARKETS=['first-team-basket','points','threes'];
  const LABELS={'first-team-basket':'First Team Basket',points:'Points',threes:'Three-Pointers Made'};
  const WEIGHTS={offense:1/3,defense:1/3,opportunity:1/3};
  const MIN_GAMES=5;
  const FIRST_TARGETS=['first-team-score-including-free-throws','first-team-made-field-goal'];
  const sum=(xs,key)=>xs.reduce((n,p)=>n+(Number.isFinite(p[key])?p[key]:0),0);
  function correlation(rows,x,y){
    const paired=rows.filter(r=>Number.isFinite(r[x])&&Number.isFinite(r[y]));
    if(paired.length<MIN_GAMES)return {n:paired.length,r:null,reason:`Needs ${MIN_GAMES} paired games`};
    const mx=sum(paired,x)/paired.length,my=sum(paired,y)/paired.length;
    let xx=0,yy=0,xy=0;for(const p of paired){const a=p[x]-mx,b=p[y]-my;xx+=a*a;yy+=b*b;xy+=a*b;}
    return {n:paired.length,r:xx&&yy?Math.max(-1,Math.min(1,xy/Math.sqrt(xx*yy))):null,reason:xx&&yy?null:'No variation in attempts or makes'};
  }
  // Use only verified specific roles. Broad G/F labels cannot become PG/SG or SF/PF.
  function positionGroup(p){const pos=p.position||p.rawPosition||'',raw=String(p.rawPosition||pos).toUpperCase();
    if(['PG','SG','SF','PF','C'].includes(pos))return pos;
    return ['PG','SG','SF','PF','C'].includes(raw)?raw:raw==='CENTER'?'C':'unknown';
  }
  function shootingRow(game,team,p,supplement,valid){
    if(game.boxScoreSource==='NBA official final box'&&!valid)return null;
    const extra=valid?supplement.games?.[game.id]?.[team]?.[p.id]:null;
    // Newly collected seasons carry these fields directly. Older/mismatched supplements cannot fill them.
    const row={...p,...(extra||{})};
    for(const k of ['points','fga','fgm','threeMade','threeAttempted','ftm','fta'])if(!Number.isFinite(row[k])||row[k]<0)return null;
    if(row.fgm>row.fga||row.threeMade>row.threeAttempted||row.threeMade>row.fgm||row.threeAttempted>row.fga||row.ftm>row.fta||2*row.fgm+row.threeMade+row.ftm!==row.points)return null;
    return row;
  }
  function summarize(rows){
    const gp=rows.length,total=Object.fromEntries(['points','fga','fgm','threeMade','threeAttempted','ftm','fta'].map(k=>[k,sum(rows,k)]));
    for(const k of ['rebounds','assists','steals','blocks','turnovers','fouls','offensiveRebounds','defensiveRebounds','plusMinus'])total[k]=gp&&rows.every(r=>Number.isFinite(r[k]))?sum(rows,k):null;
    const minutes=rows.filter(r=>Number.isFinite(r.minutes));
    const exactMinutes=gp&&rows.every(r=>Number.isFinite(r.minutesSeconds))?sum(rows,'minutesSeconds')/60:null;
    const average=k=>gp&&Number.isFinite(total[k])?total[k]/gp:null;
    return {gp,total,ppg:gp?total.points/gp:null,fgm:gp?total.fgm/gp:null,fga:gp?total.fga/gp:null,
      threePm:gp?total.threeMade/gp:null,threePa:gp?total.threeAttempted/gp:null,ftm:gp?total.ftm/gp:null,
      fgPct:total.fga?total.fgm/total.fga:null,threePct:total.threeAttempted?total.threeMade/total.threeAttempted:null,
      fta:gp?total.fta/gp:null,ftPct:total.fta?total.ftm/total.fta:null,
      tsPct:total.fga+.44*total.fta?total.points/(2*(total.fga+.44*total.fta)):null,
      rpg:average('rebounds'),apg:average('assists'),spg:average('steals'),bpg:average('blocks'),
      tov:average('turnovers'),pf:average('fouls'),oreb:average('offensiveRebounds'),dreb:average('defensiveRebounds'),plusMinus:average('plusMinus'),
      mpg:exactMinutes!==null?exactMinutes/gp:minutes.length?sum(minutes,'minutes')/minutes.length:null,minutesGames:minutes.length,
      fgCorrelation:correlation(rows,'fga','fgm'),threeCorrelation:correlation(rows,'threeAttempted','threeMade')};
  }
  function sample(snapshot,supplement){
    const valid=supplement?.meta?.parentEvidenceContentHash===snapshot.evidenceHash;
    const byPlayer={},byTeam={},positions={};
    for(const g of snapshot.games)for(const team of snapshot.gameTeams[g.id]||[]){
      const t=byTeam[team]||(byTeam[team]={games:0,points:{},threes:{},first:{},allowedPoints:{},allowedThrees:{},allowedFirst:{},totals:{points:0,threes:0,first:0,allowedPoints:0,allowedThrees:0,allowedFirst:0},missing:0});t.games++;
      const opp=team===g.home?g.away:g.home;
      for(const [side,box] of [[team,g.teams[team]],[opp,g.teams[opp]]]){
        const own=side===team;
        for(const p of box.players){if(!p.played)continue;
          const role=snapshot.players[p.id]||p,group=positionGroup(role),row=shootingRow(g,side,p,supplement,valid);
          const prefix=own?'':'allowed';
          for(const [key,value] of [['points',p.points],['threes',p.threeMade]]){const field=own?key:prefix+key[0].toUpperCase()+key.slice(1);t[field][group]=(t[field][group]||0)+(value||0);t.totals[field]+=value||0;}
          if(own){const id=String(p.id),entry=byPlayer[id]||(byPlayer[id]={all:[],teams:{},appearances:0,missing:0,firstEvents:[],firstFieldGoalEvents:[]});entry.appearances++;if(row){entry.all.push({...row,team,date:g.date,gameId:g.id,starter:p.starter});(entry.teams[team]||(entry.teams[team]=[])).push({...row,team,date:g.date,gameId:g.id,starter:p.starter});}else{entry.missing++;t.missing++;}positions[id]=group;}
        }
        const first=(snapshot.meta.target==='first-team-made-field-goal'?g.firstFieldGoals:g.firstScores)?.[side];if(first){const actor=box.players.find(p=>String(p.id)===String(first.id));const group=positionGroup(snapshot.players[first.id]||actor||{}),field=own?'first':'allowedFirst';t[field][group]=(t[field][group]||0)+1;t.totals[field]++;}
        if(own&&snapshot.openingVerified){const record=e=>({...e,team,date:g.date,gameId:g.id,source:g.opening.sourceUrl,sourceHash:g.opening.sourceHash});
          if(first&&byPlayer[first.id])byPlayer[first.id].firstEvents.push(record(first));
          const fg=g.firstFieldGoals?.[side];if(fg&&byPlayer[fg.id])byPlayer[fg.id].firstFieldGoalEvents.push(record(fg));}
      }
    }
    return {byPlayer,byTeam,positions,supplementValid:valid,openingVerified:!!snapshot.openingVerified};
  }
  function lineDecision(rows,market,line){
    if(!Number.isFinite(line)||line<0)return {line:null,side:null,status:'Market line unavailable'};
    const key=market==='points'?'points':'threeMade',mean=sum(rows,key)/rows.length,side=mean>line?'Over':mean<line?'Under':null;
    return {line,side,status:side?'Historical mean comparison · price/value unassessed':'No directional edge at this line',
      over:rows.filter(r=>r[key]>line).length,under:rows.filter(r=>r[key]<line).length,push:rows.filter(r=>r[key]===line).length,n:rows.length};
  }
  function seasonDecision(rows,market,stats){
    const key=market==='points'?'points':'threeMade',average=market==='points'?stats.ppg:stats.threePm;
    if(!Number.isFinite(average)||!rows.length)return {average:null,threshold:null,n:0,hits:0,rate:null};
    const threshold=Math.ceil(average-1e-10),hits=rows.filter(r=>r[key]>=threshold).length;
    return {average,threshold,n:rows.length,hits,rate:hits/rows.length};
  }
  function rankTeam({team,opponent,roster=[],snapshot,sample:scope,seasonScope=scope,acrossStints=false,lines={},excludedIds=[],trusted=true}){
    const t=scope.byTeam[team],def=opponent?scope.byTeam[opponent]:null,excluded=new Set(excludedIds.map(String));
    const candidates=roster.filter(p=>!excluded.has(String(p.id))).map(p=>{
      const source=scope.byPlayer[String(p.id)],rows=acrossStints?source?.all||[]:source?.teams[team]||[],stats=summarize(rows),group=positionGroup({...snapshot.players[p.id],...p,position:snapshot.players[p.id]?.position});
      const detail=snapshot.players[p.id]?.ftbByTeam||{},details=acrossStints?Object.values(detail):[detail[team]||{}];
      const count=k=>details.reduce((n,d)=>n+(d[k]||0),0),starts=count('starts'),wins=count('starterWins'),openingSample=count('openingSample');
      const fieldGoalOnly=snapshot.meta.target==='first-team-made-field-goal',firstEvents=(source?.firstEvents||[]).filter(e=>acrossStints||e.team===team),firstFieldGoalEvents=(source?.firstFieldGoalEvents||[]).filter(e=>acrossStints||e.team===team);
      return {id:String(p.id),name:p.name,team,group,rows,stats,starts,wins,startRate:starts?wins/starts:null,
        seasonStats:summarize(seasonScope.byPlayer[String(p.id)]?.all||[]),firstEvents,firstFieldGoalEvents,
        openingRate:fieldGoalOnly?(count('firstFgSample')?count('firstFgAttempts')/count('firstFgSample'):null):openingSample?count('openingAttempts')/openingSample:null,openingSample:fieldGoalOnly?count('firstFgSample'):openingSample,
        missing:acrossStints?source?.missing||0:Math.max(0,(detail[team]?.gp||0)-rows.length),
        lineup:snapshot.lastLineups[team]?.ids?.includes(String(p.id))?'Previous lineup · unconfirmed':'Starter status unconfirmed'};
    });
    const max=k=>Math.max(1,...candidates.map(p=>p.stats[k]||0));
    const maximum={fga:max('fga'),threePa:max('threePa'),mpg:max('mpg'),first:Math.max(.01,...candidates.map(p=>(p.wins+1)/(p.starts+5)))};
    return MARKETS.map(market=>{
      let reason=!trusted?'History verification failed':!opponent?'Select a matchup to supply the opponent':!t||!def?'No team/opponent sample in selected competition':null;
      if(!reason&&market==='first-team-basket'&&!scope.openingVerified)reason='Verified NBA opening play-by-play unavailable for this sample';
      const ranked=[];
      if(!reason)for(const p of candidates){
        if(p.group==='unknown'||p.stats.gp<MIN_GAMES||p.missing)continue;
        const first=market==='first-team-basket',three=market==='threes',corr=three?p.stats.threeCorrelation:p.stats.fgCorrelation;
        if(first&&p.starts<MIN_GAMES||!first&&!(corr.r>0)||three&&!(p.stats.threePa>0))continue;
        const key=first?'first':three?'threes':'points',allowed='allowed'+key[0].toUpperCase()+key.slice(1);
        if(!t.totals[key]||!def.totals[allowed])continue;
        const offense=(t[key][p.group]||0)/t.totals[key],defense=(def[allowed][p.group]||0)/def.totals[allowed];
        const opportunity=first?.5*((p.wins+1)/(p.starts+5))/maximum.first+.3*(p.openingRate||0)+.2*Math.min(1,p.starts/p.stats.gp):
          .4*((p.stats.mpg||0)/maximum.mpg)+.3*(p.stats[three?'threePa':'fga']/maximum[three?'threePa':'fga'])+.2*(p.stats[three?'threePct':'fgPct']||0)+.1*Math.max(0,corr.r);
        const score=100*(WEIGHTS.offense*offense+WEIGHTS.defense*defense+WEIGHTS.opportunity*opportunity);
        ranked.push({...p,score,components:{offense,defense,opportunity},correlation:first?null:corr,market,
          seasonTarget:first?null:seasonDecision(p.rows,market,p.seasonStats),
          decision:first?{line:null,side:null,status:snapshot.meta.target==='first-team-made-field-goal'?'First team made field goal · free throws excluded':'First team score · made free throws included'}:lineDecision(p.rows,market,lines[p.id+'|'+market]),
          sampleQuality:p.stats.gp<20?'Small sample':'20+ observed games',
          unknownOffense:(t[key].unknown||0)/t.totals[key],unknownDefense:(def[allowed].unknown||0)/def.totals[allowed]});
      }
      ranked.sort((a,b)=>b.score-a.score||b.stats.gp-a.stats.gp||a.name.localeCompare(b.name));
      return {team,opponent,market,label:market==='first-team-basket'?(snapshot.meta.target==='first-team-made-field-goal'?'First Team Basket · Field Goal':'First Team Score · Includes FT'):LABELS[market],pick:ranked[0]||null,candidates:ranked.length,
        reason:ranked.length?null:reason||`No eligible player: needs ${MIN_GAMES} complete appearances, known position${market==='first-team-basket'?` and ${MIN_GAMES} starts`: ' and positive attempts/makes correlation'}`};
    });
  }
  function build(A,H,data,supplement,{phase='regular-season',firstBasketTarget=FIRST_TARGETS[0],...options}={}){
    if(!['regular-season','playoffs'].includes(phase))throw Error('Choose regular season or playoffs; samples cannot be pooled');
    if(!FIRST_TARGETS.includes(firstBasketTarget))throw Error('Unsupported first team basket definition');
    const opening=supplement?.openingEvidence,openingVerified=!!opening&&opening.meta.parentEvidenceContentHash===data.meta.evidenceContentHash&&data.games.every(g=>opening.games[g.id]?.sourceHash===g.sourceHash);
    const knownAttempts=events=>Object.fromEntries(Object.entries(events).filter(([,e])=>e.athleteIds.length===1&&!e.identityUnresolved));
    const verifiedData=openingVerified?{...data,games:data.games.map(g=>{const o=opening.games[g.id];return {...g,firstScores:o.firstScores,firstFieldGoals:o.firstFieldGoals,opening:{eventId:g.id,firstAttempts:knownAttempts(o.firstAttempts),firstFieldGoalAttempts:knownAttempts(o.firstFieldGoalAttempts),orderedEvents:o.orderedEvents,source:opening.meta.source,sourceUrl:o.source,sourceHash:o.sourceHash}};})}:data;
    const snapshot=H.snapshotForScope(A,verifiedData,{...options,phase,target:firstBasketTarget});
    snapshot.openingVerified=openingVerified;
    snapshot.evidenceHash=data.meta.evidenceContentHash;
    const scope=sample(snapshot,supplement);
    return {snapshot,scope,season:data.meta.season,phase,through:snapshot.meta.statsThrough,complete:!!data.meta.coverageComplete,
      allPlayerStats:acrossStints=>Object.fromEntries(Object.entries(scope.byPlayer).map(([id,p])=>[id,acrossStints?summarize(p.all):Object.fromEntries(Object.entries(p.teams).map(([t,rows])=>[t,summarize(rows)]))]))};
  }
  return {MARKETS,LABELS,WEIGHTS,MIN_GAMES,FIRST_TARGETS,correlation,positionGroup,shootingRow,summarize,sample,lineDecision,seasonDecision,rankTeam,build};
});
