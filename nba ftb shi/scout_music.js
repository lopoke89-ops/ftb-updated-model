/* Optional, local soundtrack. One audio element survives all analysis tabs. */
(function(root,factory){
  'use strict';
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(!root||!root.React)return;
  const {createElement:h,useState,useEffect,useRef}=root.React;
  root.FTBScoutMusic=function ScoutMusic(){
    const [state,setState]=useState({status:'off',volume:.18}),controller=useRef(null);
    useEffect(()=>{
      let storage;try{storage=root.localStorage;}catch(_){}
      const player=api.createController(root.document.getElementById('scout-background-music'),{storage,onChange:setState});
      controller.current=player;
      return ()=>{controller.current=null;player.destroy();};
    },[]);
    const on=state.status==='playing'||state.status==='loading';
    const status={off:'Ready to loop',loading:'Loading…',playing:'Looping',paused:'Paused',blocked:'Tap play to allow audio',error:'Audio unavailable · retry'}[state.status];
    return h('div',{className:'scout-music','aria-label':'Background music'},
      h('button',{type:'button',className:on?'music-toggle active':'music-toggle','aria-label':on?'Pause background music':'Play background music','aria-pressed':on,onClick:()=>controller.current?.toggle()},
        h('span',{'aria-hidden':true},on?'Ⅱ':'♪'),h('span',null,'8-BIT ',on?'ON':'MUSIC')),
      h('div',{className:'music-track'},h('span',null,'Roundball Rock'),h('small',{role:'status','aria-live':'polite'},status)),
      h('label',{className:'music-volume'},h('span',null,'VOL'),h('input',{type:'range',min:0,max:100,step:1,value:Math.round(state.volume*100),'aria-label':'Background music volume',onChange:e=>controller.current?.setVolume(Number(e.target.value)/100)})),
      h('a',{className:'music-credit',href:'https://bitmidi.com/nba-nbc-mid',target:'_blank',rel:'noopener noreferrer',title:'Music: John Tesh · MIDI source: BitMidi'},'John Tesh · 8-bit cover'));
  };
})(typeof window==='object'?window:null,function(){
  'use strict';
  const KEY='ftb-scout-music-volume-v1';
  function createController(audio,{storage,onChange=()=>{}}={}){
    let volume=.18,status='off',request=0,disposed=false,wanted=false;
    try{const raw=storage?.getItem(KEY);const saved=raw===null||raw===undefined?NaN:Number(raw);if(Number.isFinite(saved)&&saved>=0&&saved<=1)volume=saved;}catch(_){}
    const publish=()=>{if(!disposed)onChange({status,volume});};
    const handlers={
      playing:()=>{if(!wanted){audio.pause();return;}status='playing';publish();},
      pause:()=>{if(wanted){wanted=false;request++;}if(status!=='blocked'&&status!=='error'&&status!=='off'){status='paused';publish();}},
      waiting:()=>{if(wanted){status='loading';publish();}},
      error:()=>{request++;wanted=false;status='error';publish();}
    };
    if(audio){audio.loop=true;audio.volume=volume;for(const [event,handler]of Object.entries(handlers))audio.addEventListener(event,handler);}
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
      setVolume(value){if(!Number.isFinite(value))return;volume=Math.min(1,Math.max(0,value));if(audio)audio.volume=volume;try{storage?.setItem(KEY,String(volume));}catch(_){}publish();},
      destroy(){if(disposed)return;disposed=true;request++;wanted=false;if(audio){for(const [event,handler]of Object.entries(handlers))audio.removeEventListener(event,handler);audio.pause();}}
    };
  }
  return {createController};
});
