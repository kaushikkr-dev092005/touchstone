import {test} from 'node:test';
import assert from 'node:assert/strict';
import {freshContextFetch} from './fresh-context.mjs';

test('unsigned context wait observes a new epoch without altering its response',async()=>{
 let calls=0;
 const next=Response.json({epoch:'2',anchor:'original'});
 const fetch=freshContextFetch(async()=>++calls===1?Response.json({epoch:'1'}):next,{wait:async()=>{}});
 assert.equal(await fetch('https://clearing.example/context'),next);assert.equal(calls,2);
});

test('POST payments and inference requests are never retried, including HTTP 409',async()=>{
 for(const [url,init] of [['https://clearing.example/payments',{method:'POST'}],['http://127.0.0.1/inference/one',{}]]){
  let calls=0;
  const response=new Response('',{status:409});
  const fetch=freshContextFetch(async()=>{calls++;return response;},{wait:async()=>{throw Error('Must not wait or retry')}});
  assert.equal(await fetch(url,init),response);assert.equal(calls,1);
 }
});

test('a temporary context refusal waits for availability but never creates a payment',async()=>{
 let calls=0;
 const fetch=freshContextFetch(async(_url,init)=>{
  assert.equal(init?.method,undefined);return ++calls===1?new Response('',{status:409}):Response.json({epoch:'3'});
 },{wait:async()=>{}});
 assert.deepEqual(await(await fetch('https://clearing.example/context')).json(),{epoch:'3'});assert.equal(calls,2);
});
