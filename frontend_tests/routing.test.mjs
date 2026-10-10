import assert from 'node:assert/strict';
import * as utils from '../static/utils.js';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';

test('durations distinguish genuine zero from missing or invalid estimates',()=>{
  assert.equal(typeof utils.formatDuration,'function');
  for(const value of [null,undefined,NaN,Infinity,-1,'0',false]) assert.equal(utils.formatDuration(value),'Durée indisponible');
  assert.equal(utils.formatDuration(0),'0 min');
  assert.equal(utils.formatDuration(1),'< 1 min');
  assert.equal(utils.formatDuration(960),'16 min');
  assert.equal(utils.formatDuration(3720),'1 h 02');
  assert.equal(utils.formatDuration(3599),'1 h 00');
});
test('only validated provider road LineString geometry is available',()=>{
  assert.equal(typeof utils.hasRouteGeometry,'function');
  const route={status:'ok',provider:'IGN Géoplateforme',geometry:{type:'LineString',coordinates:[[2,46],[2.1,46.1],[2.2,46.2]]}};
  assert.equal(utils.hasRouteGeometry({route}),true);
  for(const bad of [null,{}, {route:{...route,status:'unavailable'}},{route:{...route,geometry:{type:'Point',coordinates:[2,46]}}},{route:{...route,geometry:{type:'LineString',coordinates:[[2,46]]}}},{route:{...route,geometry:{type:'LineString',coordinates:[[2,46],[181,46]]}}},{route:{...route,geometry:{type:'LineString',coordinates:[[2,46],['2',46]]}}}]) assert.equal(utils.hasRouteGeometry(bad),false);
});
function harness(){
  class Element {
    constructor(){this.children=[];this.value='';this.checked=false;this.hidden=false;this.textContent='';}
    append(...children){this.children.push(...children);} replaceChildren(...children){this.children=children;} addEventListener(){} setAttribute(){} reportValidity(){return true;}
  }
  const elements=new Map();const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const drawn=[];
  const context={...utils,console,setTimeout,clearTimeout,AbortController,URL,Blob,Intl,document:{getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>[]},matchMedia:()=>({matches:false}),L:{marker:()=>({bindTooltip(){return this;},addTo(){return this;}}),geoJSON:(geometry)=>{drawn.push(geometry);return {bindTooltip(){return this;},addTo(){return this;},getBounds(){return 'road-bounds';}}}}};
  vm.createContext(context);
  let source=readFileSync(new URL('../static/app.js',import.meta.url),'utf8').replace(/^import .*?;\n/gm,'').replace('wire();initMap();bootstrap();loadCalendar();','');
  vm.runInContext(source+'\nglobalThis.app={state,payload,renderMatches,candidateMap,openNeed,scenario,exportNeeds,saveNeed,assignCandidate,renderNeeds};',context);
  return {context,app:context.app,get,drawn,text:e=>[e.textContent,...e.children.map(c=>typeof c==='string'?c:([c.textContent,...c.children.map(x=>x.textContent)].join(' ')))].join(' ')};
}
test('payload carries maximum minutes including zero',()=>{
  const {app,get}=harness();app.state.selected={id:'school'};get('start').value='2026-10-16';get('end').value='2026-10-17';get('radius').value='150';get('hours').value='12';get('travel').value='0';
  assert.equal(app.payload().max_travel_minutes,0);
  get('travel').value='90';assert.equal(app.payload().max_travel_minutes,90);
});
test('backend time order retained, partial comparison honest and retry available',()=>{
  const {app,get,text,context}=harness();context.candidateMap=()=>{};
  const teacher=id=>({id,name:id,base_label:'Base fictive',capacity_hours:12});
  app.renderMatches({candidates:[{teacher:teacher('fast-road'),distance_km:80,duration_seconds:960,road_distance_km:90},{teacher:teacher('near-slow'),distance_km:2,duration_seconds:3720,road_distance_km:4}],routing:{partial:true,warning:'Service indisponible pour certains profils'},summary:{eligible:2,total:3}});
  assert.match(text(get('candidates').children[0]),/fast-road/);assert.match(text(get('candidates').children[0]),/16 min/);
  assert.match(text(get('candidates').children[0]),/plus rapide parmi les trajets calculés/i);
  assert.match(text(get('routing-status')),/Service indisponible/);assert.ok(get('routing-status').children.some(e=>e.textContent==='Réessayer le calcul des itinéraires'));
});
test('road geometry drawn using GeoJSON, missing geometry never draws a line',()=>{
 const {app,drawn,get}=harness();app.state.selected={lat:46,lon:2};app.state.map={fitBounds(){}};app.state.candidateLayer={clearLayers(){}};
 const candidate={teacher:{name:'Fixture',lat:46.2,lon:2.2,base_label:'Base fictive'},duration_seconds:960,road_distance_km:20,route:{status:'ok',provider:'IGN Géoplateforme',geometry:{type:'LineString',coordinates:[[2.2,46.2],[2.1,46.1],[2,46]]}}};
 app.candidateMap(candidate);assert.equal(drawn.length,1);assert.equal(drawn[0],candidate.route.geometry);
 app.candidateMap({...candidate,route:null});assert.equal(drawn.length,1);assert.match(get('form-status').children[0].textContent,/itinéraire.*indisponible/i);
});
test('saved assignment audit route displayed from assignment collection',()=>{
 const {app,get,text}=harness();app.state.needs=[{id:7,status:'assigned',school_id:'school',teacher_id:'teacher',max_travel_minutes:0}];app.state.assignments=[{need_id:7,route:{duration_seconds:0,road_distance_km:0,provider:'IGN Géoplateforme'}}];
 app.renderNeeds();assert.match(text(get('needs-list')),/Trajet max\. : 0 min/);assert.match(text(get('needs-list')),/Trajet enregistré : 0 min/);assert.match(text(get('needs-list')),/IGN Géoplateforme/);
});
test('saving keeps max minutes and assigning uses stored max consistently',async()=>{
 const {app,get,context}=harness();app.state.selected={id:'school'};app.state.ready=true;get('start').value='2026-10-16';get('end').value='2026-10-17';get('hours').value='12';get('radius').value='150';get('travel').value='90';
 const calls=[];context.api=async(path,payload)=>{calls.push({path,payload});if(path==='/api/needs')return {need:{id:7,status:'open',max_travel_minutes:90}};return {};};context.refreshNeeds=async()=>{};context.renderIdentity=()=>{};context.setTab=()=>{};
 await app.saveNeed();assert.equal(calls[0].payload.max_travel_minutes,90);assert.equal('max_distance_km' in calls[0].payload,false);
 app.state.saved={id:7,status:'open',max_travel_minutes:0};get('travel').value='90';await app.assignCandidate({teacher:{id:'teacher'}});
 assert.equal(calls.find(c=>c.path.endsWith('/assign')).payload.max_travel_minutes,0);
});
test('contract fields and factual IGN privacy copy shipped',()=>{
 const html=readFileSync(new URL('../static/index.html',import.meta.url),'utf8');const app=readFileSync(new URL('../static/app.js',import.meta.url),'utf8');
 assert.match(html,/id="travel"[^>]*min="0"[^>]*max="480"[^>]*value="90"/);
 assert.match(html,/Rayon de présélection \(km à vol d’oiseau\)/);assert.match(html,/https:\/\/data.geopf.fr\/navigation\/itineraire/);
 assert.match(html,/sans trafic en temps réel/);assert.match(html,/noms, disciplines, dates/);assert.doesNotMatch(html,/Aucune durée de trajet n’est estimée|pas des itinéraires|Les plus proches d’abord/);
 assert.match(app,/75000/);assert.match(app,/Calcul des itinéraires…/);assert.match(app,/max_travel_minutes:Number\(\$\('travel'\)\.value\)/);
 assert.match(app,/\$\('travel'\)\.value=need.max_travel_minutes\?\?90/);assert.match(app,/\$\('travel'\)\.value='90'/);assert.match(app,/'max_travel_minutes'/);
 assert.doesNotMatch(app,/L\.polyline|sort\(\(a,b\)=>a.distance_km-b.distance_km\)/);
});
