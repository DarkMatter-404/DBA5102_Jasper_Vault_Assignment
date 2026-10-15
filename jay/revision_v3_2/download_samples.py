#!/usr/bin/env python3
"""Optionally redownload the pinned public samples; bundled copies work offline."""
import base64, hashlib, json, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'data/instrumetriq'

def verify(data,record):
    sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if len(data)!=record['size'] or sha!=record['sha']:raise ValueError('Source size/Git hash mismatch: '+record['path'])

def main():
    manifest=json.loads((ROOT/'source_manifest.json').read_text());(ROOT/'raw').mkdir(exist_ok=True)
    for r in manifest['files']:
        p=ROOT/'raw'/Path(r['path']).name
        if p.exists():verify(p.read_bytes(),r);print('verified',p.name);continue
        # Address immutable blobs directly; the manifest ref may be a Git tree.
        url=r['url']
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Jasper-PP-assignment-research/3.1','Accept':'application/vnd.github+json'}),timeout=60) as response:payload=json.load(response)
        if payload.get('encoding')!='base64':raise ValueError('Unexpected GitHub blob encoding')
        data=base64.b64decode(payload['content'])
        verify(data,r);tmp=p.with_suffix('.download');tmp.write_bytes(data);tmp.replace(p);print('downloaded',p.name)

if __name__=='__main__':main()
