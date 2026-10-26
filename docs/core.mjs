export const SCENES=[8,18,18,28,20,20,14];
export const VIDEO_SECONDS=SCENES.reduce((a,b)=>a+b,0);
export function sceneAt(seconds){
  let elapsed=Math.max(0,Math.min(VIDEO_SECONDS,seconds)),start=0;
  for(let index=0;index<SCENES.length;index++){
    if(elapsed<start+SCENES[index]||index===SCENES.length-1)
      return {index,progress:Math.min(1,(elapsed-start)/SCENES[index])};
    start+=SCENES[index];
  }
}
export function selectCase(runs,key){
  const expected={enhanced:'observed',missing:'insufficient_evidence',unknown:'no_pre_stop_anomaly'};
  if(!Object.hasOwn(expected,key))throw new Error('Unknown replay case');
  const run=runs[key],result=run?.trace?.at(-1)?.result;
  if(result?.status!==expected[key]||run.model_calls!==1||!result.source?.sha256)
    throw new Error('Recorded evidence failed validation');
  return {key,run,result};
}
export function timelinePoints(fixture){
  const stop=Date.parse(fixture.stop_at);
  return fixture.samples.map(row=>{
    const t=(Date.parse(row.at)-stop)/1000+60;
    if(!Number.isFinite(t)||t<0||t>60||!Number.isFinite(row.pressure_bar))throw new Error('Invalid timeline sample');
    return {t,pressure:row.pressure_bar,blocked:row.photoeye_blocked};
  }).sort((a,b)=>a.t-b.t);
}
export function splitSegments(points){
  const result=[];for(const point of points){
    const last=result.at(-1);
    if(!last||point.t-last.at(-1).t!==2)result.push([point]);
    else last.push(point);
  }return result;
}
