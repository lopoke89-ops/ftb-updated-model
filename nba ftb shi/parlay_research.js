/* Isolated deterministic evidence experiment. Never issues production picks. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory(require('./parlay.js'),require('./scouting_history.js'));else root.FTBParlayResearch=factory(root.FTBParlay,root.FTBScoutingHistory);})(typeof window!=='undefined'?window:this,function(P,H){
  'use strict';
  const mean=(prior,y,n,strength)=>({value:(prior*strength+y)/(strength+n),priorEquivalent:strength,currentN:n,currentTotal:y,currentWeight:n/(strength+n)});
  function rank({archive,current,productionCurrent=current,model,full,acrossStints=false,config,competition,firstBasketTarget,variant='full'}){
    const out={market:archive?.market||current.market,team:current.team,opponent:current.opponent,modelVersion:config?.version,configurationHash:config?.configurationHash,
      researchOnly:true,positionScope:archive?.positionScope,ranked:[],pick:null,audit:[],reason:null};
    if(!config||competition!==config.phase)return {...out,reason:'Research configuration is fitted for regular season only'};
    if(!archive?.pick||!archive.selectionReview?.coverageReady||!archive.selectionReview?.sampleReady)return {...out,reason:'Qualifying prior-season market sample unavailable'};
    const market=archive.market,first=market==='first-team-basket',three=market==='threes',key=first?'first':three?'threes':'points',allowed='allowed'+key[0].toUpperCase()+key.slice(1);
    const t=model.scope.byTeam[out.team],d=model.scope.byTeam[out.opponent];
    for(const [side,k] of [[t,key],[d,allowed]])if(side?.totals[k]>0&&1-(side[k].unknown||0)/side.totals[k]+1e-10<.8)return {...out,reason:'Current positional production below 80% known at the common comparison resolution'};
    const suffix=firstBasketTarget===P.FIRST_TARGETS[1]?'fg':'inclusive',strength=k=>{const s=config.strengths[k]?.strength;if(!(s>0))throw Error('Missing fitted prior strength: '+k);return s;};
    const posStrength=strength('position-'+(first?'first-'+suffix:key));
    const activeCurrent=new Map((productionCurrent.ranked||[]).map(p=>[p.id,p]));
    for(const p of archive.ranked){
      const currentGroup=model.scope.positions[p.id];
      if(!p.confirmation&&currentGroup&&currentGroup!=='unknown'&&currentGroup!==p.group){out.audit.push({id:p.id,reason:'Dated current role differs from historical role; rotation transfer is outside this experiment'});continue;}
      const source=model.scope.byPlayer[p.id],rows=(acrossStints?source?.all:source?.teams[out.team])||[],stats=P.summarize(rows);
      const e=H.playerEvidence(model.snapshot,p.id,out.team,acrossStints),detail=e.scoutingDetail;
      const missing=acrossStints?source?.missing:Math.max(0,(detail.gp||0)-rows.length);
      if(missing){out.audit.push({id:p.id,reason:'Incomplete current shooting rows'});continue;}
      const corr=three?stats.threeCorrelation:stats.fgCorrelation,priorCorr=p.correlation;
      const activeCorrelation=stats.gp>=5?corr:priorCorr;
      if(!first&&variant!=='no-correlation'&&!(activeCorrelation?.r>0)){out.audit.push({id:p.id,reason:'Active attempts/makes correlation is undefined or nonpositive',currentCorrelation:corr,priorCorrelation:priorCorr});continue;}
      const grade=H.firstBasketQuality(e,H.gradeContext(model.snapshot)),quality=first?(grade.rated?grade:p.firstQuality):null;
      if(first&&!(quality.factor>0)){out.audit.push({id:p.id,reason:'Observed scoring-share quality safeguard failed'});continue;}
      const minutes=rows.filter(r=>Number.isFinite(r.minutesSeconds)||Number.isFinite(r.minutes)),minutesTotal=minutes.reduce((n,r)=>n+(Number.isFinite(r.minutesSeconds)?r.minutesSeconds/60:r.minutes),0);
      if(!Number.isFinite(p.stats.mpg)){out.audit.push({id:p.id,reason:'Historical minutes unavailable'});continue;}
      const estimates={
        minutes:mean(p.stats.mpg,minutesTotal,minutes.length,strength('minutes')),
        attempts:mean(p.stats[three?'threePa':'fga'],stats.total[three?'threeAttempted':'fga'],stats.gp,strength(three?'threePa':'fga')),
        conversion:mean(p.stats[three?'threePct':'fgPct']||0,stats.total[three?'threeMade':'fgm'],stats.total[three?'threeAttempted':'fga'],strength(three?'threeConversion':'fgConversion')),
        starting:mean(p.starts/p.stats.gp,detail.starts||0,detail.gp||0,strength('starting')),
        firstRate:mean(p.starts?p.wins/p.starts:0,detail.starterWins||0,detail.starts||0,strength('firstRate-'+suffix)),
        opening:mean(p.openingRate||0,firstBasketTarget===P.FIRST_TARGETS[1]?(detail.firstFgAttempts||0):(detail.openingAttempts||0),firstBasketTarget===P.FIRST_TARGETS[1]?(detail.firstFgSample||0):(detail.openingSample||0),strength('opening-'+suffix)),
        offense:mean(p.components.offense,t?.[key]?.[p.group]||0,t?.totals[key]||0,posStrength),
        defense:mean(p.components.defense,d?.[allowed]?.[p.group]||0,d?.totals[allowed]||0,posStrength)
      };
      const currentEligible=!!productionCurrent.selectionReview?.coverageReady&&!!productionCurrent.selectionReview?.sampleReady&&activeCurrent.has(p.id);
      const target=first?null:(currentEligible?activeCurrent.get(p.id).seasonTarget:p.seasonTarget);
      out.ranked.push({id:p.id,name:p.name,group:p.group,estimates,qualityFactor:first?quality.factor:1,
        qualityBasis:first?(grade.rated?model.season:archive.evidenceModel.season):null,
        observedCurrentGrade:first?grade:null,priorGames:p.stats.gp,currentGames:stats.gp,currentStats:stats,
        currentProductionEligible:currentEligible,provisional:p.provisional,eligibilityReason:p.eligibilityReason,confirmation:p.confirmation,
        activeCorrelation:first?null:activeCorrelation,correlationBasis:first?null:stats.gp>=5?model.season:archive.evidenceModel.season,
        currentCorrelation:first?null:corr,priorCorrelation:first?null:priorCorr,
        seasonTarget:target,targetBasis:first?null:{season:currentEligible?model.season:archive.evidenceModel.season,competition,average:target.average,threshold:target.threshold},
        statsThrough:model.through,priorThrough:archive.evidenceModel.through,positionScope:out.positionScope});
    }
    const max=k=>Math.max(k==='firstRate'?.01:1,...out.ranked.map(p=>p.estimates[k].value));
    for(const p of out.ranked){const e=p.estimates;
      const opportunity=first?.5*e.firstRate.value/max('firstRate')+.3*e.opening.value+.2*e.starting.value:
        .4*e.minutes.value/max('minutes')+.3*e.attempts.value/max('attempts')+.2*e.conversion.value+.1*(variant==='no-correlation'?0:p.activeCorrelation.r);
      p.components={offense:e.offense.value,defense:e.defense.value,opportunity};
      p.score=100*(p.components.offense+p.components.defense+opportunity)/3*p.qualityFactor;
    }
    out.ranked.sort((a,b)=>b.score-a.score||b.priorGames-a.priorGames||a.id.localeCompare(b.id));
    out.pick=out.ranked[0]||null;out.reason=out.pick?null:'No candidate has qualifying historical and current research evidence';
    out.targetTable=Object.fromEntries(out.ranked.filter(p=>p.targetBasis).map(p=>[p.id,p.targetBasis]));
    if(variant==='full'){
      const reduced=p=>p?{id:p.id,name:p.name,score:p.score,seasonTarget:p.seasonTarget,targetBasis:p.targetBasis,provisional:p.provisional,currentProductionEligible:p.currentProductionEligible}:null;
      const best=fn=>[...out.ranked].sort((a,b)=>fn(b)-fn(a)||a.id.localeCompare(b.id))[0];
      out.baselines={volume:reduced(best(p=>p.estimates[first?'firstRate':'attempts'].value)),mean:reduced(best(p=>first?p.estimates.offense.value:p.seasonTarget.average)),
        'no-position':reduced(best(p=>p.components.opportunity*p.qualityFactor)),
        'no-correlation':reduced(rank({archive,current,productionCurrent,model,full,acrossStints,config,competition,firstBasketTarget,variant:'no-correlation'}).pick)};
    }
    return out;
  }
  return {mean,rank};
});
