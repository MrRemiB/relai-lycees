/* Fingerprint effective data, not just a revision counter. Freshness transitions
 * invalidate snapshots even without an edit. Routes are not roster data. */
export async function contextFingerprint(data,now=Date.now()){
 const b=data.business;
 const stale=v=>!v||Date.parse(v)>now||now-Date.parse(v)>(b?.config.freshness_days??30)*86400000;
 const text=JSON.stringify([b,(b?.profiles||[]).map(p=>[p.teacher_id,stale(p.source_updated_at),p.timetable?.known?stale(p.timetable.source_updated_at):null]),data.schools.map(s=>[s.id,s.academy,s.sector,s.pathways,s.lat,s.lon]),data.teachers,(data.assignments||[]).map(({route,...a})=>a)]);
 const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('');
}
