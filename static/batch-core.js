import {validateNeed,matchEligible,SUBJECTS} from './browser-api.js';
import {csvCell,addDays} from './utils.js';
export const BATCH_FIELDS=['school_id','subject','pathway','start_date','end_date','hours','urgency','allow_cross_academy','max_distance_km','max_travel_minutes'];
export const batchLimit=staticMode=>staticMode?100:3000;
export function parseCSV(text){
  text=text.replace(/^\uFEFF/,'');const rows=[];let row=[],cell='',quoted=false,closed=false;
  for(let i=0;i<text.length;i++){const c=text[i];if(quoted){if(c==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=c;}
    else if(c==='"'){if(cell||closed)throw Error(`Ligne ${rows.length+1} : guillemet inattendu`);quoted=true;}
    else if(c===';'||c==='\n'||c==='\r'){row.push(cell);cell='';closed=false;if(c!==';'){rows.push(row);row=[];if(c==='\r'&&text[i+1]==='\n')i++;}}
    else{if(closed)throw Error(`Ligne ${rows.length+1} : caractère après guillemet fermant`);cell+=c;}}
  if(quoted)throw Error(`Ligne ${rows.length+1} : guillemet non fermé`);if(cell||row.length||closed){row.push(cell);rows.push(row);}return rows;
}
export function validateBatch(rows,schools,{limit=100}={}){
  const errors=[],needs=[],schoolMap=new Map(schools.map(s=>[s.id,s]));
  if(!rows.length||rows[0].length!==BATCH_FIELDS.length||rows[0].some((v,i)=>v!==BATCH_FIELDS[i]))return {needs:[],errors:[{row:1,message:'En-tête strict requis : '+BATCH_FIELDS.join(';')}],count:Math.max(0,rows.length-1)};
  if(rows.length<2||rows.length-1>limit)return {needs:[],errors:[{row:1,message:`Lot de 1 à ${limit} besoins requis.`}],count:rows.length-1};
  rows.slice(1).forEach((row,i)=>{try{if(row.length!==BATCH_FIELDS.length)throw Error('Nombre de colonnes incorrect');const n=Object.fromEntries(BATCH_FIELDS.map((k,j)=>[k,row[j]]));
    for(const k of ['hours','max_distance_km','max_travel_minutes']){if(!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(n[k]))throw Error(`${k} : nombre décimal requis`);n[k]=Number(n[k]);}
    if(!['true','false'].includes(n.allow_cross_academy))throw Error('allow_cross_academy : true ou false requis');n.allow_cross_academy=n.allow_cross_academy==='true';
    const {urgency,max_distance_km,...matching}=n;validateNeed({...matching,max_distance_km},[schoolMap.get(n.school_id)].filter(Boolean));validateNeed({...matching,urgency},[schoolMap.get(n.school_id)].filter(Boolean),true);needs.push(n);
  }catch(e){errors.push({row:i+2,message:e.message});}});
  return {needs:errors.length?[]:needs,errors,count:rows.length-1};
}
export const needsCSV=needs=>'\uFEFF'+[BATCH_FIELDS,...needs.map(n=>BATCH_FIELDS.map(k=>n[k]))].map(r=>r.map(csvCell).join(';')).join('\r\n');
export function generateNeeds(schools,today,count=100){const usable=schools.filter(s=>s.pathways?.length);if(!usable.length)throw Error('Annuaire sans voie disponible');return Array.from({length:count},(_,i)=>{const s=usable[i%usable.length];return {school_id:s.id,subject:SUBJECTS[i%SUBJECTS.length],pathway:s.pathways[i%s.pathways.length],start_date:addDays(today,7+7*Math.floor(i/100)),end_date:addDays(today,11+7*Math.floor(i/100)),hours:6+i%3*3,urgency:i%5===0?'Urgente':'Normale',allow_cross_academy:false,max_distance_km:150,max_travel_minutes:90};});}
export const edgeKey=(t,s)=>JSON.stringify([[t.lon,t.lat],[s.lon,s.lat]]);
const overlap=(a,b)=>a.start_date<=b.end_date&&a.end_date>=b.start_date;
const knownRoute=(r,now)=>r&&Number.isFinite(r.expires)&&r.expires>now&&r.expires<=now+(r.status==='no_route'?3600000:604800000)&&((r.status==='ok'&&typeof r.duration_seconds==='number'&&Number.isFinite(r.duration_seconds)&&r.duration_seconds>=0)||r.status==='no_route');
export function eligibility(needs,schools,teachers,assignments=[],progress=()=>{}){
  const sm=new Map(schools.map(s=>[s.id,s])),bySubject=new Map();for(const t of teachers)for(const subject of t.subjects){if(!bySubject.has(subject))bySubject.set(subject,[]);bySubject.get(subject).push(t);}
  return needs.map((n,i)=>{const s=sm.get(n.school_id);const candidates=matchEligible(n,s,bySubject.get(n.subject)||[],assignments,n.max_distance_km).candidates;
    if(i%50===0)progress(i,needs.length);return candidates.map(c=>({teacher_id:c.teacher.id,distance_km:c.distance_km,key:edgeKey(c.teacher,s),pair:[[c.teacher.lon,c.teacher.lat],[s.lon,s.lat]]}));});
}
export function plan(needs,edges,routes=null,now=Date.now()){
  const usable=edges.map((list,i)=>routes?list.filter(e=>{const r=routes[e.key];return knownRoute(r,now)&&r.status==='ok'&&r.duration_seconds<=needs[i].max_travel_minutes*60;}).sort((a,b)=>routes[a.key].duration_seconds-routes[b.key].duration_seconds||a.distance_km-b.distance_km):list);
  const order=needs.map((_,i)=>i).sort((a,b)=>(needs[b].urgency==='Urgente')-(needs[a].urgency==='Urgente')||usable[a].length-usable[b].length||needs[a].start_date.localeCompare(needs[b].start_date)||a-b);
  const assigned=new Map(),occupancy=new Map();
  const set=(i,e)=>{const old=assigned.get(i);if(old)occupancy.set(old.teacher_id,(occupancy.get(old.teacher_id)||[]).filter(j=>j!==i));if(e){assigned.set(i,e);if(!occupancy.has(e.teacher_id))occupancy.set(e.teacher_id,[]);occupancy.get(e.teacher_id).push(i);}else assigned.delete(i);};
  for(const i of order){let chosen=false;for(const e of usable[i]){const conflicts=(occupancy.get(e.teacher_id)||[]).filter(j=>overlap(needs[j],needs[i]));if(!conflicts.length){set(i,e);chosen=true;break;}}
    // Bounded one-hop augmentation: free the only eligible profile by moving
    // an earlier flexible proposal. Never discard a covered urgent mission.
    if(!chosen)for(const e of usable[i]){const conflicts=(occupancy.get(e.teacher_id)||[]).filter(j=>overlap(needs[j],needs[i]));if(conflicts.length!==1)continue;const j=conflicts[0];const alt=usable[j].find(a=>a.teacher_id!==e.teacher_id&&!(occupancy.get(a.teacher_id)||[]).some(k=>k!==j&&overlap(needs[k],needs[j])));if(alt){set(j,alt);set(i,e);break;}}
  }
  const rows=needs.map((n,i)=>{const e=assigned.get(i);let status,reason;if(e){status='proposed';reason=routes?'Trajet IGN compatible vérifié':'Éligibilité géographique provisoire ; aucun temps routier';}
    else if(routes&&edges[i].some(e=>!knownRoute(routes[e.key],now))){status='deferred';reason='Trajets inconnus, expirés ou service indisponible : poursuivre le calcul';}
    else{status='unassigned';reason=!edges[i].length?'Aucun profil éligible (discipline, voie, secteur, académie, dates, capacité, mobilité ou affectation existante)':usable[i].length?'Conflit de dates entre propositions du lot':'Aucun trajet vérifié compatible';}
    return {row:i+2,...n,status,reason,teacher_id:e?.teacher_id??'',duration_seconds:routes&&e?routes[e.key].duration_seconds:null};});
  const counts={total:rows.length,proposed:0,deferred:0,unassigned:0};for(const r of rows)counts[r.status]++;return {rows,counts};
}
export function resultsCSV(result){const fields=['row',...BATCH_FIELDS,'status','reason','teacher_id','duration_seconds'];return '\uFEFF'+[fields,...result.rows.map(n=>fields.map(k=>n[k]))].map(r=>r.map(csvCell).join(';')).join('\r\n');}
