import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {businessCheck,validateBusiness} from '../static/business-core.js';
const fixtures=JSON.parse(fs.readFileSync(new URL('../tests/fixtures/business-parity.json',import.meta.url)));
const python=JSON.parse(execFileSync(process.env.PYTHON||'python3',['-c',`import json; from business import business_check; f=json.load(open('tests/fixtures/business-parity.json')); print(json.dumps([business_check(x['need'],x['school'],x['teacher'],x['business'],x['assignments'],x['now']) for x in f],ensure_ascii=False))`],{cwd:new URL('..',import.meta.url),encoding:'utf8'}));
for(const [i,x] of fixtures.entries())test('Python/browser business parity: '+x.name,()=>{validateBusiness(x.business,[x.school],[x.teacher]);const actual=businessCheck(x.need,x.school,x.teacher,x.business,x.assignments,x.now*1000);assert.equal(actual.status,x.status);assert.deepEqual(python[i],actual);});
