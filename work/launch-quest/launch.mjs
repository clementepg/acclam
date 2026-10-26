import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
if(Number(process.versions.node.split('.')[0])<18)throw Error('Node.js 18 or newer is required.');
const workspaceId=crypto.createHash('sha256').update(root).digest('hex');
const port=Number(process.env.ACCLAM_QUEST_PORT||4317);
if(!Number.isInteger(port)||port<1||port>65535)throw Error('ACCLAM_QUEST_PORT must be a valid local TCP port');
const url=`http://127.0.0.1:${port}`;
const sessionPath=path.join(root,'.viewer.json');
function findPython(){
  const options=process.env.ACCLAM_PYTHON?[[process.env.ACCLAM_PYTHON,[]]]:[['python3',[]],['python',[]],...(process.platform==='win32'?[['py',['-3']]]:[])];
  for(const [command,prefix] of options){
    const check=spawnSync(command,[...prefix,'-c','import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)'],{windowsHide:true,stdio:'ignore'});
    if(check.status===0)return {command,prefix};
  }
  throw Error('Python 3.10 or newer is required (standard library only). Install it on PATH or set ACCLAM_PYTHON to its executable.');
}
function runCheck(script,args=[]){
  const {command,prefix}=findPython();
  const compact=script==='quest.py'&&args[0]==='verify-copy';
  const checked=spawnSync(command,[...prefix,path.join(root,'scripts',script),...args],{cwd:root,stdio:compact?['ignore','pipe','pipe']:'inherit',encoding:'utf8',windowsHide:true,env:{...process.env,PYTHONUTF8:'1'}});
  if(checked.status!==0){
    if(compact)process.stderr.write((checked.stdout||'')+(checked.stderr||''));
    throw Error('Register validation failed. Inspect the output; no feed update was forced.');
  }
  if(compact){
    const result=JSON.parse(checked.stdout);
    console.log(JSON.stringify({mode:result.mode,result:result.result,objectives:result.objectives,
      unavailablePrivateSources:result.unavailablePrivateSources.length,fullEvidenceValidation:result.fullEvidenceValidation}));
  }
}
async function fetchJson(route){
  const response=await fetch(url+route,{signal:AbortSignal.timeout(3000)});
  if(!response.ok)throw Error(`Viewer returned ${response.status}; validate/rebuild before retrying.`);
  return response.json();
}
async function main(){
  if(process.argv.includes('--close')){
    if(!fs.existsSync(sessionPath)){console.log('No launcher-owned viewer session is recorded.');return;}
    const saved=JSON.parse(fs.readFileSync(sessionPath,'utf8'));
    const info=await fetchJson('/viewer-info');
    if(info.app!=='ACCLAM local viewer'||info.workspaceId!==workspaceId||info.pid!==saved.pid||!saved.instance||info.instance!==saved.instance||saved.port!==port)throw Error('Viewer identity differs; no process was stopped.');
    process.kill(saved.pid);
    fs.unlinkSync(sessionPath);
    console.log('ACCLAM local viewer closed.');return;
  }
  if(process.argv.includes('--update-only')){
    runCheck('checkpoint.py');return; // Always strict; missing private evidence fails.
  }
  if(process.env.ACCLAM_SOURCE_ROOT)runCheck('quest.py',['validate']);
  runCheck('quest.py',['verify-copy']); // Read-only: preserves historical receipts and snapshots.
  let running=false;
  try{
    const feed=await fetchJson('/progress.json');
    if(feed.project?.title!=='ACCLAM · Launch Quest')throw Error('Port is occupied by a different application.');
    const info=await fetchJson('/viewer-info');
    if(info.workspaceId!==workspaceId)throw Error('Port belongs to another Quest copy. Set ACCLAM_QUEST_PORT to a free local port.');
    running=true;
  }catch(error){
    if(!['ECONNREFUSED','UND_ERR_CONNECT_TIMEOUT'].includes(error.cause?.code))throw error;
  }
  if(!running){
    const instance=crypto.randomUUID();
    const out=fs.openSync(path.join(root,'evidence/viewer.log'),'a');
    const err=fs.openSync(path.join(root,'evidence/viewer-error.log'),'a');
    const child=spawn(process.execPath,[path.join(root,'server.mjs')],{cwd:root,detached:true,windowsHide:true,stdio:['ignore',out,err],env:{...process.env,ACCLAM_QUEST_INSTANCE:instance}});
    child.unref();fs.closeSync(out);fs.closeSync(err);
    fs.writeFileSync(sessionPath,JSON.stringify({pid:child.pid,instance,port}));
    for(let attempt=0;attempt<20;attempt++){
      await new Promise(resolve=>setTimeout(resolve,150));
      try{const info=await fetchJson('/viewer-info');if(info.pid===child.pid&&info.instance===instance){running=true;break;}}catch{}
    }
    if(!running)throw Error('Viewer did not become ready. Inspect evidence/viewer-error.log.');
  }
  console.log(`ACCLAM Launch Quest: ${url}`);
  if(!process.argv.includes('--no-browser')){
    const command=process.platform==='win32'?'rundll32.exe':process.platform==='darwin'?'open':'xdg-open';
    const args=process.platform==='win32'?['url.dll,FileProtocolHandler',url]:[url];
    const browser=spawn(command,args,{detached:true,stdio:'ignore',windowsHide:true});
    browser.on('error',()=>console.error(`Open ${url} in your browser.`));browser.unref();
  }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
