"""Validate/build, then retain a content-addressed historical save point."""
from quest import QUEST, REGISTER, read, write, digest, build
import json

result=build()
revision=result['revision']
folder=QUEST/'checkpoints'/revision[:16]
folder.mkdir(parents=True,exist_ok=True)
for name,source in [('PROJECT_REGISTER.json',REGISTER),('progress.json',QUEST/'dist/progress.json')]:
    target=folder/name
    if target.exists() and target.read_bytes()!=source.read_bytes():
        raise SystemExit('Checkpoint content conflict; preserve existing snapshot and investigate.')
    if not target.exists():target.write_bytes(source.read_bytes())
write(folder/'receipt.json',{'meaning':'Historical snapshot only. Current authority is work/launch-quest/PROJECT_REGISTER.json.',
    'asOf':read(REGISTER)['asOf'],'registerSha256':digest(REGISTER),'projectionRevision':revision})
print(json.dumps(result))
