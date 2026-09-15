#!/usr/bin/env python3
"""New execution receipts; historical AHIF/standalone receipts remain untouched."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge.common import C, profile, sha
from bridge.projection import engine

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine-root',type=Path,required=True);a=p.parse_args()
    qa=ROOT/'qa/bridge';qa.mkdir(exist_ok=True)
    result={'started_at':datetime.now(timezone.utc).isoformat(),'status':'failed','python':sys.version,'commands':[]}
    def run(argv,directory,log):
        r=subprocess.run([str(x) for x in argv],cwd=directory,capture_output=True)
        (qa/log).write_bytes((r.stdout+r.stderr).replace(str(ROOT).encode(),b'<repository>').replace(str(a.engine_root).encode(),b'<engine>'))
        result['commands'].append({'argv':[str(x).replace(str(ROOT),'<repository>').replace(str(a.engine_root),'<engine>') for x in argv],
            'exit_code':r.returncode,'log':log})
        if r.returncode:raise ValueError('check_failed:'+log)
    try:
        run([sys.executable,'-m','pytest','tests/bridge','-q','--tb=short'],ROOT,'tests.log')
        # Historical check script writes results; run a copy so original receipts stay frozen.
        with tempfile.TemporaryDirectory() as td:
            copy=Path(td)/'ahif';(copy/'scripts').mkdir(parents=True);(copy/'qa').mkdir()
            shutil.copytree(ROOT/'docs/ahif',copy/'docs/ahif',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy2(ROOT/'scripts/check_contract.py',copy/'scripts/check_contract.py')
            shutil.copy2(ROOT/'qa/source-inventory.json',copy/'qa/source-inventory.json')
            run([sys.executable,copy/'scripts/check_contract.py'],copy,'format-check.log')
            result['format_check']=json.loads((copy/'qa/standalone-verification.json').read_bytes())
            (qa/'format-tests.log').write_bytes((copy/'qa/standalone-tests.log').read_bytes())
        baseline=json.loads((qa/'engine-baseline.json').read_bytes());different=[]
        for f in baseline['files']:
            data=(a.engine_root/f['path']).read_bytes()
            blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if blob!=f['git_blob_sha']:different.append(f['path'])
        if different:raise ValueError('frozen_engine_differs')
        result['engine_baseline']={'repository':'https://github.com/jaykobdetar/account-history-analyzer',
            'commit':baseline['commit'],'files_checked':len(baseline['files']),'all_match':True}
        _,_,_,ident=engine();result['engine']={k:v for k,v in ident.items() if k!='config_json'}
        expected=json.loads((ROOT/'qa/source-inventory.json').read_bytes())['files']
        actual={str(f.relative_to(ROOT/'docs/ahif')):sha(f.read_bytes()) for f in (ROOT/'docs/ahif').rglob('*') if f.is_file() and '__pycache__' not in f.parts}
        if expected!=actual:raise ValueError('historical_contract_changed')
        result['preserved_contract_files']=len(expected)
        result['profile_bindings']={name:profile(name)[1] for name in ['reddit-export-csv','ahas-conservative']}
        result['implementation_files']={str(f.relative_to(ROOT)):sha(f.read_bytes()) for folder in ['bridge','profiles','tests/bridge']
            for f in sorted((ROOT/folder).rglob('*')) if f.is_file() and '__pycache__' not in f.parts}
        for f in ['scripts/private_integration.py','scripts/check_bridge.py','requirements-bridge-test.txt']:
            result['implementation_files'][f]=sha((ROOT/f).read_bytes())
        result['limitations']=['Fictional tests plus one separately documented private metadata-only integration.',
            'No retained-prose projection or scientific authorship accuracy validation.',
            'Original format-only test skips its parent-dependent integration test; new bridge tests use actual AHAS.',
            'Bounded trusted-file helper, not a production hostile-ingestion audit.']
        result['status']='passed'
    except Exception as exc:result['error']=str(exc)
    result['finished_at']=datetime.now(timezone.utc).isoformat()
    (qa/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','preserved_contract_files','engine_baseline','profile_bindings','error'] if k in result},indent=2))
    return 0 if result['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
