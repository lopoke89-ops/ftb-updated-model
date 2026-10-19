/* Separate experimental prop distributions. Existing Parlay grades are never probabilities. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FTBEV=api;})(typeof window==='object'?window:this,function(){
  'use strict';
  const VERSION='ev-props-v1',MAX_AGE=300000,MIN_GAMES=20,POS=['G','F','C'];
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),sum=(rows,k)=>rows.reduce((n,r)=>n+r[k],0);
  const group=raw=>({PG:'G',SG:'G',SF:'F',PF:'F',G:'G',F:'F',C:'C',GUARD:'G',FORWARD:'F',CENTER:'C'}[String(raw||'').toUpperCase()]||null);
  const mean=(rows,k)=>rows.length?sum(rows,k)/rows.length:0;
  function validRow(p){return p.played&&['points','fgm','fga','threeMade','threeAttempted','ftm','fta','minutes'].every(k=>Number.isFinite(p[k])&&p[k]>=0)&&p.minutes>0&&p.fgm<=p.fga&&p.threeMade<=p.fgm&&p.threeMade<=p.threeAttempted&&p.threeAttempted<=p.fga&&p.ftm<=p.fta&&2*p.fgm+p.threeMade+p.ftm===p.points;}
  function newState(){return {players:{},teams:{},league:{},seen:new Set(),through:null,phases:new Set(),seasons:new Set()};}
  function addGame(s,g){
    if(s.seen.has(g.id))throw Error('Duplicate EV fixture');s.seen.add(g.id);s.through=g.date;s.phases.add(g.phase);
    for(const team of [g.home,g.away]){
      const own=s.teams[team]||(s.teams[team]={games:0,own:{},allowed:{},ownMinutes:0,allowedMinutes:0});own.games++;
      const opp=team===g.home?g.away:g.home;
      for(const [side,isOwn] of [[team,true],[opp,false]])for(const p of g.teams[side].players){
        if(!validRow(p))continue;own[isOwn?'ownMinutes':'allowedMinutes']+=p.minutes;const role=group(p.officialPosition||p.rawPosition),target=isOwn?own.own:own.allowed;
        if(role){const a=target[role]||(target[role]={points:0,threes:0,minutes:0});a.points+=p.points;a.threes+=p.threeMade;a.minutes+=p.minutes;
          if(isOwn){const a=s.league[role]||(s.league[role]={points:0,threes:0,minutes:0});a.points+=p.points;a.threes+=p.threeMade;a.minutes+=p.minutes;}}
        if(isOwn)(s.players[String(p.id)]||(s.players[String(p.id)]=[])).push({...p,id:String(p.id),team,date:g.date,gameId:g.id,role,season:g.season||String(g.date).slice(0,4)});
      }
    }
  }
  function buildState(games,{before,phase='regular-season'}={}){const s=newState();for(const g of [...games].filter(g=>g.phase===phase&&(!before||g.date<before)).sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id)))addGame(s,g);return s;}
  function correlation(rows,x,y){const mx=mean(rows,x),my=mean(rows,y);let xx=0,yy=0,xy=0;for(const r of rows){const a=r[x]-mx,b=r[y]-my;xx+=a*a;yy+=b*b;xy+=a*b;}return xx&&yy?xy/Math.sqrt(xx*yy):null;}
  function features(s,id,team,opponent){
    const all=s.players[String(id)]||[],rows=all.filter(r=>r.team===team);if(rows.length<MIN_GAMES)return {reason:`Needs ${MIN_GAMES} complete prior appearances with ${team}; has ${rows.length} (${all.length-rows.length} other-team appearances excluded from EV)`};
    const recent=rows.slice(-20),n=recent.length,w=recent.map((_,i)=>Math.pow(.94,n-1-i)),ws=w.reduce((a,b)=>a+b,0),avg=k=>recent.reduce((a,r,i)=>a+w[i]*r[k],0)/ws;
    const blend=(a,b)=>(a*n+b*5)/(n+5),minutes=blend(avg('minutes'),mean(rows,'minutes'));
    const attempts=k=>minutes*blend(avg(k)/Math.max(.1,avg('minutes')),sum(rows,k)/sum(rows,'minutes'));
    const fga=attempts('fga'),threePa=attempts('threeAttempted'),fta=attempts('fta');
    const twoA=rows.reduce((a,r)=>a+r.fga-r.threeAttempted,0),twoM=rows.reduce((a,r)=>a+r.fgm-r.threeMade,0);
    const pct=(made,att,prior)=>(made+prior*40)/(att+40);
    const p2=pct(recent.reduce((a,r)=>a+r.fgm-r.threeMade,0),recent.reduce((a,r)=>a+r.fga-r.threeAttempted,0),(twoM+1)/(twoA+2));
    const p3=pct(sum(recent,'threeMade'),sum(recent,'threeAttempted'),(sum(rows,'threeMade')+1)/(sum(rows,'threeAttempted')+2));
    const pft=pct(sum(recent,'ftm'),sum(recent,'fta'),(sum(rows,'ftm')+1)/(sum(rows,'fta')+2));
    const fg=correlation(rows,'fga','fgm'),three=correlation(rows,'threeAttempted','threeMade'),role=rows.at(-1).role;
    const own=s.teams[team],def=s.teams[opponent],league=s.league[role];
    const ratios=key=>{
      const rate=league?.minutes>0?league[key]/league.minutes:0,a=own?.own[role],d=def?.allowed[role];
      const shrink=(box,games)=>rate>0&&box?.minutes>0?Math.exp(clamp(Math.log(Math.max(.01,(box[key]/box.minutes)/rate)),-.7,.7)*games/(games+20)):1;
      return {offense:shrink(a,own?.games||0),defense:shrink(d,def?.games||0)};
    };
    const dispersion={},histograms={};for(const market of ['points','threes']){const key=market==='points'?'points':'threeMade',m=mean(rows,key),variance=rows.reduce((a,r)=>a+(r[key]-m)**2,0)/(rows.length-1);dispersion[market]=m>0?clamp((variance-m)/(m*m),.01,2):.5;histograms[market]={};for(const r of rows)histograms[market][r[key]]=(histograms[market][r[key]]||0)+1;}
    return {n:rows.length,recentGames:n,minutes,role,dispersion,histograms,otherTeamAppearances:all.length-rows.length,through:rows.at(-1).date,teams:[...new Set(rows.map(r=>r.team))],lastTeam:rows.at(-1).team,recentStarterRate:recent.filter(r=>r.starter).length/n,
      fga,fgm:Math.max(0,fga-threePa)*p2+threePa*p3,threePa,threePm:threePa*p3,fta,ftm:fta*pft,
      base:{points:2*Math.max(0,fga-threePa)*p2+3*threePa*p3+fta*pft,threes:threePa*p3},baseline:{points:mean(rows,'points'),threes:mean(rows,'threeMade')},
      ratios:{points:ratios('points'),threes:ratios('threes')},correlation:{points:fg,threes:three},positionSample:!!role&&!!league&&own?.games>=10&&def?.games>=10&&Object.values(own.own).reduce((n,p)=>n+p.minutes,0)/own.ownMinutes>=.8&&Object.values(def.allowed).reduce((n,p)=>n+p.minutes,0)/def.allowedMinutes>=.8,
      teamGames:own?.games||0,opponentGames:def?.games||0};
  }
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
  function predict(f,market,model){
    if(f.reason)return {reason:f.reason};if(!POS.includes(f.role)||!f.positionSample)return {reason:'Needs supported G/F/C role and 10 prior games for both teams'};
    if(!(f.correlation[market]>0))return {reason:'Attempts/makes correlation is not positive'};
    if(market==='threes'&&!(f.threePa>0))return {reason:'No supported three-point opportunity'};
    const config=model?.markets?.[market];if(!config||!config.calibration||!config.diagnostic)return {reason:'Probability model is not available for this market'};
    const mu=(config.meanMode==='season-mean'?f.baseline[market]:f.base[market])*Math.pow(f.ratios[market].defense,config.defensePower)*Math.pow(f.ratios[market].offense,config.offensePower);
    const alpha=clamp(config.alpha*(1-(config.dispersionBlend||0))+f.dispersion[market]*(config.dispersionBlend||0),.01,2);
    return {mass:distribution(mu,alpha),mu,alpha,calibration:config.calibration,features:f,market,modelVersion:model.version};
  }
  function probabilities(prediction,{side,line}){
    if(!prediction?.mass||!Number.isFinite(line)||line<0||!['over','under','at-least'].includes(side))throw Error('Unsupported exact prop contract');
    const f=k=>calibratedCDF(prediction.mass,k,prediction.calibration);let win,loss,push=0;
    if(side==='at-least'){if(!Number.isInteger(line))throw Error('Milestone must be an integer');win=1-f(line-1);loss=1-win;}
    else if(Number.isInteger(line)){push=f(line)-f(line-1);if(side==='over'){win=1-f(line);loss=f(line-1);}else{win=f(line-1);loss=1-f(line);}}
    else if(side==='over'){win=1-f(Math.floor(line));loss=1-win;}else{win=f(Math.floor(line));loss=1-win;}
    return {win:clamp(win,0,1),loss:clamp(loss,0,1),push:clamp(push,0,1)};
  }
  function expectedValue(p,decimal){if(!Number.isFinite(decimal)||decimal<=1||['win','loss','push'].some(k=>!Number.isFinite(p[k])||p[k]<0)||Math.abs(p.win+p.loss+p.push-1)>1e-7)throw Error('Invalid price or settlement probabilities');return p.win*(decimal-1)-p.loss;}
  function contractSupport(prediction,q){
    const f=prediction.features,hist=f?.histograms?.[q.market];if(!hist)return 'Exact-line outcome history unavailable';
    const lower=q.side==='at-least'?q.line-1:Number.isInteger(q.line)?q.line-1:Math.floor(q.line),upper=q.side!=='at-least'&&Number.isInteger(q.line)?q.line:lower;
    const lo=q.market==='points'?Math.max(0,Math.round(f.baseline.points)-8):0,hi=q.market==='points'?Math.round(f.baseline.points)+8:6;
    if(lower<lo||upper>hi)return 'Target outside the fitted calibration range; tail EV withheld';
    let wins=0,losses=0;for(const [value,n] of Object.entries(hist)){const y=Number(value);if(q.side==='at-least')y>=q.line?wins+=n:losses+=n;else if(q.side==='over'){if(y>q.line)wins+=n;else if(y<q.line)losses+=n;}else{if(y<q.line)wins+=n;else if(y>q.line)losses+=n;}}
    return wins<5||losses<5?'Needs five prior wins and five losses at this exact target; tail EV withheld':null;
  }
  function quoteState(q,fixture,now){
    const age=now-Date.parse(q.capturedAt),earliest=Math.min(Date.parse(fixture.scheduledTipoff),Date.parse(q.fanduelTipoff||fixture.scheduledTipoff));
    if(q.region!=='TN'||q.fixtureId!==fixture.id||q.team!==fixture.home&&q.team!==fixture.away||q.period!=='full-game'||!['points','threes'].includes(q.market)||!/^\d+$/.test(q.fanduelEventId||'')||Math.abs(Date.parse(q.fanduelTipoff)-Date.parse(fixture.scheduledTipoff))>900000)return 'identity-mismatch';
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
      if(snapshot.schemaVersion!==1||snapshot.region!=='TN'||snapshot.bookmaker!=='fanduel'||entry.fixture?.home!==fixture.home||entry.fixture?.away!==fixture.away||entry.fanduelEventId!==q.fanduelEventId)reason='Odds snapshot identity mismatch';
      else if(status!=='fresh')reason='Quote '+status;
      else if(roster.length!==1||roster[0].team!==q.team||roster[0].name!==q.player)reason='Current-roster identity mismatch';
      else if(!/^https:\/\/sportsbook\.fanduel\.com\//.test(q.source||''))reason='Quote source mismatch';
      else if(!Number.isInteger(q.american)||Math.abs(q.american)<100||Math.abs(q.decimal-(q.american>0?1+q.american/100:1+100/Math.abs(q.american)))>1e-6)reason='Offered price formats disagree';
      else if(eligibility[q.playerId]?.excluded)reason=eligibility[q.playerId].reason||'Unavailable player';
      const prediction=predictions[fixture.id+'|'+q.team+'|'+q.playerId+'|'+q.market];
      if(!reason&&(prediction?.reason||!prediction))reason=prediction?.reason||'Probability evidence unavailable';
      if(!reason)reason=contractSupport(prediction,q);
      if(reason){audit.push({key,player:q.player,market:q.market,reason,status});continue;}
      try{const p=probabilities(prediction,q),ev=expectedValue(p,q.decimal),available=eligibility[q.playerId]||{provisional:true,reason:'Availability unconfirmed'};
        rows.push({quote:q,probabilities:p,ev,breakEven:1/q.decimal,conditionalWin:p.win/(p.win+p.loss),projection:prediction.mu,features:prediction.features,provisional:!!available.provisional||!!prediction.roleUncertain,availability:prediction.roleUncertain?prediction.roleReason:available.reason,status});
      }catch(error){audit.push({key,player:q.player,reason:error.message,status:'invalid'});}
    }}
    rows.sort((a,b)=>b.ev-a.ev||a.quote.key.localeCompare(b.quote.key));return {rows,audit};
  }
  return {VERSION,MAX_AGE,MIN_GAMES,group,validRow,newState,addGame,buildState,features,distribution,cdf,logit,sigmoid,calibratedCDF,predict,probabilities,expectedValue,contractSupport,quoteState,evaluateQuotes};
});
