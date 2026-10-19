/* Read-only experimental prices/probabilities. No bet placement. */
(function(){
  'use strict';
  const E=window.FTBEV,H=window.FTBScoutingHistory,L=window.FTBLineups,Q=window.FTBProjectedLineups,h=React.createElement,{useState,useEffect,useMemo,useRef}=React;
  const SOURCE='https://raw.githubusercontent.com/lopoke89-ops/ftb-updated-model/nba-live-odds/odds.json';
  const VERSION_SOURCE='https://api.github.com/repos/lopoke89-ops/ftb-updated-model/git/ref/heads/nba-live-odds';
  const pct=v=>Number.isFinite(v)?(100*v).toFixed(1)+'%':'—',signed=v=>(v>0?'+':'')+pct(v);
  const formatTime=t=>t?new Date(t).toLocaleString('en-US',{timeZone:'America/Chicago',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' CT':'Not available';
  const label=q=>(q.market==='points'?'Points':'Made threes')+' · '+(q.side==='at-least'?q.line+'+':q.side+' '+q.line);
  window.FTBEVPanel=function EVPanel({data,archiveData,fixtures=[],rosters={},liveContext={},trusted=false,mode,phase,period,headToHead,excludedIds=[],teamColors={}}){
    const model=window.__FTB_EV_MODEL__,[snapshot,setSnapshot]=useState(window.__FTB_EV_ODDS_CACHE__||null),[source,setSource]=useState({status:'checking'}),[market,setMarket]=useState('all'),[side,setSide]=useState('all'),[positiveOnly,setPositive]=useState(true),[provisional,setProvisional]=useState(true),[bestOnly,setBest]=useState(true),[message,setMessage]=useState('');
    const [clock,setClock]=useState(Date.now());
    const sequence=useRef(0),loading=useRef(false),refresh=useRef(null),now=Math.max(Date.now(),clock,liveContext.now||0);
    const supported=mode==='upcoming'&&!headToHead&&period==='0'&&['all','regular-season'].includes(phase)&&fixtures.every(f=>f.phase==='regular-season');
    async function load(){
      if(loading.current||!supported)return;loading.current=true;const token=++sequence.current,attempt=new Date().toISOString();setSource(s=>({...s,status:'checking',lastAttempt:attempt}));
      try{const version=await fetch(VERSION_SOURCE+'?read='+Date.now()+'-'+token,{cache:'no-store',signal:AbortSignal.timeout(12000)});if(!version.ok)throw Error('Odds version HTTP '+version.status);const ref=await version.json();
        if(ref.ref!=='refs/heads/nba-live-odds'||ref.object?.type!=='commit'||!/^[a-f0-9]{40}$/.test(ref.object?.sha||''))throw Error('Odds version identity mismatch');
        if(token!==sequence.current)return;const commit=ref.object.sha,url='https://raw.githubusercontent.com/lopoke89-ops/ftb-updated-model/'+commit+'/odds.json';
        const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('Odds feed HTTP '+r.status);const next=await r.json();
        if(next.schemaVersion!==1||next.bookmaker!=='fanduel'||next.region!=='TN'||!next.fixtures||typeof next.fixtures!=='object')throw Error('Odds feed identity/schema mismatch');
        if(token!==sequence.current)return;window.__FTB_EV_ODDS_CACHE__=next;setSnapshot(next);setSource({status:'loaded',lastAttempt:attempt,lastSuccess:new Date().toISOString(),captureAt:next.checkedAt,commit,url});
      }catch(error){if(token===sequence.current)setSource(s=>({...s,status:'unavailable',lastAttempt:attempt,error:error.message}));}
      finally{if(token===sequence.current)loading.current=false;}
    }
    refresh.current=load;
    useEffect(()=>{
      const time=Date.now(),deadlines=fixtures.flatMap(f=>[Date.parse(f.scheduledTipoff),...(snapshot?.fixtures?.[f.id]?.quotes||[]).flatMap(q=>[Date.parse(q.capturedAt)+E.MAX_AGE+1,Date.parse(q.fanduelTipoff)])]).filter(t=>Number.isFinite(t)&&t>time);
      if(!deadlines.length)return;const timer=setTimeout(()=>setClock(Date.now()),Math.max(1,Math.min(...deadlines)-time));return()=>clearTimeout(timer);
    },[snapshot,fixtures,clock]);
    useEffect(()=>{if(!supported)return;load();const stop=Q?.startRefresh(()=>refresh.current());return()=>{++sequence.current;loading.current=false;stop?.();};},[supported]);
    const integrity=trusted&&model?.version===E.VERSION&&model.archiveEvidenceHash===archiveData?.meta?.evidenceContentHash;
    const state=useMemo(()=>{
      if(!integrity||!supported||!fixtures.length)return null;const before=fixtures[0].date;
      const games=[...archiveData.games.map(g=>({...g,season:archiveData.meta.season})),...(data.meta.season!==archiveData.meta.season?data.games.map(g=>({...g,season:data.meta.season})):[])];
      return E.buildState(games,{before});
    },[integrity,supported,archiveData,data,fixtures[0]?.date]);
    const predictionState=useMemo(()=>{
      const predictions={},eligibility={};if(!state)return {predictions,eligibility};
      for(const fixture of fixtures)for(const team of [fixture.home,fixture.away])for(const p of rosters[team]||[]){
        const injuries=L.availableInjuries(liveContext.injuries||{},liveContext.confirmedStarters||{},fixture,now);
        const available=H.pickEligibility(String(p.id),{...liveContext,injuries,fresh:liveContext.fresh||L.validConfirmation(liveContext.confirmedStarters?.[p.id],fixture,now)});
        eligibility[p.id]=excludedIds.includes(p.id)?{excluded:true,reason:'Excluded scenario'}:available;
        const f=E.features(state,p.id,team,fixture.home===team?fixture.away:fixture.home),view=Q.playerView(p.id,team,fixture,liveContext.lineupContext,now);
        const roleUncertain=!f.reason&&((!!view.record&&f.recentStarterRate<.5)||(!view.record&&view.teamStatus!=='unavailable'&&f.recentStarterRate>.8));
        for(const market of ['points','threes'])predictions[fixture.id+'|'+team+'|'+p.id+'|'+market]=roleUncertain?{reason:'Projected role differs from recent starts; current-role probability unavailable'}:{...E.predict(f,market,model)};
      }return {predictions,eligibility};
    },[state,fixtures,rosters,liveContext.injuries,liveContext.fresh,liveContext.lineupContext,JSON.stringify(excludedIds),Math.floor(now/300000)]);
    const evaluated=useMemo(()=>integrity&&supported?E.evaluateQuotes({snapshot,fixtures,rosters,...predictionState,now}):{rows:[],audit:[]},[integrity,supported,snapshot,fixtures,rosters,predictionState,now]);
    let rows=evaluated.rows.filter(r=>(market==='all'||r.quote.market===market)&&(side==='all'||r.quote.side===side)&&(!positiveOnly||r.ev>0)&&(provisional||!r.provisional));
    if(bestOnly){const seen=new Set();rows=rows.filter(r=>{const key=r.quote.fixtureId+'|'+r.quote.playerId+'|'+r.quote.market;if(seen.has(key))return false;seen.add(key);return true;});}
    function record(results,filters){
      return {schemaVersion:2,recordType:'experimental-ev-snapshot',capturedAt:new Date().toISOString(),modelVersion:model.version,modelHash:model.modelHash,engineHash:model.engineHash,protocolHash:model.protocolHash,forwardProtocolHash:model.forwardProtocolHash,rulesProfileHash:model.rulesProfileHash,
        archiveEvidenceHash:archiveData.meta.evidenceContentHash,currentEvidenceHash:data.meta.evidenceContentHash,source:{url:SOURCE,bookmaker:'fanduel',region:'TN',checkedAt:snapshot?.checkedAt,transport:source},
        fixtures,filters,displayedSelectionKeys:rows.map(r=>r.quote.key),lineupContext:liveContext.lineupContext,availabilitySource:liveContext.availabilitySource,results,audit:evaluated.audit,
        interpretation:'Conditional on participation; experimental estimates, not verified issuance receipts. No joint parlay probability. Historical calibration does not establish profitable EV.'};
    }
    useEffect(()=>{if(!evaluated.rows.length||!window.FTBEVArchive||source.status!=='loaded'||!source.commit||source.captureAt!==snapshot?.checkedAt)return;let active=true;
      window.FTBEVArchive.save(record(evaluated.rows,{selection:'all supported offers before display filters',market,side,positiveOnly,provisional,bestOnly})).then(()=>{if(active)setMessage('Pregame offers, predictions and displayed selections retained in this browser. Export saved history to keep a separate copy.');}).catch(error=>{if(active)setMessage(error.message+' · Save EV evidence can still download the visible rows.');});return()=>{active=false;};
    },[snapshot?.checkedAt,predictionState,market,side,positiveOnly,provisional,bestOnly,source.status,source.commit]);
    function download(value,name){const text=JSON.stringify(value,null,2),url=URL.createObjectURL(new Blob([text],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
    function save(){
      if(!source.commit||source.captureAt!==snapshot?.checkedAt){setMessage('Wait for a verified odds version before saving this capture.');return;}
      const time=Math.max(Date.now(),liveContext.now||0);
      if(rows.some(r=>E.quoteState(r.quote,fixtures.find(f=>f.id===r.quote.fixtureId),time)!=='fresh')){setClock(time);setMessage('An offer expired or its game started. Refresh odds before saving evidence.');return;}
      const value=record(rows,{market,side,positiveOnly,provisional,bestOnly});
      download(value,'ftb-ev-'+fixtures[0].date+'-'+Date.now()+'.json');setMessage('Visible EV evidence downloaded.');
    }
    async function exportHistory(){try{const records=await window.FTBEVArchive.all();download({schemaVersion:1,recordType:'experimental-ev-history',exportedAt:new Date().toISOString(),records},'ftb-ev-history-'+Date.now()+'.json');setMessage(records.length+' saved pregame snapshots exported.');}catch(error){setMessage(error.message);}}
    async function gradeHistory(){try{if(!window.FTBEVGrading||!integrity)throw Error('Verified history/grading is unavailable');const records=await window.FTBEVArchive.all(),report=window.FTBEVGrading.grade(records,[archiveData,data]);download(report,'ftb-ev-grading-'+Date.now()+'.json');setMessage(`Research grading downloaded: ${report.counts.win+report.counts.loss+report.counts.push} completed, ${report.counts.void} void, ${report.counts.pending} pending, ${report.counts.review+report.counts.invalid} need review. Repeated snapshots are retained; sportsbook settlement is unverified.`);}catch(error){setMessage(error.message);}}
    return h('section',{className:'ev-panel'},h('h2',null,'EV Bets',h('span',{className:'ev-experimental'},'Experimental estimates')),
      h('p',null,'FanDuel Tennessee · full-game Points and Made Threes · probabilities conditional on participation. EV requires 20 prior appearances with the current team and supported exact-line history. Existing Parlay grades and season-average targets are unchanged. First Basket and First Team Basket EV are not modeled.'),
      !supported?h('div',{className:'analyst-notice',role:'status'},'Choose Upcoming game, regular season, All available in scope, and All opponents. EV uses prior regular-season appearances with the current team, with labeled prior-season history. Playoff, preseason, review, and head-to-head EV are unavailable.'):
      !integrity?h('div',{className:'analyst-notice',role:'status'},'Verified probability model/history mismatch. EV estimates are withheld.'):
      h(React.Fragment,null,
        h('div',{className:'ev-source',role:'status'},h('button',{type:'button',onClick:load,disabled:source.status==='checking'},source.status==='checking'?'Checking odds…':'Refresh odds'),h('span',null,`Last request: ${formatTime(source.lastAttempt)} · last successful read: ${formatTime(source.lastSuccess)} · collector checked: ${formatTime(snapshot?.checkedAt)}`),
          source.error&&h('strong',null,source.error+' · last capture retained with its original age'),h('small',null,'Checks every 5 minutes while this view is open. Quotes older than 5 minutes, cached after source failures, suspended, or past either advertised tipoff are excluded.')),
        h('details',{className:'ev-filters'},h('summary',null,'EV filters',h('span',null,`${rows.length} displayed · ${evaluated.rows.length} priced · ${evaluated.audit.length} withheld`)),
          h('div',{className:'controls'},h('label',null,'Market ',h('select',{'aria-label':'EV market',value:market,onChange:e=>setMarket(e.target.value)},h('option',{value:'all'},'Points and Threes'),h('option',{value:'points'},'Points'),h('option',{value:'threes'},'Made Threes'))),
            h('label',null,'Bet type ',h('select',{'aria-label':'EV bet type',value:side,onChange:e=>setSide(e.target.value)},h('option',{value:'all'},'All offered types'),h('option',{value:'over'},'Over'),h('option',{value:'under'},'Under'),h('option',{value:'at-least'},'Milestones'))),
            ...[[positiveOnly,setPositive,'Positive estimated EV only'],[provisional,setProvisional,'Include provisional availability / role'],[bestOnly,setBest,'Best offer per player / prop']].map(([checked,setter,label])=>h('label',{key:label},h('input',{type:'checkbox',checked,onChange:e=>setter(e.target.checked)}),label)))),
        h('p',{className:'ev-note'},'Highest estimated conditional EV first. Estimates assume participation and ordinary full-game settlement. Unsupported tail lines, insufficient current-team samples, and projected role changes are withheld. Future-game availability remains provisional. Prior-season transfer and live injury effects remain unvalidated. Large differences from bookmaker prices can reflect model error; no profitable advantage is established.'),
        !rows.length&&h('div',{className:'analyst-notice',role:'status'},!fixtures.length?'No selected upcoming fixtures.':!snapshot?'No FanDuel capture available yet.':evaluated.rows.length?'No estimates match these filters.':'No fresh, supported offers for this scope. Check the withheld evidence below; stale quotes do not produce fresh EV.'),
        h('div',{className:'ev-table-wrap'},h('table',{className:'ev-table'},h('thead',null,h('tr',null,['Player / bet','FanDuel','Model win / push','Break-even¹','Conditional EV','Evidence / availability'].map(s=>h('th',{key:s,scope:'col'},s)))),
          h('tbody',null,rows.map(r=>h('tr',{key:r.quote.key,style:{'--team-color':teamColors[r.quote.team]||'#64748b'}},
            h('th',{scope:'row'},h('strong',{className:'player-name'},r.quote.player),h('small',null,r.quote.team+' · '+label(r.quote)),h('a',{href:r.quote.source,target:'_blank',rel:'noreferrer'},'FanDuel market')),
            h('td',null,(r.quote.american>0?'+':'')+r.quote.american,h('small',null,formatTime(r.quote.capturedAt))),h('td',null,pct(r.probabilities.win),h('small',null,'Push '+pct(r.probabilities.push)),h('small',null,'Decisive win '+pct(r.conditionalWin))),h('td',null,pct(r.breakEven)),
            h('td',{className:r.ev>0?'ev-positive':'ev-negative'},signed(r.ev),h('small',null,'per $1 of action')),
            h('td',null,`${r.features.n} appearances · ${r.features.role} comparison`,h('small',null,`${(r.features.historySeasons||[]).join(' / ')} · Through ${r.features.through} · ${r.features.teams.join(' / ')} history`),h('small',null,r.features.roleSource||'Historical position proxy'),h('strong',{className:r.provisional?'ev-provisional':'ev-ready'},r.provisional?'Provisional':'Availability checked'),
              h('details',null,h('summary',null,'Projection details'),h('p',null,r.availability),h('p',null,`Calibrated mean ${r.projection.toFixed(2)} ${r.quote.market}; raw distribution mean ${(r.rawProjection??r.projection).toFixed(2)}. ${r.features.minutes.toFixed(1)} minutes. FGA/FGM ${r.features.fga.toFixed(1)}/${r.features.fgm.toFixed(1)}; 3PA/3PM ${r.features.threePa.toFixed(1)}/${r.features.threePm.toFixed(1)}; FTA/FTM ${r.features.fta.toFixed(1)}/${r.features.ftm.toFixed(1)}.`),h('p',null,`Correlation ${r.features.correlation[r.quote.market].toFixed(3)}. Opponent allowance is per G/F/C player-minute, shrunk toward league rates. Learned offense/defense powers: ${model.markets[r.quote.market].offensePower}/${model.markets[r.quote.market].defensePower}.`),h('p',null,`Decisive-outcome win chance ${pct(r.conditionalWin)}; loss ${pct(r.probabilities.loss)}. Assumes participation; pushes/voids return stake. Model ${model.version}.`)))))))),
        h('small',{className:'ev-note'},'¹ Compare break-even with decisive win, which excludes pushes. EV retains pushes as zero profit: P(win) × (decimal odds − 1) − P(loss). EV is conditional on participation and ordinary settlement. Single-bet EV does not establish combined-parlay EV.'),
        h('div',{className:'controls'},h('button',{type:'button',onClick:save,disabled:!rows.length},'Save EV evidence'),h('button',{type:'button',onClick:exportHistory},'Export saved EV history'),h('button',{type:'button',onClick:gradeHistory,disabled:!integrity},'Grade saved EV history')),h('p',{role:'status'},message),
        h('details',null,h('summary',null,'Withheld offers and collector coverage'),h('ul',null,evaluated.audit.map((a,i)=>h('li',{key:i},`${a.player||'Offer'}: ${a.reason}`))),h('ul',null,fixtures.flatMap(f=>(snapshot?.fixtures?.[f.id]?.issues||(!snapshot?.fixtures?.[f.id]?['No captured event']:[])).map((issue,i)=>h('li',{key:f.id+'|'+i},`${f.away} @ ${f.home}: ${issue}`))))),
        h('details',{className:'ev-diagnostics'},h('summary',null,'Probability diagnostics and limitations'),h('p',null,'Development through Dec 15, 2025; calibration Dec 16–Feb 15; later-date diagnostics Feb 16–Apr 12, 2026. No selected-day results enter features. The completed archive was already inspected. These are retrospective diagnostics, not an unseen live record or historical odds-profit test.'),
          ...['points','threes'].map(m=>{const full=model.markets[m].diagnostic,d=model.markets[m].supportedDiagnostic;return h('p',{key:m},`${m}, supported lines: ${d.appearances} appearances / ${d.fixtures} fixtures. Brier ${d.brier.toFixed(4)} (mean baseline ${d.meanBaseline.brier.toFixed(4)}); log loss ${d.logLoss.toFixed(4)} (baseline ${d.meanBaseline.logLoss.toFixed(4)}). Full grid: Brier ${full.brier.toFixed(4)} / ${full.appearances} appearances. These differently selected samples cannot be compared as evidence that the support filter improved accuracy.`);}),
          h('p',null,'Diagnostics use predefined historical thresholds, not archived FanDuel offers. Historical pregame injury/lineup announcements and FanDuel prices were not archived. G/F/C labels are position proxies, not defender assignments; missing NBA printed roles use the stored historical roster label. Projected role changes and insufficient current-team history are withheld. Quotes outside the calibration range or without five prior wins and losses at the target are withheld. Prior-season estimates remain experimental. Save pregame quotes and predictions now to evaluate future outcomes.'))));
  };
})();
