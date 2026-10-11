/* NBA Daily Lineups: explicit status and position, never last-game starters. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.FTBLineups=factory();})(typeof window!=='undefined'?window:this,function(){
  'use strict';
  const POS=['PG','SG','SF','PF','C'];
  const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const urlFor=date=>'https://stats.nba.com/js/data/leaders/00_daily_lineups_'+date.replace(/-/g,'')+'.json';
  function validConfirmation(record,fixture,now=Date.now()){
    const age=now-Date.parse(record?.capturedAt),tip=Date.parse(fixture?.scheduledTipoff);
    return !!record&&record.status==='confirmed'&&record.source===urlFor(fixture?.date||'')&&record.fixtureId===fixture?.id&&
      record.date===fixture?.date&&fixture?.status==='pre'&&Number.isFinite(tip)&&now<tip&&age>=0&&age<=5*60*1000&&
      [fixture.home,fixture.away].includes(record.team)&&POS.includes(record.position)&&/^\d+$/.test(record.nbaId);
  }
  function parse(json,{date,fixtures,rosters,capturedAt,now=Date.now()}){
    if(!Array.isArray(json?.games))throw Error('NBA lineup games unavailable');
    const confirmed={},projected={},issues=[];
    for(const g of json.games){
      const matches=fixtures.filter(f=>f.date===date&&f.home===g.homeTeam?.teamAbbreviation&&f.away===g.awayTeam?.teamAbbreviation);
      if(matches.length!==1)continue;
      const fixture=matches[0];
      if(Number(g.gameStatus)!==1||fixture.status!=='pre'||now>=Date.parse(fixture.scheduledTipoff))continue;
      for(const side of ['homeTeam','awayTeam']){
        const box=g[side],team=box.teamAbbreviation,players=(box.players||[]).filter(p=>POS.includes(p.position));
        if(players.length!==5||new Set(players.map(p=>p.position)).size!==5||new Set(players.map(p=>String(p.personId))).size!==5){issues.push(team+': complete five-position lineup unavailable');continue;}
        const mapped=players.map(p=>{
          const roster=(rosters[team]||[]).filter(r=>r.nbaId?String(r.nbaId)===String(p.personId):norm(r.name)===norm(p.playerName));
          return roster.length===1?{id:String(roster[0].id),nbaId:String(p.personId),name:p.playerName,team,position:p.position,
            status:p.lineupStatus==='Confirmed'&&p.rosterStatus==='Active'?'confirmed':'projected',
            fixtureId:fixture.id,nbaGameId:String(g.gameId),date,capturedAt,source:urlFor(date),sourceTimestamp:p.timestamp||null}:null;
        });
        if(mapped.some(p=>!p)||new Set(mapped.map(p=>p.id)).size!==5){issues.push(team+': lineup identities unresolved');continue;}
        const allConfirmed=mapped.every(p=>p.status==='confirmed');
        for(const p of mapped){if(allConfirmed&&validConfirmation(p,fixture,now))confirmed[p.id]=p;else projected[p.id]={...p,status:'projected'};}
      }
    }
    return {confirmed,projected,issues,capturedAt,date,source:urlFor(date)};
  }
  function availableInjuries(injuries,confirmed,fixture,now){
    const result={...injuries};
    for(const [id,p] of Object.entries(confirmed))if(validConfirmation(p,fixture,now)&&result[id]?.status==='QUESTIONABLE')
      result[id]={...result[id],status:'AVAILABLE',carriedForward:false,capturedAt:p.capturedAt,reason:'NBA confirmed active starter',source:p.source};
    return result;
  }
  return {POS,urlFor,parse,validConfirmation,availableInjuries};
});
