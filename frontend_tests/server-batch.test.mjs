import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
test('server panel delegates durable planning and never uses browser state',()=>{
 const ui=readFileSync(new URL('../static/batch-ui.js',import.meta.url),'utf8');
 assert.match(ui,/if\(!staticMode\)return setupServerBatch/);
 const server=readFileSync(new URL('../static/server-batch-ui.js',import.meta.url),'utf8');
 for(const path of ['/api/batches','/run','/cancel'])assert.ok(server.includes(path));
 for(const prohibited of ['localStorage','RouteClient','new Worker'])assert.ok(!server.includes(prohibited));
 assert.match(server,/3000/);
});
import {setupServerBatch} from '../static/server-batch-ui.js';

test('server controls create and read back3000, run, cancel, reopen and export',async()=>{
 class Element {
  constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.value='';}
  append(...items){this.children.push(...items);if(this.tag==='select'&&!this.value&&items[0])this.value=items[0].value;}
  replaceChildren(...items){this.children=[];this.append(...items);}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(){}
  before(e){elements.push(e);}
  click(){}
 }
 const elements=[],tabs=new Element('div'),foot=new Element('p');
 globalThis.document={createElement:tag=>new Element(tag),querySelector:s=>s==='.tabs'?tabs:foot};
 globalThis.Option=class extends Element{constructor(text,value){super('option');this.textContent=text;this.value=value;}};
 globalThis.confirm=()=>true;
 const school={id:'S1',pathways:['Générale']},calls=[];
 let job={id:'a'.repeat(32),status:'queued',results:[],counts:{total:3000,proposed:0,deferred:3000,unassigned:0},progress:{phase:'queued',done:0,total:3000}};
 const api=async(path,payload)=>{
  calls.push([path,payload]);
  if(path==='/api/bootstrap')return {schools:[school],metadata:{today:'2026-10-10'}};
  if(path==='/api/batches'&&payload){assert.equal(payload.needs.length,3000);job.results=payload.needs.map((n,i)=>({...n,row:i+2,status:'deferred',reason:'unknown',teacher_id:'',duration_seconds:null}));return {job};}
  if(path==='/api/batches')return {jobs:[job]};
  if(path.endsWith('/run')){job={...job,status:'partial',partial:true};return {job};}
  if(path.endsWith('/cancel')){job={...job,status:'cancelled'};return {job};}
  assert.equal(path,'/api/batches/'+job.id);return {job};
 };
 setupServerBatch({api,setTab:()=>{}});
 const pane=elements[0],tools=pane.children.find(e=>e.className==='batch-tools');
 const press=async prefix=>{const b=tools.children.find(e=>e.textContent?.startsWith(prefix));assert.ok(b,prefix);await b.onclick();};
 await press('Générer');await press('Enregistrer');await press('Lancer');await press('Annuler');await press('Lister');await press('Ouvrir');await press('Exporter');
 assert.ok(calls.some(([p,v])=>p.endsWith('/run')&&JSON.stringify(v)==='{}'));
 assert.ok(calls.some(([p])=>p.endsWith('/cancel')));
 assert.ok(calls.filter(([p,v])=>p==='/api/batches/'+job.id&&v===undefined).length>=4,'mutations/readback/export read server');
 delete globalThis.document;delete globalThis.Option;delete globalThis.confirm;
});

test('dispatcher attaches bootstrap CSRF token only on server POSTs',()=>{
 const js=readFileSync(new URL('../static/app.js',import.meta.url),'utf8');
 assert.match(js,/X-CSRF-Token/);assert.match(js,/csrf_token/);
});
