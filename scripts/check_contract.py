#!/usr/bin/env python3
"""Standalone packaging checks; preserve all versioned contract files and receipts."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'docs/ahif/0.1.1'
REFERENCE=CONTRACT/'reference'
sys.path.insert(0,str(REFERENCE))
import validate_bundle as v
import test_review

SKIP_REASON='Requires the original AHAS workspace and installation; not part of standalone format validation.'

def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}

def main():
    qa=ROOT/'qa';qa.mkdir(exist_ok=True)
    result={'started_at':datetime.now(timezone.utc).isoformat(),'status':'failed',
            'python':sys.version,'dependencies':{p:version(p) for p in ('jsonschema','referencing')},
            'analysis_performed':False,'ahif_version':'0.1.1'}
    try:
        # Decorate only the in-memory test. Preserved versioned bytes stay intact.
        method=test_review.ReviewTests.test_actual_ahas_schema_rejects_direct_ahif
        test_review.ReviewTests.test_actual_ahas_schema_rejects_direct_ahif=unittest.skip(SKIP_REASON)(method)
        stream=io.StringIO()
        suite=unittest.defaultTestLoader.discover(str(REFERENCE))
        run=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        (qa/'standalone-tests.log').write_text(stream.getvalue().replace(str(ROOT),'<repository>'))
        result['tests']={'run':run.testsRun,'passed':run.testsRun-len(run.failures)-len(run.errors)-len(run.skipped),
                         'failures':len(run.failures),'errors':len(run.errors),
                         'skipped':[{'test':test.id(),'reason':reason} for test,reason in run.skipped]}
        expected=json.loads((qa/'source-inventory.json').read_text())['files']
        actual=hashes(ROOT/'docs/ahif')
        result['source_preservation']={'files':len(expected),'byte_identical':actual==expected}
        checksums={}
        for name,base in [('0.1.1',CONTRACT),('0.1.0',ROOT/'docs/ahif/history/0.1.0')]:
            count=0
            for line in (base/'SHA256SUMS.txt').read_text().splitlines():
                digest,path=line.split('  ',1)
                assert hashlib.sha256((base/path).read_bytes()).hexdigest()==digest,path
                count+=1
            checksums[name]=count
        result['verified_checksum_entries']=checksums
        result['bundles']={p.name:v.validate_bundle(p,require_canonical=True) for p in sorted((CONTRACT/'examples').iterdir()) if p.is_dir()}
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'contract';shutil.copytree(REFERENCE,target/'reference');(target/'schemas').mkdir()
            for name in ('build_schemas.py','build_examples.py'):
                completed=subprocess.run([sys.executable,str(target/'reference'/name)],capture_output=True,text=True,
                                         env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=60)
                if completed.returncode: raise RuntimeError(completed.stderr)
            compared=0
            for folder in ('schemas','examples'):
                before=hashes(CONTRACT/folder);after=hashes(target/folder)
                assert before==after,folder+' differs after regeneration'
                compared+=len(before)
        result['regeneration']={'files_compared':compared,'byte_identical':True}
        result['limitations']=['Original AHAS integration test explicitly skipped; engine not included.',
                              'No source collection, projection, scientific analysis or production ingestion audit.',
                              'Historical adoption receipts are preserved, not regenerated.']
        if run.wasSuccessful() and len(run.skipped)==1 and actual==expected:
            result['status']='passed_for_standalone_checks'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc).replace(str(ROOT),'<repository>')
    result['finished_at']=datetime.now(timezone.utc).isoformat()
    (qa/'standalone-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','tests','source_preservation','regeneration','error') if k in result},indent=2))
    return 0 if result['status']=='passed_for_standalone_checks' else 1

if __name__=='__main__': raise SystemExit(main())
