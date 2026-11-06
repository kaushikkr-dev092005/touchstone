import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../apps/dashboard/index.html',import.meta.url),'utf8');
function extract(name,next){return html.slice(html.indexOf('function '+name+'('),html.indexOf('function '+next+'('));}

test('particle tilt repeats the measured cycle and has distinct burst and horizon states',()=>{
  const context=vm.createContext({MOTION:{cycleMs:2383}});
  vm.runInContext(extract('motionTilt','motionEnvelope')+extract('motionEnvelope','makeStars'),context);
  const horizon=context.motionTilt(1800),burst=context.motionTilt(1800+2383/2);
  assert.ok(horizon>1.5);assert.ok(burst<.07);
  assert.ok(Math.abs(context.motionTilt(1800+2383)-horizon)<1e-8);
  assert.equal(context.motionEnvelope(0),0);assert.equal(context.motionEnvelope(1),0);
  assert.ok(context.motionEnvelope(.5)>.99);
});

test('particle scheduler pauses offscreen, hidden, user-paused, reduced motion and confirmed halt',()=>{
  const cancelled=[];let paints=0;
  const context=vm.createContext({starContext:{},starFrame:0,starTime:1,heroVisible:true,reduceMotion:false,motionPaused:false,
    document:{hidden:false,body:{dataset:{eventLight:'idle'}}},paintStars:()=>paints++,
    requestAnimationFrame:()=>71,cancelAnimationFrame:id=>cancelled.push(id),drawStars:()=>{}});
  vm.runInContext(extract('scheduleStars','finishIntro'),context);
  context.scheduleStars();assert.equal(context.starFrame,71);
  context.scheduleStars();assert.equal(context.starFrame,71);assert.equal(cancelled.length,0);
  for(const [property,value] of [['reduceMotion',true],['motionPaused',true],['heroVisible',false]]){
    context[property]=value;context.scheduleStars();assert.equal(context.starFrame,0);
    context[property]=!value;context.scheduleStars();assert.equal(context.starFrame,71);
  }
  context.document.hidden=true;context.scheduleStars();assert.equal(context.starFrame,0);
  context.document.hidden=false;context.document.body.dataset.eventLight='kill';context.scheduleStars();
  assert.equal(context.starFrame,0);assert.ok(paints>0);
});
