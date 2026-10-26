// Local attachments are never serialized into the register, URLs, or responses.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export class SourceError extends Error {
  constructor(message,status=500){super(message);this.status=status;}
}
export function canonicalRelative(value){
  if(typeof value!=='string'||!value||value.includes('\\')||value.includes('\0')||path.posix.isAbsolute(value)||path.win32.isAbsolute(value)||/^[A-Za-z]:/.test(value)||value.split('/').some(part=>!part||part==='.'||part==='..'))throw new SourceError('Source path must stay inside the allowed root',404);
  return value;
}
export function resolveInside(base,relative){
  canonicalRelative(relative);
  const root=fs.realpathSync(base),target=path.resolve(root,relative);
  const real=fs.realpathSync(target),rel=path.relative(root,real);
  if(rel==='..'||rel.startsWith('..'+path.sep)||path.isAbsolute(rel))throw new SourceError('Source symbolic link leaves the allowed root',403);
  if(!fs.statSync(real).isFile())throw new SourceError('Source is not a file',404);
  return real;
}
export function createSourceResolver(workspace,externalRoot=process.env.ACCLAM_SOURCE_ROOT){
  const manifestPath=path.join(workspace,'work/launch-quest/EXTERNAL_SOURCES.json');
  const pinned=new Map(),hashes=new Map();
  if(fs.existsSync(manifestPath)){
    const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8').replace(/^\uFEFF/,''));
    if(manifest.schemaVersion!==1||!Array.isArray(manifest.files))throw new SourceError('Invalid external source manifest');
    for(const item of manifest.files){
      canonicalRelative(item.path);
      if(pinned.has(item.path)||!/^[0-9a-f]{64}$/.test(item.sha256)||item.reason!=='private_client_source')throw new SourceError('Invalid external source manifest entry');
      pinned.set(item.path,item.sha256);
    }
  }
  function resolve(relative){
    canonicalRelative(relative);
    let file;
    try{file=resolveInside(workspace,relative);}catch(error){
      if(error instanceof SourceError)throw error;
      if(error.code!=='ENOENT'&&error.code!=='ENOTDIR')throw error;
      if(!pinned.has(relative))throw new SourceError('Linked repository file is unavailable. Check the repository copy.',500);
      if(!externalRoot)throw new SourceError('Private client source omitted from this repository. Attach the original Website folder locally with ACCLAM_SOURCE_ROOT to open this evidence. The preserved task status does not re-verify unavailable evidence.',424);
      try{file=resolveInside(externalRoot,relative);}catch(attachmentError){
        if(attachmentError instanceof SourceError)throw attachmentError;
        if(attachmentError.code!=='ENOENT'&&attachmentError.code!=='ENOTDIR')throw attachmentError;
        throw new SourceError('The attached ACCLAM_SOURCE_ROOT does not contain this allowlisted private dependency.',424);
      }
    }
    if(pinned.has(relative)){
      const stat=fs.statSync(file),key=JSON.stringify([file,stat.size,stat.mtimeMs,stat.ctimeMs]);
      let actual=hashes.get(key);
      if(!actual){actual=crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');hashes.set(key,actual);}
      if(actual!==pinned.get(relative))throw new SourceError('Private source hash differs from the preserved evidence pin. Restore the original source before using this link.',409);
    }
    return file;
  }
  return {resolve};
}
