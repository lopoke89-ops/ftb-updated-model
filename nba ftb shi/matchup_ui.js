/* Matchup presentation uses appearance-level evidence, independent of pick engines. */
(function(){
  'use strict';
  const h=React.createElement,M=window.FTBMatchup,{useState,useMemo}=React;
  const labels={G:'Guards',F:'Forwards',C:'Centers',PG:'Point guards',SG:'Shooting guards',SF:'Small forwards',PF:'Power forwards',unknown:'Unknown role'};
  const format=v=>Number.isFinite(v)?v.toFixed(2):'Unavailable';
  const note=text=>h('p',{className:'matchup-note'},text);
  const signed=v=>Number.isFinite(v)?`${v>=0?'+':''}${v.toFixed(1)}%`:'Unavailable';
  function SourceGames({sample}){
    return h('details',{className:'matchup-source-games'},h('summary',null,`${sample.team} source games · ${sample.from||'unavailable'}–${sample.through||'unavailable'}`),
      h('ul',null,sample.sources.map(s=>h('li',{key:s.id},s.url?h('a',{href:s.url,target:'_blank',rel:'noreferrer'},`${s.date} vs ${s.opponent} · ${s.id} · NBA gamebook`):`${s.date} vs ${s.opponent} · ${s.id} · source unavailable`))));
  }
  function Evidence({sample,metric,rate,label}){
    const s=sample.own?sample.own[metric]:sample.series;
    return h('p',{className:'matchup-sample'},h('strong',null,label),` · ${sample.games} team games · through ${sample.through||'unavailable'} · ${s.appearances} played appearances`,
      rate==='per48'?` · ${(s.seconds/60).toFixed(1)} player-minutes`:'',
      s.missing?` · ${s.missing} appearances missing verified ${metric==='firstTeam'?'first-score evidence':M.METRICS[metric]}`:'',
      s.missingMinutes?` · ${s.missingMinutes} appearances missing minutes`:'',
      sample.roleCoverage?` · role sources: ${sample.roleCoverage.gamebook} gamebook, ${sample.roleCoverage.datedFallback} dated box fallback, ${sample.roleCoverage.unknown} unknown · ${sample.roleCoverage.verifiedFive||0} appearances also have verified five-position starter roles`:'');
  }
  function Shooting({d}){
    const cell=x=>`${x.made??'Unavailable'} / ${x.attempted??'Unavailable'} · ${x.percentage===null?'conversion unavailable':x.percentage.toFixed(1)+'%'} · ${x.games} games`;
    return h('details',{className:'matchup-evidence matchup-shooting'},h('summary',null,'Shooting · makes / attempts & pooled conversion'),
      note('Verified final boxes · full game including overtime. Counts use the displayed history and appearance roles. Percentages pool makes and attempts; no attempts means unavailable conversion. Counts are raw, regardless of chart normalization.'),
      h('div',{className:'matchup-table-scroll'},h('table',null,h('caption',null,`${d.production.team} production / opponents vs ${d.allowance.team} · shooting`),
        h('thead',null,h('tr',null,['Position','Shot','Production: made / attempted · %','Opponents: made / attempted · %'].map(t=>h('th',{key:t,scope:'col'},t)))),
        h('tbody',null,M.shootingRows(d).flatMap(r=>['FG','2P','3P','FT'].map(kind=>h('tr',{key:r.position+kind},h('th',{scope:'row'},labels[r.position]),h('td',null,kind),h('td',null,cell(r.production[kind])),h('td',null,cell(r.allowance[kind])))))))));
  }
  function EventEvidence({sample,opposing,metric}){
    const e=sample.events[opposing?'against':'own'],key=metric==='assists'?'assistedMakes':metric==='blocks'?'blockedAttempts':'distancedAttempts',f=e.features[key];
    const names={assistedMakes:'Made field goals explicitly linked to a credited passer, by passer role',blockedAttempts:'Blocked attempts explicitly linked to the shooter, by shooter role',distancedAttempts:'Field-goal attempts with a printed distance, by shooter role'};
    const total=Object.values(f.buckets).reduce((a,b)=>a+b,0);
    return h('details',{className:'matchup-evidence matchup-event-context'},h('summary',null,`${opposing?'Opponents vs ':''}${sample.team} · play-by-play coverage & context`),
      note(`Full-game ledger: ${e.fullyVerified} fully verified, ${e.partial} partial, ${e.unavailable} unavailable / ${e.expected} scoped games. Core charts and shooting counts use independently verified final boxes.`),
      metric==='firstTeam'?(e.opening.gameIds.length?note(`Opening attempt conversion: ${e.opening.gameIds.length?e.opening.firstAttemptMade+' / '+e.opening.gameIds.length:'Unavailable'} first attempts made. ${e.opening.freeThrowScores} first scores from free throws; ${e.opening.andOneAwarded} linked and-ones awarded, ${e.opening.andOneAttempted} attempted, ${e.opening.andOneMade} made. Exact eligible games: ${e.opening.gameIds.join(', ')||'none'}.`):note('Opening event context unavailable: no reconciled opening observations in this scope.')):h(React.Fragment,null,
        note(`${names[key]}. ${f.gameIds.length?total+' records across '+f.gameIds.length+' reconciled games, through '+f.through:'Unavailable: no reconciled games for this feature in this scope'}. This subset has its own sample and is not compared to a full-history baseline.`),
        f.gameIds.length>0&&note(Object.entries(f.buckets).map(([p,n])=>`${labels[p]}: ${n}`).join(' · ')),
        note(`Exact eligible games: ${f.gameIds.join(', ')||'none'}. Printed distance is source context; it does not establish shot coordinates, corner threes, or a midrange classification.`)));
  }
  function Direction({d,metric,rate,teamColors}){
    const a=d.production,b=d.allowance,own=a.own[metric],against=b.against[metric],rows=M.rows(d,metric,rate),unit=rate==='share'?'%':rate==='per48'?'per 48 player-min':'per team game';
    const largest=Math.max(1,...rows.flatMap(r=>[r.production,r.allowance,r.baseline]).filter(Number.isFinite));
    const available=rows.filter(r=>r.position!=='unknown'&&r.production!==null&&r.allowance!==null);
    const alignment=available.filter(r=>r.productionAbove>0&&r.allowanceAbove>0).sort((x,y)=>Math.min(y.productionAbove,y.allowanceAbove)-Math.min(x.productionAbove,x.allowanceAbove));
    const unknown=own.buckets.unknown,oppUnknown=against.buckets.unknown;
    return h('section',{className:'matchup-direction','data-production-team':a.team,'data-allowance-team':b.team},
      h('h4',null,h('span',{style:{color:`color-mix(in srgb, ${teamColors[a.team]||'#94a3b8'} 55%, #fff)`}},a.team),' production ',h('span',{className:'matchup-versus'},'vs'),' opponents against ',h('span',{style:{color:`color-mix(in srgb, ${teamColors[b.team]||'#94a3b8'} 55%, #fff)`}},b.team)),
      h(Evidence,{sample:a,metric,rate,label:a.team+' production'}),
      h(Evidence,{sample:{...b,own:null,series:against,roleCoverage:b.againstRoleCoverage},metric,rate,label:'Opponents vs '+b.team}),
      !a.games||!b.games?h('div',{className:'matchup-unavailable',role:'status'},`Comparison unavailable: ${!a.games?a.team:b.team} has no completed games in this scope. Broader history is not substituted.`):h(React.Fragment,null,
        h('div',{className:'matchup-legend'},h('span',null,h('i',{className:'matchup-swatch production'}),a.team+' production'),h('span',null,h('i',{className:'matchup-swatch allowance'}),'Opponents vs '+b.team),h('span',null,'Reference shown in table')),
        h('div',{className:'matchup-chart',role:'img','aria-label':`${M.METRICS[metric]} by position: ${a.team} production versus opponents against ${b.team}; ${unit}`},rows.map(r=>h('div',{className:'matchup-position',key:r.position},
          h('strong',null,labels[r.position]),h('div',{className:'matchup-bars'},[['production',r.production],['allowance',r.allowance]].map(([kind,value])=>h('div',{className:'matchup-bar-line',key:kind},
            h('div',{className:'matchup-bar-track'},Number.isFinite(value)&&h('div',{className:'matchup-bar '+kind,style:{width:100*value/largest+'%'}})),h('span',null,format(value)+(rate==='share'&&Number.isFinite(value)?'%':'')))))))),
        h('p',{className:'matchup-unit'},`${M.METRICS[metric]} ${unit} · common scale within this comparison`),
        alignment.length?note(`Observed alignment: ${labels[alignment[0].position].toLowerCase()}. ${a.team} production is ${signed(alignment[0].productionAbove)} and opposing production against ${b.team} is ${signed(alignment[0].allowanceAbove)} relative to that position’s league reference. This is descriptive evidence, not a prediction.`):note(available.length?'No recorded position is above the league reference on both sides of this comparison.':'No comparable recorded position in this scope; check role and statistic coverage.'),
        (unknown?.appearances||oppUnknown?.appearances)&&note(`Unknown roles: ${unknown?.appearances||0}/${own.appearances} production appearances (${own.seconds?(100*(unknown?.seconds||0)/own.seconds).toFixed(1)+'%':'unavailable'} of player-minutes) and ${oppUnknown?.appearances||0}/${against.appearances} opposing appearances (${against.seconds?(100*(oppUnknown?.seconds||0)/against.seconds).toFixed(1)+'%':'unavailable'} of player-minutes). Unknown stays visible; unrecorded positions are unavailable, not zero.`),
        ['points','threes'].includes(metric)&&h(Shooting,{d}),
        metric==='firstTeam'&&window.FTBOpeningPathsPanel&&h(window.FTBOpeningPathsPanel,{games:a.openingPathGames,team:a.team,target:a.firstTarget||'first-score',dataset:a.openingPaths,positionScope:d.positions}),h(EventEvidence,{sample:a,metric,opposing:false}),h(EventEvidence,{sample:b,metric,opposing:true}),
        h('details',{className:'matchup-evidence'},h('summary',null,'Values, denominators & source games'),
          h('div',{className:'matchup-table-scroll'},h('table',null,h('caption',null,`${M.METRICS[metric]} · ${unit}`),h('thead',null,h('tr',null,['Position',a.team+' production','Opponents vs '+b.team,'League reference','Production numerator / denominator','Opposing numerator / denominator'].map(l=>h('th',{key:l,scope:'col'},l)))),
            h('tbody',null,rows.map(r=>{
              const denominator=(series,pos)=>{const b=series.buckets[pos];if(!b)return 'No recorded appearances';const den=rate==='per48'?`${(b.seconds/60).toFixed(2)} player-min × 48`:rate==='share'?`${series.total??'unavailable'} total events × 100`:`${series.games} team games`;return `${b.total??'unavailable'} / ${den} · ${b.appearances} appearances in ${b.games} games`;};
              return h('tr',{key:r.position},h('th',{scope:'row'},labels[r.position]),h('td',null,format(r.production)),h('td',null,format(r.allowance)),h('td',null,format(r.baseline)),h('td',null,denominator(own,r.position)),h('td',null,denominator(against,r.position)));
            })))),
          h(SourceGames,{sample:a}),h(SourceGames,{sample:b}))));
  }
  window.FTBMatchupPanel=function FTBMatchupPanel({data,archiveData,fixtures,options,teamColors,trusted}){
    const [metric,setMetric]=useState('points'),[positions,setPositions]=useState('broad'),[rate,setRate]=useState('per48'),[firstTarget,setFirstTarget]=useState('including-free-throws');
    const result=useMemo(()=>{try{return M.build({...data,roleEvidence:data.meta.season===window.__FTB_PARLAY_DATA__?.meta?.season?window.__FTB_PARLAY_DATA__.datedRoleEvidence:data.roleEvidence,playByPlay:data.playByPlay||(window.__FTB_PLAY_BY_PLAY__?.parentEvidenceContentHash===data.meta.evidenceContentHash?window.__FTB_PLAY_BY_PLAY__:null)},{...archiveData,roleEvidence:window.__FTB_PARLAY_DATA__?.datedRoleEvidence,playByPlay:window.__FTB_PLAY_BY_PLAY__},fixtures,{...options,positions,firstTarget,trusted});}catch(e){return {error:e.message};}},[data,archiveData,fixtures,options.date,options.mode,options.phase,options.window,options.basis,options.headToHead,positions,firstTarget,trusted]);
    const shownRate=metric==='firstTeam'?'share':rate;
    return h('section',{className:'matchup-panel','aria-label':'Positional matchup evidence'},h('h2',null,'Positional matchup evidence'),
      h('div',{className:'controls matchup-controls'},
        h('label',null,'Statistic',h('select',{'aria-label':'Matchup statistic',value:metric,onChange:e=>setMetric(e.target.value)},Object.entries(M.METRICS).map(([k,l])=>h('option',{key:k,value:k},k==='points'?'Points · full game':k==='firstTeam'?'First Team Basket · opening only':l)))),
        h('label',null,'Positions',h('select',{'aria-label':'Matchup positions',value:positions,onChange:e=>setPositions(e.target.value)},h('option',{value:'broad'},'G / F / C · recorded roles'),h('option',{value:'strict'},'PG / SG / SF / PF / C · strict'))),
        metric==='firstTeam'?h('label',null,'Opening score definition',h('select',{'aria-label':'Matchup opening score',value:firstTarget,onChange:e=>setFirstTarget(e.target.value)},h('option',{value:'including-free-throws'},'First team score · includes free throws'),h('option',{value:'field-goals'},'First team made field goal'))):h('label',null,'Compare as',h('select',{'aria-label':'Matchup rate',value:rate,onChange:e=>setRate(e.target.value)},h('option',{value:'per48'},'Per 48 player-minutes'),h('option',{value:'perGame'},'Per team game'),h('option',{value:'share'},'Share of recorded production')))),
      note(metric==='firstTeam'?'Opening scoring shares only, separate from full-game points.':'Full-game statistics · includes overtime. Positional patterns describe history, not individual defensive assignments.'),
      h('details',{className:'matchup-methodology'},h('summary',null,'Definitions, position coverage & history policy'),
      note(metric==='firstTeam'?'Opening tendencies only: one first score per team per game. Shares use all verified first-team scoring events, including unknown roles. This is separate from full-game points and from who scores first in the whole game.':'Per 48 player-minutes adjusts for the time recorded by each position group; it is not pace or possession adjusted. Per-game totals can reflect more players or playing time.'),
      note('Roles belong to each historical appearance and team stint. Gamebook positions take priority; dated box-score G/F/C labels are used when the PDF omits a role. Strict five-position mode uses complete, hash-linked, same-game NBA starter role sets where verified; remaining broad labels stay unknown. These patterns do not identify individual defenders or guarantee a matchup advantage.'),
      note('Prior-season comparisons describe the teams in that season. They do not move a traded player’s old-team production onto the current roster.'),
      options.mode==='upcoming'&&options.basis==='auto'&&note('Automatic history uses current-season records once both teams have completed games in this scope; otherwise it uses labeled prior-season history. These descriptive charts have separate sample requirements from Parlay and EV predictions.')),
      metric==='threes'&&note('Main chart: made threes from verified full-game boxes. The shooting breakdown separates 3PM, 3PA and pooled 3P% for both histories.'),
      metric==='blocks'&&note('Blocks belong to the player recording the block. Opponents vs a team means opposing blockers; it does not identify the positions of shooters whose shots were blocked.'),
      metric==='assists'&&note('Assists belong to the passer’s position.'),
      ['rebounds','offensiveRebounds','defensiveRebounds'].includes(metric)&&note('Rebounds are player-credited rebounds; unassigned team rebounds are excluded. Offensive and defensive splits use verified gamebook counts.'),
      result.error?h('div',{className:'matchup-unavailable',role:'alert'},'Positional comparisons unavailable: '+result.error):!result.comparisons.length?h('div',{className:'matchup-unavailable',role:'status'},'No matchup on this selected date. Choose a saved game date or an available scheduled game.'):result.comparisons.map(c=>h('article',{key:c.fixture.id,className:'matchup-fixture','data-fixture-id':c.fixture.id},
        h('h3',null,`${c.fixture.away} @ ${c.fixture.home}`),
        c.unavailable?h('div',{className:'matchup-unavailable',role:'status'},c.unavailable):h(React.Fragment,null,
          h('p',{className:'matchup-scope'},`${c.season} ${c.isArchive?'· prior-season history · historical team rosters':'· selected-season history'} · ${window.FTBScoutingHistory.PHASES[options.phase]} · ${options.window==='0'?'all games in scope':'last '+options.window+(options.headToHead?' meetings':' games per team')} · ${options.headToHead?'head-to-head only':'all opponents'}`),
          note(c.isArchive?`Completed prior-season games only; every result precedes ${options.date}. Each side’s actual statistics-through date is shown below.`:c.scopeMode==='review'?'Season review uses the complete verified season, including the selected game when present. Choose Historical pregame research to exclude selected-day and later results.':`Only completed games before ${options.date} are included. Same-day games are excluded.`),
          c.headToHead&&note('Both directions use the same head-to-head meetings. A team’s production and its opponent’s allowance therefore describe the same events and can match exactly.'),
          h('div',{className:'matchup-directions'},c.directions.map(d=>h(Direction,{key:d.production.team,d,metric,rate:shownRate,teamColors}))),
          note(`League reference: ${c.reference[metric].games} team games from the same season, competition, date cutoff and per-team window, across all opponents. Percent differences are descriptive; no prediction or EV is calculated here.`)))));
  };
})();
