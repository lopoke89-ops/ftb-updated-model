(function(){
  'use strict';
  const h=React.createElement,{useState,useMemo,useEffect}=React,P=window.FTBParlay;
  const num=v=>Number.isFinite(v)?v.toFixed(1):'Unavailable',pct=v=>Number.isFinite(v)?(100*v).toFixed(1)+'%':'Unavailable';
  const panel={background:'#0d1120',border:'1px solid #161f35',borderRadius:11,padding:14,marginBottom:12};
  const muted={color:'#94a3b8',fontSize:12,lineHeight:1.6};
  function compareTable(id,comparison){
    const phases=['regular-season','playoffs'],stats=phases.map(phase=>P.summarize(comparison[phase].scope.byPlayer[id]?.all||[]));
    const metrics=[['GP',s=>String(s.gp)],['MIN',s=>num(s.mpg)],['PTS',s=>num(s.ppg)],['REB',s=>num(s.rpg)],['AST',s=>num(s.apg)],['STL',s=>num(s.spg)],['BLK',s=>num(s.bpg)],['+/-',s=>num(s.plusMinus)],['FGM / FGA',s=>`${num(s.fgm)} / ${num(s.fga)}`],['FG%',s=>pct(s.fgPct)],['3PM / 3PA',s=>`${num(s.threePm)} / ${num(s.threePa)}`],['3P%',s=>pct(s.threePct)],['FTM / FTA',s=>`${num(s.ftm)} / ${num(s.fta)}`],['FT%',s=>pct(s.ftPct)],['TO',s=>num(s.tov)],['PF',s=>num(s.pf)],['OREB',s=>num(s.oreb)],['DREB',s=>num(s.dreb)],['TS%',s=>pct(s.tsPct)]];
    return h('div',{style:{overflowX:'auto'}},h('table',{style:{width:'100%',textAlign:'left',fontSize:12}},
      h('caption',null,'Season averages across team stints · same date cutoff · excludes rolling and opponent filters'),
      h('thead',null,h('tr',null,['Stat','Regular season','Postseason · Playoffs'].map(v=>h('th',{key:v,scope:'col'},v)))),
      h('tbody',null,metrics.map(([label,format])=>h('tr',{key:label},h('th',{scope:'row'},label),...stats.map((s,i)=>h('td',{key:phases[i]},format(s))))))),
      h('small',{style:muted},'Counts are per appearance except GP. Minutes use NBA gamebook seconds. Percentages use summed shooting counts; TS% = PTS / [2 × (FGA + 0.44 × FTA)]. Play-in and the standalone Cup final are excluded.'));
  }
  window.FTBParlayPanel=function ParlayPanel({A,H,data,supplement,options,phase,period,teams,fixtures,rosters,acrossStints,excludedIds,trusted,teamColors={}}){
    const [competition,setCompetition]=useState(['regular-season','playoffs'].includes(phase)?phase:'regular-season'),[lines,setLines]=useState({});
    useEffect(()=>{if(['regular-season','playoffs'].includes(phase))setCompetition(phase);},[phase]);
    const contextKey=[data.meta.season,options.date,options.mode,competition,period,JSON.stringify(options.historyMatchups||[]),JSON.stringify(excludedIds),JSON.stringify(fixtures)].join('|');
    useEffect(()=>setLines({}),[contextKey]);
    const model=useMemo(()=>P.build(A,H,data,supplement,{...options,phase:competition,window:period}),[A,H,data,supplement,options.date,options.mode,options.positionReferences,JSON.stringify(options.historyMatchups),competition,period]);
    const comparison=useMemo(()=>Object.fromEntries(['regular-season','playoffs'].map(phase=>[phase,P.build(A,H,data,supplement,{...options,phase,window:0,historyMatchups:undefined})])),[A,H,data,supplement,options.date,options.mode,options.positionReferences]);
    const displayed=fixtures.length?[...new Set(fixtures.flatMap(g=>[g.home,g.away]))]:teams;
    const slots=displayed.flatMap(team=>{const fixture=fixtures.find(g=>g.home===team||g.away===team),opponent=fixture?(fixture.home===team?fixture.away:fixture.home):null;
      return P.rankTeam({team,opponent,roster:rosters[team]||[],snapshot:model.snapshot,sample:model.scope,acrossStints:acrossStints&&!options.historyMatchups,excludedIds,lines,trusted});});
    return h('section',{'aria-label':'Parlay Machine'},h('h2',null,'Parlay Machine'),
      h('div',{className:'analyst-notice',role:'status'},`${model.season} ${competition==='playoffs'?'postseason / playoff':'regular-season'} history through ${model.through||'no eligible games'}. ${options.mode==='review'&&model.complete?'Completed archive.':'Statistics available before the selected game date.'} ${Number(period)?`Last ${period} eligible team games. `:''}${options.historyMatchups?'Selected opponents only. ':''}Three market slots per team. Rankings describe evidence strength; they are not calibrated probabilities.`),
      h('div',{className:'controls'},h('label',null,'Parlay statistical sample ',h('select',{'aria-label':'Parlay statistical sample',value:competition,onChange:e=>setCompetition(e.target.value)},h('option',{value:'regular-season'},'Regular season'),h('option',{value:'playoffs'},'Postseason · Playoffs')))),
      h('p',{style:muted},'Regular season and playoffs are never pooled here. This selector controls Parlay competition; the date, statistical period and opponent-history filters still apply. First Team Basket means that team’s first scoring play, including made free throws. Matchups use verified PG, SG, SF, PF and C roles. Broad G/F labels remain unknown; players without a verified specific position are excluded from selections.'),
      h('details',null,h('summary',null,'How selections are weighted'),h('p',{style:muted},'All markets: one-third team scoring by position, one-third opponent allowance by position, one-third player opportunity. First Team Basket uses first-score shares; Points uses full-game points shares; Threes uses full-game made-three shares. Unknown-position production remains in the denominator.'),
        h('p',{style:muted},'First-basket opportunity: 50% relative smoothed starter scoring rate, 30% opening-attempt rate, 20% starting frequency. Points/Threes opportunity: 40% relative historical minutes, 30% relative attempt volume, 20% conversion, 10% positive game-level Pearson correlation. At least five complete appearances are required; first basket also requires five starts. Points and Threes require positive correlation. These new ranking weights have not been calibrated as a forecast model.'),
        h('p',{style:muted},'Manual prop lines are compared to the selected player’s scoped historical average. Over/Under is a research lean; prices and expected value are unavailable. Averages do not represent confirmed projected minutes. Prior-season scouting follows stable player IDs across team stints; head-to-head samples use the displayed team only. Missing shooting rows prevent a selection.')),
      !slots.length&&h('p',null,'Load a matchup and its roster to generate selections.'),
      displayed.map(team=>h('section',{key:team,style:{...panel,'--team-color':teamColors[team]||'#64748b'}},h('h3',{className:'parlay-team-heading'},h('span',{className:'team-badge'},team)),h('div',{className:'analyst-grid parlay-grid'},slots.filter(s=>s.team===team).map(slot=>{
        const p=slot.pick;if(!p)return h('article',{key:slot.market,className:'player-card parlay-card','data-market':slot.market,'data-team':team},h('h4',{className:'parlay-market'},slot.label),h('p',null,'Selection unavailable'),h('small',{style:muted},slot.reason),h('div',{className:'card-accent'}));
        const key=p.id+'|'+slot.market,c=p.components,s=p.stats;
        return h('article',{key:slot.market,className:'player-card parlay-card','data-market':slot.market,'data-team':team},h('h4',{className:'parlay-market'},slot.label),h('strong',{className:'player-name parlay-player-name'},p.name),h('p',{className:'player-meta'},h('span',{className:'team-badge'},team),` vs ${slot.opponent} · ${p.group}`),
          h('p',null,`Evidence score ${num(p.score)} / 100 · ${p.sampleQuality}`),h('p',{style:muted},`Position scoring share ${pct(c.offense)} · opponent allowance share ${pct(c.defense)} · player opportunity ${pct(c.opportunity)}`),
          h('p',{style:muted},`${s.gp} appearances · ${num(s.mpg)} historical MPG (${s.minutesGames} recorded) · ${p.lineup}`),
          h('p',null,`${num(s.ppg)} PPG · FGM/FGA ${num(s.fgm)}/${num(s.fga)} (${pct(s.fgPct)}) · 3PM/3PA ${num(s.threePm)}/${num(s.threePa)} (${pct(s.threePct)}) · ${num(s.ftm)} FTM`),
          p.correlation?h('p',null,`${slot.market==='points'?'FGA ↔ FGM':'3PA ↔ 3PM'} correlation: ${p.correlation.r.toFixed(3)} · ${p.correlation.n} paired games`):h('p',null,`${p.wins} first team scores in ${p.starts} starts · ${pct(p.startRate)} · opening-attempt share ${pct(p.openingRate)} (${p.openingSample} games)`),
          slot.market!=='first-team-basket'&&h('label',null,'Sportsbook line ',h('input',{type:'number',min:0,step:.5,value:lines[key]??'','aria-label':`${team} ${slot.label} sportsbook line`,placeholder:'Enter line',onChange:e=>{const text=e.target.value;setLines(old=>{const next={...old};if(text===''||!Number.isFinite(Number(text))||Number(text)<0)delete next[key];else next[key]=Number(text);return next;});}})),
          h('p',null,p.decision.side?`${p.decision.side} ${p.decision.line} · ${p.decision.status}`:p.decision.status),
          Number.isFinite(p.decision.n)&&h('small',{style:muted},`Observed over / under / push: ${p.decision.over} / ${p.decision.under} / ${p.decision.push} in ${p.decision.n} games`),
          h('details',null,h('summary',null,'Separate season averages and source evidence'),compareTable(p.id,comparison),h('p',{style:muted},`Unknown-position production: team ${pct(p.unknownOffense)}, opponent ${pct(p.unknownDefense)}. ${slot.candidates} eligible candidates.`),
            h('p',{style:muted},supplement?.meta?.verification||'Shooting statistics read from collected box scores.'),h('ul',null,p.rows.map(r=>{const g=model.snapshot.games.find(g=>g.id===r.gameId);return h('li',{key:r.gameId},h('a',{href:g?.source||'#',target:'_blank',rel:'noreferrer'},`${r.date} · ${r.team} · game ${r.gameId}`));}))),h('div',{className:'card-accent'}));
      })))),h('p',{style:muted},'Sportsbook prices and combined parlay probability are unavailable. No joint-leg model has been validated.'));
  };
})();
