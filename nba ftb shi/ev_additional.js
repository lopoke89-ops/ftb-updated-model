/* Separately versioned assists/rebounds research. Original count models remain frozen. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEVAdditional=api;})(typeof window==='object'?window:this,function(){
 'use strict';
 const VERSION='ev-assists-rebounds-v1',MARKETS=['assists','rebounds'],MAX_AGE=300000,MIN_GAMES=20,POS=['G','F','C'];
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),sum=(rs,k)=>rs.reduce((n,r)=>n+r[k],0),mean=(rs,k)=>sum(rs,k)/rs.length;
 const group=raw=>({PG:'G',SG:'G',SF:'F',PF:'F',G:'G',F:'F',C:'C',GUARD:'G',FORWARD:'F',CENTER:'C'}[String(raw||'').toUpperCase()]||null);
 function seasonOf(date){const year=Number(date.slice(0,4)),start=Number(date.slice(5,7))>=7?year:year-1;return start+'-'+String(start+1).slice(-2);}
 function validRow(p,market){return p.played===true&&Number.isFinite(p.minutes)&&p.minutes>=0&&Number.isInteger(p[market])&&p[market]>=0&&(market!=='rebounds'||Number.isInteger(p.offensiveRebounds)&&p.offensiveRebounds>=0&&Number.isInteger(p.defensiveRebounds)&&p.defensiveRebounds>=0&&p.offensiveRebounds+p.defensiveRebounds===p.rebounds);}
 function newState(){return {players:{},teams:{},league:{},seen:new Set(),through:null};}
 function addGame(s,g){
  if(s.seen.has(g.id))throw Error('Duplicate additional-count fixture');
  if(g.boxScoreSource!=='NBA official final box'||!/^[a-f0-9]{64}$/.test(g.sourceHash||''))throw Error('Official gamebook evidence required');
  s.seen.add(g.id);s.through=g.date;
  for(const team of [g.home,g.away]){
   const teamState=s.teams[team]||(s.teams[team]={});
   for(const market of MARKETS){
    const t=teamState[market]||(teamState[market]={games:0,own:{},allowed:{},ownMinutes:0,allowedMinutes:0,missingGames:0});
    const opp=team===g.home?g.away:g.home,valid=side=>g.teams[side].players.filter(p=>p.played);
    if([team,opp].some(side=>valid(side).some(p=>!validRow(p,market)||p.statsSourceHash!==g.sourceHash))){t.missingGames++;continue;}
    t.games++;
    for(const side of [team,opp])for(const p of valid(side)){
     const own=side===team,role=group(p.officialPosition||p.rawPosition),target=own?t.own:t.allowed;
     t[own?'ownMinutes':'allowedMinutes']+=p.minutes;
     if(role){const a=target[role]||(target[role]={count:0,minutes:0});a.count+=p[market];a.minutes+=p.minutes;
      if(own){const a=(s.league[market]||(s.league[market]={}))[role]||((s.league[market])[role]={count:0,minutes:0});a.count+=p[market];a.minutes+=p.minutes;}}
    }
   }
   for(const p of g.teams[team].players)if(p.played&&p.statsSourceHash===g.sourceHash)
    (s.players[String(p.id)]||(s.players[String(p.id)]=[])).push({...p,team,date:g.date,gameId:g.id,season:g.season||seasonOf(g.date),role:group(p.officialPosition||p.rawPosition)});
  }
 }
 function buildState(games,{before,phase='regular-season'}={}){const s=newState();for(const g of [...games].filter(g=>g.phase===phase&&(!before||g.date<before)).sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id)))addGame(s,g);return s;}
 function features(s,id,team,opponent,market){
  if(!MARKETS.includes(market))return {reason:'Unsupported additional-count market'};
  const all=s.players[String(id)]||[],same=all.filter(p=>p.team===team),rows=same.filter(p=>validRow(p,market));
  if(rows.length<MIN_GAMES||rows.length!==same.length)return {reason:rows.length!==same.length?'Missing or inconsistent credited-stat records': 'Needs 20 complete prior appearances with '+team+'; has '+rows.length};
  const recent=rows.slice(-20),weights=recent.map((_,i)=>.94**(recent.length-1-i)),w=weights.reduce((a,b)=>a+b,0),avg=k=>recent.reduce((n,r,i)=>n+weights[i]*r[k],0)/w;
  if(!(sum(rows,'minutes')>0&&avg('minutes')>0))return {reason:'No positive recorded playing-time exposure'};
  const blend=(a,b)=>(a*recent.length+b*5)/(recent.length+5),minutes=blend(avg('minutes'),mean(rows,'minutes')),baseline=mean(rows,market),recentMean=avg(market),rate=blend(recentMean/avg('minutes'),sum(rows,market)/sum(rows,'minutes'));
  const own=s.teams[team]?.[market],def=s.teams[opponent]?.[market],role=rows.at(-1).role,league=s.league[market]?.[role];
  const known=box=>box?Object.values(box).reduce((n,r)=>n+r.minutes,0):0;
  const positionSample=!!role&&league?.minutes>0&&own?.games>=10&&def?.games>=10&&known(own.own)/own.ownMinutes>=.8&&known(def.allowed)/def.allowedMinutes>=.8;
  const ratio=(box,n)=>league?.count>0&&box?.minutes>0?Math.exp(clamp(Math.log(Math.max(.01,(box.count/box.minutes)/(league.count/league.minutes))),-.7,.7)*n/(n+20)):1;
  const variance=rows.reduce((n,r)=>n+(r[market]-baseline)**2,0)/(rows.length-1),histogram={};for(const r of rows)histogram[r[market]]=(histogram[r[market]]||0)+1;
  return {market,n:rows.length,recentGames:recent.length,minutes,role,roleSource:rows.at(-1).officialPosition?'NBA printed final-box position':'Stored historical role',
   through:rows.at(-1).date,historySeasons:[...new Set(rows.map(r=>r.season))],teams:[team],lastTeam:team,otherTeamAppearances:all.length-same.length,recentStarterRate:recent.filter(r=>r.starter).length/recent.length,
   base:{[market]:minutes*rate},baseline:{[market]:baseline},recent:{[market]:recentMean},dispersion:{[market]:baseline>0?clamp((variance-baseline)/(baseline*baseline),.01,2):.5},histograms:{[market]:histogram},
   ratios:{[market]:{offense:ratio(own?.own[role],own?.games||0),defense:ratio(def?.allowed[role],def?.games||0)}},positionSample,teamGames:own?.games||0,opponentGames:def?.games||0,
   offensiveRebounds:market==='rebounds'?mean(rows,'offensiveRebounds'):null,defensiveRebounds:market==='rebounds'?mean(rows,'defensiveRebounds'):null};
 }
 function thresholds(f,market){const offsets=market==='assists'?[-3,-1,0,1,3]:[-4,-2,0,2,4];return [...new Set(offsets.map(n=>Math.max(0,Math.round(f.baseline[market])+n)))];}
  function distribution(mu,alpha){
    if(!Number.isFinite(mu)||mu<0||!Number.isFinite(alpha)||alpha<=0)throw Error('Invalid count distribution');
    if(mu===0)return [1];const r=1/alpha,q=mu/(r+mu),out=[];let p=Math.exp(r*Math.log(r/(r+mu))),total=0;
    for(let k=0;k<800;k++){out.push(p);total+=p;if(k>mu&&1-total<1e-12)break;p*=((k+r)/(k+1))*q;}
    if(total<.999999)throw Error('Count distribution tail did not converge');return out;
  }
  function cdf(mass,k){if(k<0)return 0;let p=0;for(let i=0;i<mass.length&&i<=Math.floor(k);i++)p+=mass[i];return clamp(p,0,1);}
  const logit=p=>Math.log(clamp(p,1e-8,1-1e-8)/(1-clamp(p,1e-8,1-1e-8)));
  const sigmoid=z=>1/(1+Math.exp(-clamp(z,-40,40)));
  function calibratedCDF(mass,k,cal){const p=cdf(mass,k);return p===0||p===1?p:sigmoid((cal?.a??1)*logit(p)+(cal?.b??0));}
  function probabilities(prediction,{side,line}){
    if(!prediction?.mass||!Number.isFinite(line)||line<0||!Number.isInteger(2*line)||!['over','under','at-least'].includes(side))throw Error('Unsupported exact prop contract');
    const f=k=>calibratedCDF(prediction.mass,k,prediction.calibration);let win,loss,push=0;
    if(side==='at-least'){if(!Number.isInteger(line))throw Error('Milestone must be an integer');win=1-f(line-1);loss=1-win;}
    else if(Number.isInteger(line)){push=f(line)-f(line-1);if(side==='over'){win=1-f(line);loss=f(line-1);}else{win=f(line-1);loss=1-f(line);}}
    else if(side==='over'){win=1-f(Math.floor(line));loss=1-win;}else{win=f(Math.floor(line));loss=1-win;}
    return {win:clamp(win,0,1),loss:clamp(loss,0,1),push:clamp(push,0,1)};
  }
  function expectedValue(p,decimal){if(!Number.isFinite(decimal)||decimal<=1||['win','loss','push'].some(k=>!Number.isFinite(p[k])||p[k]<0)||Math.abs(p.win+p.loss+p.push-1)>1e-7)throw Error('Invalid price or settlement probabilities');return p.win*(decimal-1)-p.loss;}
 function predict(f,market,model){
  if(f.reason)return {reason:f.reason};if(!f.positionSample)return {reason:'Needs supported G/F/C roles, 10 prior team games and 80% known-role minutes'};
  const c=model?.markets?.[market];if(!c?.enabled)return {reason:c?.withheldReason||'Separate market validation is not complete'};
  const raw=c.meanMode==='season-mean'?f.baseline[market]:c.meanMode==='recent-mean'?f.recent[market]:f.base[market];
  const mu=raw*f.ratios[market].defense**c.defensePower,alpha=c.alpha,mass=distribution(mu,alpha),calibratedMean=mass.reduce((n,_,k)=>n+1-calibratedCDF(mass,k,c.calibration),0);
  return {mass,mu,alpha,calibratedMean,calibration:c.calibration,features:f,market,modelVersion:VERSION};
 }
 function contractSupport(prediction,q){
  const f=prediction.features,hist=f?.histograms?.[q.market];if(!hist)return 'Exact-line credited-stat history unavailable';
  const cuts=thresholds(f,q.market),lo=Math.min(...cuts),hi=Math.max(...cuts),lower=q.side==='at-least'?q.line-1:Number.isInteger(q.line)?q.line-1:Math.floor(q.line),upper=q.side!=='at-least'&&Number.isInteger(q.line)?q.line:lower;
  if(lower<lo||upper>hi)return 'Target outside the separately fitted range; tail EV withheld';
  let wins=0,losses=0;for(const [value,n]of Object.entries(hist)){const y=Number(value);if(q.side==='at-least')y>=q.line?wins+=n:losses+=n;else if(q.side==='over'){if(y>q.line)wins+=n;else if(y<q.line)losses+=n;}else{if(y<q.line)wins+=n;else if(y>q.line)losses+=n;}}
  return wins<5||losses<5?'Needs five prior wins and five losses at this exact target; tail EV withheld':null;
 }
  function quoteState(q,fixture,now){
    const age=now-Date.parse(q.capturedAt),earliest=Math.min(Date.parse(fixture.scheduledTipoff),Date.parse(q.fanduelTipoff||fixture.scheduledTipoff));
    if(q.region!=='TN'||q.fixtureId!==fixture.id||q.team!==fixture.home&&q.team!==fixture.away||q.period!=='full-game'||!MARKETS.includes(q.market)||!/^\d+$/.test(q.fanduelEventId||'')||!Number.isFinite(Date.parse(q.fanduelTipoff))||Math.abs(Date.parse(q.fanduelTipoff)-Date.parse(fixture.scheduledTipoff))>900000)return 'identity-mismatch';
    if(fixture.status!=='pre'||!Number.isFinite(earliest)||now>=earliest)return 'closed';
    if(!Number.isFinite(age)||age<0||age>MAX_AGE)return 'stale';
    if(q.captureState==='cached')return 'cached';
    return q.marketStatus==='OPEN'&&q.runnerStatus==='ACTIVE'?'fresh':'suspended';
  }
  function evaluateQuotes({snapshot,fixtures,rosters,predictions,eligibility={},now=Date.now()}){
    const rows=[],audit=[],seen=new Set();
    for(const fixture of fixtures){const entry=snapshot?.fixtures?.[fixture.id];for(const q of entry?.quotes||[]){
      let reason=null;const status=quoteState(q,fixture,now),roster=(rosters[q.team]||[]).filter(p=>String(p.id)===q.playerId),key=q.key;
      if(seen.has(key)){audit.push({player:q.player,reason:'Duplicate offered selection'});continue;}seen.add(key);
      if(snapshot.schemaVersion!==1||snapshot.region!=='TN'||snapshot.bookmaker!=='fanduel'||entry.fixture?.home!==fixture.home||entry.fixture?.away!==fixture.away||entry.fixture?.id!==fixture.id||entry.fixture?.date!==fixture.date||entry.fixture?.season!==fixture.season||entry.fixture?.phase!==fixture.phase||fixture.phase!=='regular-season'||Date.parse(entry.fixture?.scheduledTipoff)!==Date.parse(fixture.scheduledTipoff)||entry.fanduelEventId!==q.fanduelEventId)reason='Odds snapshot identity mismatch';
      else if(status!=='fresh')reason='Quote '+status;
      else if(roster.length!==1||roster[0].team!==q.team||roster[0].name!==q.player)reason='Current-roster identity mismatch';
      else if(!/^https:\/\/sportsbook\.fanduel\.com\//.test(q.source||''))reason='Quote source mismatch';
      else if(!Number.isInteger(q.american)||Math.abs(q.american)<100||!Number.isFinite(q.decimal)||Math.abs(q.decimal-(q.american>0?1+q.american/100:1+100/Math.abs(q.american)))>1e-6)reason='Offered price formats disagree';
      else if(eligibility[q.playerId]?.excluded)reason=eligibility[q.playerId].reason||'Unavailable player';
      const prediction=predictions[fixture.id+'|'+q.team+'|'+q.playerId+'|'+q.market];
      if(!reason&&(prediction?.reason||!prediction))reason=prediction?.reason||'Probability evidence unavailable';
      if(!reason)reason=contractSupport(prediction,q);
      if(reason){audit.push({key,player:q.player,market:q.market,reason,status});continue;}
      try{const p=probabilities(prediction,q),ev=expectedValue(p,q.decimal),available=eligibility[q.playerId]||{provisional:true,reason:'Availability unconfirmed'};
        rows.push({quote:q,probabilities:p,ev,breakEven:1/q.decimal,conditionalWin:p.win/(p.win+p.loss),projection:prediction.calibratedMean??prediction.mu,rawProjection:prediction.mu,dispersion:prediction.alpha,features:prediction.features,provisional:!!available.provisional||!!prediction.roleUncertain,availability:prediction.roleUncertain?prediction.roleReason:available.reason,status});
      }catch(error){audit.push({key,player:q.player,reason:error.message,status:'invalid'});}
    }}
    rows.sort((a,b)=>b.ev-a.ev||a.quote.key.localeCompare(b.quote.key));return {rows,audit};
  }
 return {VERSION,MARKETS,MAX_AGE,MIN_GAMES,group,validRow,newState,addGame,buildState,features,thresholds,distribution,cdf,logit,sigmoid,calibratedCDF,predict,probabilities,expectedValue,contractSupport,quoteState,evaluateQuotes};
});
