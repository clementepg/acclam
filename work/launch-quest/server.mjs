import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createSourceResolver,resolveInside,SourceError} from './source-resolver.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
const workspace=path.resolve(root,'../..');
const port=Number(process.env.ACCLAM_QUEST_PORT||4317);
if(!Number.isInteger(port)||port<1||port>65535)throw Error('ACCLAM_QUEST_PORT must be a valid local TCP port');
const sources=createSourceResolver(workspace);
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const workspaceId=crypto.createHash('sha256').update(root).digest('hex');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.txt':'text/plain; charset=utf-8','.csv':'text/plain; charset=utf-8','.pdf':'application/pdf','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.png':'image/png','.jpg':'image/jpeg'};
function allowedSources(register){
  const allowed=new Set(['work/launch-quest/README.txt']);
  for(const milestone of register.milestones)for(const task of milestone.objectives){
    for(const link of [...(task.sources||[]),...(task.evidence||[]),...(task.proofs||[])])allowed.add(link.path);
  }
  return allowed;
}
const server=http.createServer((req,res)=>{
  res.setHeader('Cache-Control','no-store');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Referrer-Policy','no-referrer');
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'");
  const send=(code,text)=>{res.writeHead(code,{'Content-Type':'text/plain; charset=utf-8'});res.end(text);};
  if(!['GET','HEAD'].includes(req.method))return send(405,'Read-only local viewer');
  if(req.headers.host && !['127.0.0.1','localhost','[::1]'].some(host=>req.headers.host===`${host}:${port}`))return send(403,'Loopback host required');
  try{
    const pathname=new URL(req.url,'http://127.0.0.1').pathname;
    if(pathname==='/viewer-info'){
      res.writeHead(200,{'Content-Type':'application/json; charset=utf-8'});
      return res.end(JSON.stringify({app:'ACCLAM local viewer',pid:process.pid,instance:process.env.ACCLAM_QUEST_INSTANCE||'',workspaceId}));
    }
    const register=JSON.parse(fs.readFileSync(path.join(root,'PROJECT_REGISTER.json'),'utf8'));
    let file;
    if(pathname.startsWith('/source/')){
      const relative=decodeURIComponent(pathname.slice(8));
      if(!allowedSources(register).has(relative))return send(404,'Source is not linked by this register');
      file=sources.resolve(relative);
    }else{
      const name=pathname==='/'?'index.html':pathname.slice(1);
      if(!['index.html','app.js','style.css','progress.json'].includes(name))return send(404,'Not found');
      if(name==='progress.json'){
        const receipt=JSON.parse(fs.readFileSync(path.join(root,'evidence/REGISTER_VERIFICATION.json'),'utf8'));
        if(receipt.registerSha256!==sha(path.join(root,'PROJECT_REGISTER.json')))return send(409,'Register changed. Validate and rebuild the projection.');
        const projection=JSON.parse(fs.readFileSync(path.join(root,'dist/progress.json'),'utf8'));
        if(receipt.projectionRevision!==projection.revision)return send(409,'Projection revision does not match the validated receipt.');
        // Python generator owns content hashing; validate file integrity separately.
        if(receipt.projectionSha256 && receipt.projectionSha256!==sha(path.join(root,'dist/progress.json')))return send(409,'Projection integrity changed. Rebuild from the register.');
      }
      file=resolveInside(path.join(root,'dist'),name);
    }
    const stat=fs.statSync(file);
    res.writeHead(200,{'Content-Type':mime[path.extname(file).toLowerCase()]||'application/octet-stream','Content-Length':stat.size});
    if(req.method==='HEAD')return res.end();
    fs.createReadStream(file).pipe(res);
  }catch(error){
    if(error instanceof SourceError)return send(error.status,error.message);
    send(500,'Local file unavailable. Validate the repository copy or attach its private source dependencies.');
  }
});
server.listen(port,'127.0.0.1',()=>process.stdout.write(`ACCLAM Launch Quest local: http://127.0.0.1:${port}\n`));
server.on('error',error=>{process.stderr.write(`Viewer could not start (${error.code}).\n`);process.exit(1);});
