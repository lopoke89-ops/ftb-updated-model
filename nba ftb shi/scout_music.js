/* Optional, local soundtrack. One audio element survives all analysis tabs. */
(function(root,factory){
  'use strict';
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(!root||!root.React)return;
  const {createElement:h,useState,useEffect,useRef}=root.React;
  root.FTBScoutMusic=function ScoutMusic(){
    const [state,setState]=useState({status:'off',volume:.18,track:'roundball'}),controller=useRef(null);
    useEffect(()=>{
      let storage;try{storage=root.localStorage;}catch(_){}
      const player=api.createController(root.document.getElementById('scout-background-music'),{storage,onChange:setState});
      controller.current=player;
      return ()=>{controller.current=null;player.destroy();};
    },[]);
    const on=state.status==='playing'||state.status==='loading';
    const track=api.TRACKS.find(t=>t.id===state.track)||api.TRACKS[0];
    const status={off:'Ready to loop',loading:'Loading…',playing:'Looping',paused:'Paused',blocked:'Tap play to allow audio',error:'Audio unavailable · retry'}[state.status];
    return h('div',{className:'scout-music','aria-label':'Background music'},
      h('button',{type:'button',className:on?'music-toggle active':'music-toggle','aria-label':on?'Pause background music':'Play background music','aria-pressed':on,onClick:()=>controller.current?.toggle()},
        h('span',{'aria-hidden':true},on?'Ⅱ':'♪'),h('span',null,on?'MUSIC ON':'MUSIC')),
      h('div',{className:'music-track'},h('select',{'aria-label':'Music track',value:state.track,onChange:e=>controller.current?.selectTrack(e.target.value)},api.TRACKS.map(t=>h('option',{key:t.id,value:t.id},t.label))),h('small',{role:'status','aria-live':'polite'},status)),
      h('label',{className:'music-volume'},h('span',null,'VOL'),h('input',{type:'range',min:0,max:100,step:1,value:Math.round(state.volume*100),'aria-label':'Background music volume',onChange:e=>controller.current?.setVolume(Number(e.target.value)/100)})),
      track.href?h('a',{className:'music-credit',href:track.href,target:'_blank',rel:'noopener noreferrer',title:track.credit},track.credit):h('span',{className:'music-credit',title:track.credit},track.credit));
  };
})(typeof window==='object'?window:null,function(){
  'use strict';
  const KEY='ftb-scout-music-volume-v1';
  const TRACK_KEY='ftb-scout-music-track-v1';
  const TRACKS=Object.freeze([
    Object.freeze({id:'roundball',label:'NBA on NBC · 8-bit',file:'roundball-rock-8bit.mp3',credit:'John Tesh · MIDI: BitMidi',href:'https://bitmidi.com/nba-nbc-mid'}),
    Object.freeze({id:'may-brendan',label:'Battle! May–Brendan · RSE',file:'may-brendan-rse.mp3',credit:'Pokémon RSE · Soundfonts: Exabyte U'}),
    Object.freeze({id:'gym-leader',label:'Battle! Gym Leader · RSE',file:'gym-leader-rse.mp3',credit:'Pokémon RSE · Soundfonts: Exabyte U'}),
    Object.freeze({id:'mt-pyre-peak',label:'Mt. Pyre Peak · RSE',file:'mt-pyre-peak-rse.mp3',credit:'Pokémon RSE · Soundfonts: Exabyte U'}),
    Object.freeze({id:'surfing',label:'Surfing · RSE',file:'surfing-rse.mp3',credit:'Pokémon RSE · Soundfonts: Exabyte U'}),
    Object.freeze({id:'diving',label:'Diving · RSE',file:'diving-rse.mp3',credit:'Pokémon RSE · Soundfonts: Exabyte U'})
  ]);
  function createController(audio,{storage,onChange=()=>{}}={}){
    let volume=.18,status='off',request=0,disposed=false,wanted=false,track='roundball';
    const sources=Object.fromEntries(TRACKS.map(t=>[t.id,audio?.getAttribute?.('data-'+t.id+'-src')||t.file]));
    try{const raw=storage?.getItem(KEY);const saved=raw===null||raw===undefined?NaN:Number(raw);if(Number.isFinite(saved)&&saved>=0&&saved<=1)volume=saved;}catch(_){}
    try{const saved=storage?.getItem(TRACK_KEY);if(TRACKS.some(t=>t.id===saved))track=saved;}catch(_){}
    const publish=()=>{if(!disposed)onChange({status,volume,track});};
    const handlers={
      playing:()=>{if(!wanted){audio.pause();return;}status='playing';publish();},
      pause:()=>{if(!audio.paused)return;if(wanted){wanted=false;request++;}if(status!=='blocked'&&status!=='error'&&status!=='off'){status='paused';publish();}},
      waiting:()=>{if(wanted){status='loading';publish();}},
      error:()=>{if(!audio.error)return;request++;wanted=false;status='error';publish();}
    };
    if(audio){audio.loop=true;audio.volume=volume;if(audio.getAttribute?.('src')!==sources[track])audio.src=sources[track];for(const [event,handler]of Object.entries(handlers))audio.addEventListener(event,handler);}
    else status='error';
    publish();
    async function play(){
      if(disposed||!audio)return;
      const token=++request;wanted=true;status='loading';publish();
      try{
        if(audio.error)audio.load();
        await audio.play();
        if(disposed||token!==request)return;
        status=audio.paused?'paused':'playing';publish();
      }catch(error){
        if(disposed||token!==request)return;
        wanted=false;status=error.name==='NotAllowedError'?'blocked':'error';publish();
      }
    }
    function pause(){request++;wanted=false;audio?.pause();status='paused';publish();}
    return {play,pause,toggle(){if(wanted)pause();else return play();},
      selectTrack(id){
        if(disposed||!audio||id===track||!TRACKS.some(t=>t.id===id))return;
        const resume=wanted,idle=status==='off';request++;wanted=false;audio.pause();track=id;
        audio.src=sources[track];audio.load();status=idle?'off':'paused';
        try{storage?.setItem(TRACK_KEY,track);}catch(_){}publish();
        if(resume)return play();
      },
      setVolume(value){if(!Number.isFinite(value))return;volume=Math.min(1,Math.max(0,value));if(audio)audio.volume=volume;try{storage?.setItem(KEY,String(volume));}catch(_){}publish();},
      destroy(){if(disposed)return;disposed=true;request++;wanted=false;if(audio){for(const [event,handler]of Object.entries(handlers))audio.removeEventListener(event,handler);audio.pause();}}
    };
  }
  return {createController,TRACKS};
});
