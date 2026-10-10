/* Local QA server: source frontend + existing sanitized teacher snapshot only.
 * No build, no official JSON mutation, no Python, no runtime/source exposure. */
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(new URL('..',import.meta.url).pathname);
const server=http.createServer(async(req,res)=>{try{let url=decodeURIComponent(new URL(req.url,'http://localhost').pathname);let file;if(url==='/'||url==='/index.html')file=path.join(root,'static/index.html');else if(url==='/data/teachers.json')file=path.join(root,'dist/pages/data/teachers.json');else if(['/data/schools.json','/data/calendar.json'].includes(url))file=path.join(root,url.slice(1));else {const relative=url.replace(/^\/static\//,'/').slice(1);if(relative.includes('..')||!relative||!/^[-\w/]+\.(js|css|png|txt)$/.test(relative))throw Error();file=path.join(root,'static',relative);}let body=await readFile(file);if(file.endsWith('/index.html'))body=Buffer.from(body.toString().replace('<head>','<head><meta name="relai-mode" content="static">').replaceAll('/static/','./'));res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':file.endsWith('.png')?'image/png':'text/html');res.setHeader('Cache-Control','no-store');res.end(body);}catch{res.writeHead(404);res.end('Not found');}});
server.listen(8131,'127.0.0.1',()=>console.log('Relai source static QA http://127.0.0.1:8131'));
