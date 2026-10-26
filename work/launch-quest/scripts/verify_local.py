"""Read-only automated QA on an isolated local port.

Default: strict original-evidence validation (attach ACCLAM_SOURCE_ROOT).
--copy: preserved snapshot and available evidence only, with explicit 424 links.
Historical receipts, screenshots, source maps and task history are never rewritten.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from quest import QUEST, REGISTER, read, digest, validate, verify_copy
from test_quest import node_runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copy',action='store_true',help='Bounded repository snapshot verification; does not claim full private evidence validation')
    args=parser.parse_args()
    register_result=verify_copy() if args.copy else validate(read(REGISTER))
    tests=subprocess.run([sys.executable,str(QUEST/'scripts/test_quest.py')],capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
    if tests.returncode:raise ValueError(tests.stdout+tests.stderr)
    node=node_runtime()
    syntax=['server.mjs','source-resolver.mjs','launch.mjs','dist/app.js']
    for file in syntax:
        checked=subprocess.run([node,'--check',str(QUEST/file)],capture_output=True,text=True)
        if checked.returncode:raise ValueError(checked.stderr)
    projection=read(QUEST/'dist/progress.json')
    links={s['url'].split('#')[0] for m in projection['milestones'] for t in m['objectives'] for s in t['sources']+t['evidence']}
    links.add(projection['project']['continuityUrl'])
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    process=subprocess.Popen([node,str(QUEST/'server.mjs')],env={**os.environ,'ACCLAM_QUEST_PORT':str(port)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    base=f'http://127.0.0.1:{port}'
    try:
        for _ in range(50):
            if process.poll() is not None:raise ValueError('Isolated viewer stopped before becoming ready')
            try:
                with urlopen(base+'/progress.json',timeout=1) as response:
                    if response.status==200:break
            except OSError:time.sleep(.1)
        else:raise ValueError('Isolated viewer did not start')
        def inspect(url):
            try:
                with urlopen(Request(base+url,method='HEAD'),timeout=20) as response:return {'url':url,'status':response.status}
            except HTTPError as error:
                status=error.code;error.close();return {'url':url,'status':status}
        with ThreadPoolExecutor(max_workers=4) as pool:link_results=list(pool.map(inspect,sorted(links)))
        allowed={200,424} if args.copy else {200}
        bad=[item for item in link_results if item['status'] not in allowed]
        if bad:raise ValueError('Evidence link check failed: '+json.dumps(bad,ensure_ascii=True))
    finally:
        process.terminate();process.wait(timeout=5)
    return {'schemaVersion':1,'reviewedAtUtc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'mode':'repository_copy' if args.copy else 'strict_attached_sources',
            'result':'passed','fullEvidenceValidation':not args.copy,
            'registerSha256':digest(REGISTER),'projectionRevision':projection['revision'],
            'register':register_result,'automatedTests':{'result':'passed','summary':tests.stderr.strip()},
            'syntaxChecks':syntax,'sourceLinks':link_results,'writesPerformed':False,
            'limits':'Automated checks only; retained historical browser screenshots are not a new browser or Wix inspection.'}


if __name__=='__main__':
    try:print(json.dumps(main(),ensure_ascii=True))
    except Exception as error:print(str(error));raise SystemExit(1)
