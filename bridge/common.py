"""Reuse frozen AHIF checker and write new local destinations only."""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ahif_011_checker', ROOT/'docs/ahif/0.1.1/reference/validate_bundle.py')
ahif = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ahif)
C = ahif.canonical
load = ahif.strict_loads
sha = lambda b: hashlib.sha256(b).hexdigest()

def profile(name):
    value=load((ROOT/'profiles'/name/'1.0.0/profile.json').read_bytes())
    directory=ROOT/'profiles'/name/'1.0.0'
    binding={'profile':value,'readme_sha256':sha((directory/'README.md').read_bytes())}
    if (directory/'receipt.schema.json').exists():binding['receipt_schema_sha256']=sha(C(load((directory/'receipt.schema.json').read_bytes())))
    return value, sha(C(binding))

def write_json(path, value):
    Path(path).write_bytes(C(value)+b'\n')

def file_info(path, name=None):
    p=Path(path)
    return {'path':name or p.name,'sha256':sha(p.read_bytes()),'byte_length':p.stat().st_size}

@contextmanager
def new_destination(destination):
    dest=Path(destination).absolute()
    if dest.exists() or dest.is_symlink(): raise ValueError('output_exists')
    if any(p.is_symlink() for p in dest.parents): raise ValueError('output_symlink_ancestry')
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp=Path(tempfile.mkdtemp(prefix='.ahif-stage-',dir=dest.parent))
    try:
        yield tmp
        # Local trusted-files helper; concurrent writers/races are out of scope.
        if dest.exists(): raise ValueError('output_exists')
        tmp.rename(dest)
    finally:
        if tmp.exists(): shutil.rmtree(tmp)

def write_bundle(root, manifest, records, accounts=()):
    manifest=dict(manifest)
    manifest['files']=[]
    for name,role,rows in [('records.jsonl','records',records),('accounts.jsonl','accounts',accounts)]:
        if role=='accounts' and not rows:continue
        data=b''.join(C(r)+b'\n' for r in sorted(rows,key=lambda r:r['observation_id']))
        (root/name).write_bytes(data)
        manifest['files'].append({'path':name,'role':role,'sha256':sha(data),'byte_length':len(data),'row_count':len(rows)})
    manifest['files'].sort(key=lambda f:f['path'])
    manifest['sources']=sorted(manifest['sources'],key=lambda s:s['source_id'])
    manifest['coverage']=sorted(manifest['coverage'],key=C)
    write_json(root/'manifest.json',manifest)
    return ahif.validate_bundle(root,require_canonical=True)

def read_bundle(root):
    root=Path(root)
    check=ahif.validate_bundle(root)
    manifest=load((root/'manifest.json').read_bytes())
    rows={'records':[],'accounts':[]}
    for f in manifest['files']:
        if f['role'] in rows:
            rows[f['role']].extend(load(line) for line in (root/f['path']).read_bytes().split(b'\n') if line)
    return manifest, rows['records'], rows['accounts'], check
