/* GitHub Pages demo backend. No server, HR roster or multi-user locking.
 * State is untrusted, versioned and read back after writes. Only public school
 * coordinates leave the browser, via IGN; never names, subjects or dates.
 */
import {parisDate} from './utils.js';
export const STATE_KEY='relai-lycees-static-v1';
const CACHE_KEY=STATE_KEY+'-routes';
const PROVIDER='IGN Géoplateforme',SOURCE='https://data.geopf.fr/navigation/itineraire';
export const SUBJECTS=['Mathématiques','Lettres modernes','Anglais','Histoire-géographie','Physique-chimie','SVT','SES','Philosophie','Économie-gestion','EPS','Sciences industrielles'];
export const PATHWAYS=['Générale','Technologique','Professionnelle'];
const copy=x=>JSON.parse(JSON.stringify(x));
const own=(x,k)=>Object.prototype.hasOwnProperty.call(x,k);
const valueOr=(x,k,fallback)=>own(x,k)?x[k]:fallback;
function object(x){if(!x||typeof x!=='object'||Array.isArray(x))throw Error('Objet JSON requis.');return x;}
function fields(x,allowed){object(x);if(Object.keys(x).some(k=>!allowed.includes(k)))throw Error('Champs inconnus : aucune donnée personnelle acceptée.');}
function num(x,low,high){if(typeof x!=='number'||!Number.isFinite(x)||x<low||x>high)throw Error('Nombre fini hors plage.');return x;}
function bool(x){if(typeof x!=='boolean')throw Error('Booléen JSON requis.');return x;}
function date(x){if(typeof x!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(x)||x<'0001-01-01'||!Number.isFinite(Date.parse(x+'T12:00:00Z'))||new Date(x+'T12:00:00Z').toISOString().slice(0,10)!==x)throw Error('Date ISO YYYY-MM-DD valide requise.');return x;}
function identifier(x){if(!Number.isSafeInteger(x)||x<1)throw Error('Identifiant de besoin invalide.');return x;}
function coords(x){if(x.lat==null||x.lon==null)return false;num(x.lat,-90,90);num(x.lon,-180,180);return true;}
function point(p){if(!Array.isArray(p)||p.length!==2)throw Error('Point invalide.');num(p[0],-180,180);num(p[1],-90,90);return p;}
export function distanceKm(a,b){const r=Math.PI/180;const h=Math.sin((b[1]-a[1])*r/2)**2+Math.cos(a[1]*r)*Math.cos(b[1]*r)*Math.sin((b[0]-a[0])*r/2)**2;return 6371.0088*2*Math.asin(Math.sqrt(Math.min(1,Math.max(0,h))));}
export function validateNeed(payload,schools,creation=false){
  fields(payload,['school_id','subject','pathway','start_date','end_date','hours','allow_cross_academy','max_travel_minutes',...(creation?['urgency']:['max_distance_km','need_id'])]);
  const school=schools.find(s=>s.id===payload.school_id);if(!school)throw Error('Établissement inconnu.');
  if(!SUBJECTS.includes(payload.subject)||!PATHWAYS.includes(payload.pathway)||!school.pathways.includes(payload.pathway))throw Error('Discipline ou voie inconnue ou non proposée.');
  if(date(payload.start_date)>date(payload.end_date))throw Error('La fin doit suivre le début.');
  num(payload.hours,.1,60);bool(valueOr(payload,'allow_cross_academy',false));num(valueOr(payload,'max_travel_minutes',90),0,480);coords(school);
  if(creation&&!['Normale','Urgente'].includes(valueOr(payload,'urgency','Normale')))throw Error('Urgence inconnue.');
  if(!creation){num(valueOr(payload,'max_distance_km',150),0,2000);if(own(payload,'need_id'))identifier(payload.need_id);}
  return {...payload,allow_cross_academy:valueOr(payload,'allow_cross_academy',false),max_travel_minutes:valueOr(payload,'max_travel_minutes',90),...(creation?{urgency:valueOr(payload,'urgency','Normale')}:{})};
}
export function matchEligible(need,school,teachers,assignments,radius=150){
  num(radius,0,2000);const candidates=[],excluded=[],exclusions={};
  for(const teacher of teachers){const reasons=[];let dist=null;
    if(coords(school)&&coords(teacher))dist=distanceKm([teacher.lon,teacher.lat],[school.lon,school.lat]);else reasons.push('Coordonnées indisponibles');
    if(!teacher.subjects.includes(need.subject))reasons.push('Discipline incompatible');
    if(!teacher.pathways.includes(need.pathway))reasons.push('Voie incompatible');
    if(!['Public','Privé'].includes(school.sector)||!['Public','Privé'].includes(teacher.sector))reasons.push('Secteur inconnu : compatibilité non vérifiable');else if(school.sector!==teacher.sector)reasons.push('Secteur incompatible');
    if(school.academy!==teacher.academy&&!(teacher.cross_academy&&need.allow_cross_academy))reasons.push('Académie incompatible');
    if(teacher.available_from>need.start_date||teacher.available_until<need.end_date)reasons.push('Disponibilité insuffisante');
    if(teacher.capacity_hours<need.hours)reasons.push('Capacité hebdomadaire insuffisante');
    if(dist!==null&&dist>teacher.max_distance_km)reasons.push('Hors mobilité du profil');
    if(dist!==null&&dist>radius)reasons.push('Hors rayon du besoin');
    if(assignments.some(a=>a.teacher_id===teacher.id&&a.start_date<=need.end_date&&a.end_date>=need.start_date))reasons.push('Affectation sur une période chevauchante');
    const rounded=dist===null?null:Math.round(dist*100)/100;
    if(reasons.length){for(const r of reasons)exclusions[r]=(exclusions[r]||0)+1;excluded.push({teacher_id:teacher.id,name:teacher.name,distance_km:rounded,reasons});}
    else candidates.push({teacher,distance_km:rounded,_distance:dist,reasons:['Discipline, voie, secteur et académie compatibles','Disponible sur toute la période','Capacité suffisante et aucune affectation chevauchante','Distance dans les deux rayons de mobilité']});
  }
  candidates.sort((a,b)=>a._distance-b._distance||b.teacher.capacity_hours-a.teacher.capacity_hours||a.teacher.id.localeCompare(b.teacher.id));
  for(const c of candidates)delete c._distance;
  return {candidates,excluded,summary:{eligible:candidates.length,total:teachers.length,exclusions}};
}
export function validateRoute(body,start,end){
  object(body);point(start);point(end);const code=body.error?.code??body.code;
  if(['NO_ROUTE','NoRoute','NO_PATH','POINT_NOT_FOUND'].includes(code))return {status:'no_route',duration_seconds:null};
  if(body.error)throw Error('Erreur IGN.');
  for(const [key,value] of Object.entries({resource:'bdtopo-osrm',profile:'car',optimization:'fastest',distanceUnit:'kilometer',timeUnit:'second',crs:'EPSG:4326'}))if(valueOr(body,key,value)!==value)throw Error('Unités ou profil IGN inattendus.');
  const duration=num(body.duration,0,1e9),distance=num(body.distance,0,1e7),g=body.geometry;
  if(g?.type!=='LineString'||!Array.isArray(g.coordinates)||g.coordinates.length<2||g.coordinates.length>25000)throw Error('Tracé routier absent.');
  g.coordinates.forEach(point);
  for(const [field,original,endpoint] of [['start',start,g.coordinates[0]],['end',end,g.coordinates.at(-1)]]){
    if(typeof body[field]!=='string'||!/^[-+\d.eE]+,[-+\d.eE]+$/.test(body[field]))throw Error('Extrémité IGN absente.');
    const snapped=point(body[field].split(',').map(Number));if(distanceKm(snapped,original)>1||distanceKm(endpoint,original)>1)throw Error('Ancrage IGN éloigné de plus de 1 km.');
  }
  if(typeof body.resourceVersion!=='string'||body.resourceVersion.length<1||body.resourceVersion.length>120)throw Error('Version IGN absente.');
  return {status:'ok',duration_seconds:duration,road_distance_km:distance,geometry:{type:'LineString',coordinates:copy(g.coordinates)},resource_version:body.resourceVersion};
}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export class RouteClient {
  constructor(options={}){this.fetch=options.fetch??globalThis.fetch.bind(globalThis);this.storage=options.storage;this.now=options.now??Date.now;this.sleep=options.sleep??sleep;this.budget=Math.min(80,Math.max(0,options.budget??80));this.deadlineMs=Math.min(30000,Math.max(0,options.deadlineMs??30000));this.limit=Math.min(120,Math.max(1,options.cacheLimit??120));this.nextStart=0;this.running=false;this.cache={};
    try{const raw=this.storage?.getItem(CACHE_KEY)||'{}';if(raw.length>3000000)throw Error();const stored=JSON.parse(raw);if(stored.version===1&&stored.entries&&typeof stored.entries==='object'&&!Array.isArray(stored.entries))this.cache=Object.fromEntries(Object.entries(stored.entries).filter(([,e])=>e&&Number.isFinite(e.expires)&&e.expires>this.now()).slice(0,this.limit));}catch{/* Route cache is disposable, mission state is not. */}
  }
  key(pair){return JSON.stringify(['ign-car-v1','bdtopo-osrm','car','fastest',pair]);}
  cached(key,pair){const e=this.cache[key];if(!e||typeof e.expires!=='number'||e.expires<=this.now())return null;
    try{const r=e.route;if(r.provider!==PROVIDER||!['ok','no_route','unavailable'].includes(r.status))throw Error();const ttl=r.status==='ok'?604800000:r.status==='no_route'?3600000:30000;if(e.expires>this.now()+ttl)throw Error();
      if(r.status==='ok')validateRoute({duration:r.duration_seconds,distance:r.road_distance_km,resourceVersion:r.resource_version,start:pair[0].join(','),end:pair[1].join(','),geometry:r.geometry},...pair);
      return {...copy(r),cached:true};
    }catch{delete this.cache[key];return null;}
  }
  save(key,route){const now=this.now(),ttl=route.status==='ok'?604800000:route.status==='no_route'?3600000:30000;this.cache[key]={route:copy(route),expires:now+ttl,created:now};
    const entries=Object.entries(this.cache).filter(([,v])=>v.expires>now).sort((a,b)=>b[1].created-a[1].created).slice(0,this.limit);
    this.cache=Object.fromEntries(entries);let text=JSON.stringify({version:1,entries:this.cache});while(text.length>3000000&&entries.length){entries.pop();this.cache=Object.fromEntries(entries);text=JSON.stringify({version:1,entries:this.cache});}
    try{this.storage?.setItem(CACHE_KEY,text);}catch{/* Quota must not convert a real route into a fictitious fallback. */}
  }
  async calculate(pair,deadline,signal){
    if(this.now()>=deadline||signal?.aborted)return {status:'deferred',duration_seconds:null};
    while(this.now()<this.nextStart){if(this.nextStart>=deadline)return {status:'deferred',duration_seconds:null};await this.sleep(this.nextStart-this.now());if(this.now()>=deadline||signal?.aborted)return {status:'deferred',duration_seconds:null};}
    // Reserve at the actual start, not the scheduled wakeup: delayed browser
    // timers must never bunch multiple requests into the same quarter-second.
    this.nextStart=this.now()+250;
    const query=new URLSearchParams({resource:'bdtopo-osrm',profile:'car',optimization:'fastest',start:pair[0].join(','),end:pair[1].join(','),geometryFormat:'geojson',getSteps:'false',getBbox:'true',distanceUnit:'kilometer',timeUnit:'second',crs:'EPSG:4326'});
    const controller=new AbortController();const abort=()=>controller.abort();signal?.addEventListener('abort',abort,{once:true});
    let timer,route;try{
      const timed=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('Timeout IGN'));},Math.min(6000,Math.max(1,deadline-this.now())));});
      const request=(async()=>{const response=await this.fetch(SOURCE+'?'+query,{mode:'cors',credentials:'omit',referrerPolicy:'no-referrer',headers:{Accept:'application/json'},signal:controller.signal});if(!response.ok&&![400,404,422].includes(response.status))throw Error('IGN indisponible');
        // Limit bytes before parsing where a real streaming Response is available.
        let body;if(response.body?.getReader){const reader=response.body.getReader(),parts=[];let size=0;while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>4000000){await reader.cancel();throw Error('Réponse IGN trop grande');}parts.push(value);}const all=new Uint8Array(size);let offset=0;for(const p of parts){all.set(p,offset);offset+=p.length;}body=JSON.parse(new TextDecoder().decode(all));}else body=await response.json();
        return validateRoute(body,...pair);})();
      route=await Promise.race([request,timed]);
    }catch{route={status:'unavailable',duration_seconds:null};}finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
    route={...route,provider:PROVIDER,resource:'bdtopo-osrm',profile:'car',optimization:'fastest',computed_at:new Date(this.now()).toISOString(),cached:false};if(!signal?.aborted)this.save(this.key(pair),route);return route;
  }
  async routeMany(pairs,{fresh=false,signal}={}){
    pairs.forEach(p=>{if(!Array.isArray(p)||p.length!==2)throw Error('Paire invalide.');p.forEach(point);});
    const deferred=()=>({status:'deferred',duration_seconds:null,cached:false});const results=pairs.map(p=>fresh?null:this.cached(this.key(p),p));const pending=new Map();
    pairs.forEach((p,i)=>{if(!results[i]){const key=this.key(p);if(!pending.has(key))pending.set(key,{pair:p,indices:[]});pending.get(key).indices.push(i);results[i]=deferred();}});
    if(!pending.size||this.running||signal?.aborted)return results;this.running=true;const deadline=this.now()+this.deadlineMs;const jobs=[...pending.values()].slice(0,this.budget);let next=0;
    const worker=async()=>{while(next<jobs.length&&this.now()<deadline&&!signal?.aborted){const job=jobs[next++];const route=await this.calculate(job.pair,deadline,signal);if(this.now()<=deadline&&!signal?.aborted)for(const i of job.indices)results[i]=route;}};
    try{await Promise.all(Array.from({length:Math.min(2,jobs.length)},worker));return results;}finally{this.running=false;}
  }
}
function validateTeacher(t,schools){
  const allowed=['id','name','subjects','academy','sector','lat','lon','base_label','capacity_hours','max_distance_km','available_from','available_until','pathways','cross_academy'];fields(t,allowed);if(Object.keys(t).length!==allowed.length)throw Error('Schéma de profil démo strict requis.');
  if(typeof t.id!=='string'||!/^DEMO-\d{4,8}$/.test(t.id)||t.name!=='Profil démo '+t.id.slice(5))throw Error('Profil anonyme DEMO requis.');
  for(const [key,choices] of [['subjects',SUBJECTS],['pathways',PATHWAYS]])if(!Array.isArray(t[key])||!t[key].length||new Set(t[key]).size!==t[key].length||t[key].some(v=>!choices.includes(v)))throw Error('Discipline ou voie invalide.');
  if(!coords(t))throw Error('Coordonnées requises.');const anchor=schools.find(s=>s.academy===t.academy&&s.sector===t.sector&&s.lat===t.lat&&s.lon===t.lon);
  if(!anchor||!['Public','Privé'].includes(t.sector))throw Error('Ancrage officiel d’établissement requis.');
  if(typeof t.base_label!=='string'||!t.base_label.length||t.base_label.length>300)throw Error('Libellé démo invalide.');
  num(t.capacity_hours,.1,60);num(t.max_distance_km,0,2000);bool(t.cross_academy);if(date(t.available_from)>date(t.available_until))throw Error('Disponibilité invalide.');
  return {...t,base_label:`Ancrage administratif fictif · ${anchor.name} · ${anchor.city}`};
}
function freshState(){return {version:1,revision:0,nextId:1,needs:[],assignments:[],teachers:[]};}
export function createBrowserAPI(options={}){
  const fetcher=options.fetch??globalThis.fetch.bind(globalThis);let storage=options.storage;
  if(!storage)try{storage=globalThis.localStorage;}catch{/* handled explicitly on state reads */}
  const router=options.router??new RouteClient({...options,storage,fetch:fetcher});let loading;
  async function load(){if(!loading)loading=Promise.all(['schools','calendar','teachers'].map(async name=>{const response=await fetcher(`./data/${name}.json`,{credentials:'same-origin'});if(!response.ok)throw Error('Instantané public indisponible.');return response.json();})).then(([s,c,t])=>{
      const teachers=Array.isArray(t)?t:t.teachers;if(!Array.isArray(s.schools)||!Array.isArray(c.holidays)||!Array.isArray(teachers))throw Error('Instantané public invalide.');
      // Public builder owns these anonymous generated snapshots, not an RH export.
      if(teachers.some(x=>!/^DEMO-\d{4,8}$/.test(x.id)||x.name!=='Profil démo '+x.id.slice(5)))throw Error('Instantané de profils non anonyme.');
      return {schools:s.schools,metadata:s.metadata||{},calendar:c,teachers};
    }).catch(e=>{loading=null;throw e;});return loading;}
  function read(data){try{
    if(!storage)throw Error();const raw=storage.getItem(STATE_KEY);if(raw===null)return freshState();if(raw.length>3000000)throw Error();const state=JSON.parse(raw);fields(state,['version','revision','nextId','needs','assignments','teachers']);
    if(state.version!==1||!Number.isSafeInteger(state.revision)||state.revision<0||!Array.isArray(state.needs)||!Array.isArray(state.assignments)||!Array.isArray(state.teachers)||state.needs.length>5000||state.teachers.length+data.teachers.length>5000)throw Error();identifier(state.nextId);
    const needIds=new Set(),teachers=new Set(data.teachers.map(t=>t.id));for(const t of state.teachers){validateTeacher(t,data.schools);if(teachers.has(t.id))throw Error();teachers.add(t.id);}
    for(const n of state.needs){fields(n,['school_id','subject','pathway','start_date','end_date','hours','allow_cross_academy','max_travel_minutes','urgency','id','status','teacher_id','created_at']);const {id,status,teacher_id,created_at,...payload}=n;identifier(id);validateNeed(payload,data.schools,true);if(needIds.has(id)||id>=state.nextId||!['open','assigned','closed'].includes(status)||!Number.isFinite(Date.parse(created_at)))throw Error();needIds.add(id);if(status==='assigned'?!teachers.has(teacher_id):teacher_id!==null)throw Error();}
    const assigned=new Set();for(const a of state.assignments){fields(a,['id','need_id','teacher_id','start_date','end_date','hours','created_at','route']);identifier(a.id);const n=state.needs.find(n=>n.id===a.need_id);if(!n||n.status!=='assigned'||assigned.has(n.id)||n.teacher_id!==a.teacher_id||n.start_date!==a.start_date||n.end_date!==a.end_date||n.hours!==a.hours)throw Error();assigned.add(n.id);const t=[...data.teachers,...state.teachers].find(t=>t.id===a.teacher_id),s=data.schools.find(s=>s.id===n.school_id),r=a.route;if(r?.provider!==PROVIDER||r.status!=='ok')throw Error();validateRoute({duration:r.duration_seconds,distance:r.road_distance_km,resourceVersion:r.resource_version,start:[t.lon,t.lat].join(','),end:[s.lon,s.lat].join(','),geometry:r.geometry},[t.lon,t.lat],[s.lon,s.lat]);}
    if(state.needs.some(n=>n.status==='assigned'&&!assigned.has(n.id)))throw Error();return state;
  }catch{throw Error('Stockage local indisponible ou corrompu. Aucun écrasement automatique ; réinitialisez explicitement la démo dans Données.');}}
  function write(state,data,expectedRevision){const latest=read(data);if(latest.revision!==expectedRevision)throw Error('État modifié dans un autre onglet. Actualisez puis réessayez.');state.revision=expectedRevision+1;const text=JSON.stringify(state);if(text.length>3000000)throw Error('Limite du stockage local atteinte.');try{storage.setItem(STATE_KEY,text);if(storage.getItem(STATE_KEY)!==text)throw Error();}catch{throw Error('Stockage local : enregistrement non vérifié (quota ou accès refusé).');}return read(data);}
  const allTeachers=(data,state)=>[...data.teachers,...state.teachers];
  function storedNeed(state,id){const n=state.needs.find(n=>n.id===identifier(id));if(!n)throw Error('Besoin introuvable.');return n;}
  async function routed(n,data,state,teachers,opts={}){
    const school=data.schools.find(s=>s.id===n.school_id);const result=matchEligible(n,school,teachers,state.assignments,n.max_distance_km??150);const base=result.candidates;const pairs=base.map(c=>[[c.teacher.lon,c.teacher.lat],[school.lon,school.lat]]);const routes=await router.routeMany(pairs,opts);let calculated=0,unavailable=0,deferred=0;const candidates=[];
    base.forEach((c,i)=>{const r=routes[i]??{status:'unavailable'};let reason;if(r.status==='ok'){calculated++;if(r.duration_seconds>n.max_travel_minutes*60)reason='Temps de trajet supérieur au maximum';else candidates.push({...c,straight_line_km:c.distance_km,duration_seconds:r.duration_seconds,duration_minutes:r.duration_seconds/60,road_distance_km:r.road_distance_km,route:r,reasons:[...c.reasons,'Temps de trajet estimé dans le maximum demandé']});}else if(r.status==='deferred'){deferred++;reason='Calcul différé : budget ou délai de calcul atteint, réessayez';}else{unavailable++;reason='Itinéraire indisponible';}
      if(reason){result.excluded.push({teacher_id:c.teacher.id,name:c.teacher.name,distance_km:c.distance_km,reasons:[reason],route_status:r.status});result.summary.exclusions[reason]=(result.summary.exclusions[reason]||0)+1;}});
    candidates.sort((a,b)=>a.duration_seconds-b.duration_seconds||a.road_distance_km-b.road_distance_km||b.teacher.capacity_hours-a.teacher.capacity_hours||a.teacher.id.localeCompare(b.teacher.id));const partial=!!deferred||routes.some(r=>!['ok','no_route'].includes(r.status));
    return {...result,candidates,summary:{...result.summary,eligible:candidates.length,compatible_before_routing:base.length,routes_calculated:calculated,routes_unavailable:unavailable,routes_deferred:deferred},routing:{provider:PROVIDER,profile:'car',traffic:false,partial,warning:partial?'Comparaison partielle : seuls les trajets calculés sont classés. Réessayez ; aucune durée fictive n’est substituée.':null,requested:base.length,calculated,unavailable,deferred},method:'Durée exacte en voiture, puis distance routière, capacité décroissante et identifiant. Aucun emploi du temps disponible : toute affectation chevauchante bloque le profil. Validation humaine simulée uniquement.'};
  }
  return async function api(path,payload,signal){
    const data=await load();if(path==='/api/reset'){fields(payload,['confirm']);if(payload.confirm!==true)throw Error('Confirmation explicite requise.');try{storage.removeItem(STATE_KEY);storage.removeItem(CACHE_KEY);router.cache={};if(storage.getItem(STATE_KEY)!==null)throw Error();}catch{throw Error('Réinitialisation du stockage local impossible.');}return {reset:true};}
    const state=read(data),revision=state.revision,teachers=allTeachers(data,state);
    if(payload===undefined){
      if(path==='/api/calendar')return copy(data.calendar);
      if(path==='/api/needs')return copy({needs:state.needs});
      if(path==='/api/bootstrap')return copy({schools:data.schools,teachers,needs:state.needs,assignments:state.assignments,metadata:{...data.metadata,teacher_count:teachers.length,demo:true,subjects:SUBJECTS,pathways:PATHWAYS,today:parisDate(new Date().toISOString()),calendar:data.calendar.metadata,storage:'Navigateur uniquement — non synchronisé entre appareils ; pas de verrouillage inter-onglets.',routing:{provider:PROVIDER,profile:'car',traffic:false,rate_limit_rps:4,uncached_budget:80,batch_deadline_seconds:30}}});
    }else{
      if(JSON.stringify(payload).length>1048576)throw Error('Import limité à 1 Mio.');
      if(path==='/api/needs'){const n=validateNeed(payload,data.schools,true);if(state.needs.length>=5000)throw Error('Limite de 5000 besoins.');n.id=state.nextId++;identifier(state.nextId);Object.assign(n,{status:'open',teacher_id:null,created_at:new Date().toISOString()});state.needs.push(n);const saved=write(state,data,revision);return copy({need:storedNeed(saved,n.id)});}
      if(path==='/api/match'){const n=validateNeed(payload,data.schools);if(n.need_id){const saved=storedNeed(state,n.need_id);for(const k of ['school_id','subject','pathway','start_date','end_date','hours','allow_cross_academy','max_travel_minutes'])if(n[k]!==saved[k])throw Error('Le scénario doit correspondre au besoin enregistré.');}return copy(await routed(n,data,state,teachers,{signal}));}
      if(path==='/api/teachers/import'){fields(payload,['teachers','confirm_demo']);if(payload.confirm_demo!==true||!Array.isArray(payload.teachers)||!payload.teachers.length||payload.teachers.length>200||teachers.length+payload.teachers.length>5000)throw Error('Import de 1 à 200 profils fictifs exclusivement, confirmation requise.');const ids=new Set(teachers.map(t=>t.id));const batch=payload.teachers.map(t=>{const validated=validateTeacher(t,data.schools);if(ids.has(t.id))throw Error('Identifiant déjà présent : import append-only.');ids.add(t.id);return validated;});state.teachers.push(...batch);const saved=write(state,data,revision);if(saved.teachers.length!==state.teachers.length)throw Error('Import non vérifié.');return {imported:batch.length};}
      const found=/^\/api\/needs\/([1-9]\d*)\/(assign|release|close)$/.exec(path);if(found){const id=identifier(Number(found[1])),action=found[2],n=storedNeed(state,id);fields(payload,action==='assign'?['teacher_id','max_distance_km','max_travel_minutes']:[]);
        if(action==='assign'){
          if(n.status!=='open')throw Error('Le besoin n’est plus ouvert.');num(valueOr(payload,'max_distance_km',150),0,2000);if((valueOr(payload,'max_travel_minutes',n.max_travel_minutes))!==n.max_travel_minutes)throw Error('Trajet maximum différent du besoin enregistré.');
          const t=teachers.find(t=>t.id===payload.teacher_id);if(!t)throw Error('Profil introuvable.');
          const result=await routed({...n,max_distance_km:valueOr(payload,'max_distance_km',150)},data,state,[t],{fresh:true,signal});const candidate=result.candidates[0];if(!candidate||signal?.aborted)throw Error('Profil incompatible, itinéraire indisponible ou trajet supérieur au maximum.');
          // Re-read after network await: no cached eligibility or pre-await state writes.
          const latest=read(data),current=storedNeed(latest,id),currentTeacher=allTeachers(data,latest).find(x=>x.id===t.id);if(current.status!=='open'||JSON.stringify(current)!==JSON.stringify(n)||!currentTeacher||!matchEligible(current,data.schools.find(s=>s.id===current.school_id),[currentTeacher],latest.assignments,valueOr(payload,'max_distance_km',150)).candidates.length)throw Error('Conflit : besoin modifié ou profil déjà affecté.');
          const assignment={id,need_id:id,teacher_id:t.id,start_date:current.start_date,end_date:current.end_date,hours:current.hours,created_at:new Date().toISOString(),route:candidate.route};latest.assignments.push(assignment);current.status='assigned';current.teacher_id=t.id;const saved=write(latest,data,latest.revision);return copy({need:storedNeed(saved,id),assignment:saved.assignments.find(a=>a.need_id===id)});
        }
        if(action==='release'){if(n.status!=='assigned')throw Error('Aucune affectation à libérer.');state.assignments=state.assignments.filter(a=>a.need_id!==id);n.status='open';n.teacher_id=null;}else{if(n.status!=='open')throw Error('Libérez l’affectation avant de clôturer.');n.status='closed';}return copy({need:storedNeed(write(state,data,revision),id)});
      }
    }
    throw Error('Ressource statique introuvable.');
  };
}
