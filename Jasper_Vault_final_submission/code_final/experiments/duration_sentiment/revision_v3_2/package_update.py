#!/usr/bin/env python3
"""Create a self-contained update containing only jay/ paths, suitable for a branch commit."""
import argparse,hashlib,json,zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
DEPENDENCIES=[
    'jay/README.md','jay/pp_pricing.py','jay/revision_v2/pricing.py',
    'jay/revision_v3/pricing.py','jay/revision_v3/news.py','jay/revision_v3/collect_news.py',
    'jay/revision_v3_1/pricing.py','jay/revision_v3_1/social.py','jay/revision_v3_1/collect_social.py',
    'jay/revision_v3_1/data/news_expanded_2026.jsonl','jay/revision_v3_1/data/btc_social_snapshots.csv',
]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    files={REPO/x for x in DEPENDENCIES}
    files.update(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'runtime' not in p.parts and p.name!='package_manifest.json')
    entries=[{'path':p.relative_to(REPO).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(files)]
    assert all(r['path'].startswith('jay/') for r in entries)
    assert len(entries)+1<=100,'Use split uploads or Git CLI if adding more files'
    assert max(r['bytes'] for r in entries)<25*1024**2,'An extracted file exceeds browser upload size'
    manifest={'release':'V3.2 combined framework','file_count_including_manifest':len(entries)+1,'max_file_bytes':max(r['bytes'] for r in entries),'paths_relative_to':'repository root','files':entries}
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for r in entries:z.write(REPO/r['path'],r['path'])
        z.writestr('jay/revision_v3_2/package_manifest.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print(json.dumps({'zip':str(target.resolve()),'bytes':target.stat().st_size,'files':len(entries)+1,'max_file_bytes':manifest['max_file_bytes'],'sha256':digest(target)},indent=2))

if __name__=='__main__':main()
