import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {selectCase,timelinePoints,sceneAt,VIDEO_SECONDS} from '../docs/core.mjs';

const runs=JSON.parse(await readFile(new URL('../demo/verified_runs.json',import.meta.url)));
const fixture=JSON.parse(await readFile(new URL('../data/incidents/STOP-001.json',import.meta.url)));

test('replay uses the actual recorded case and its source evidence',()=>{
  const value=selectCase(runs,'enhanced');
  assert.equal(value.result.first_observed.lead_seconds,18);
  assert.equal(value.run.model_calls,1);
  assert.equal(value.result.source.sha256,runs.enhanced.trace[0].result.source.sha256);
});
test('missing and unknown remain distinct outcomes',()=>{
  assert.equal(selectCase(runs,'missing').result.status,'insufficient_evidence');
  assert.equal(selectCase(runs,'unknown').result.status,'no_pre_stop_anomaly');
  assert.throws(()=>selectCase(runs,'arbitrary'));
});
test('timeline preserves observed sample times and pressure values',()=>{
  const points=timelinePoints(fixture);
  assert.equal(points.length,31);
  assert.equal(points[0].t,0);
  assert.equal(points.at(-1).t,60);
  assert.equal(points.find(p=>p.pressure<5).t,42);
  assert.equal(points.find(p=>p.blocked).t,54);
});
test('walkthrough is shorter than three minutes with complete scene coverage',()=>{
  assert(VIDEO_SECONDS<180);
  assert.equal(sceneAt(0).index,0);
  assert.equal(sceneAt(VIDEO_SECONDS).index,6);
  assert.equal(sceneAt(VIDEO_SECONDS+10).index,6);
});
