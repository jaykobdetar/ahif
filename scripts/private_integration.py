#!/usr/bin/env python3
"""Bounded one-export integration; exact paths/maps/reports stay in a private output.

Run using the existing analyzer's offline_exec.py and environment. Never executes
an old converter or changes a historical input. No live collection or pilot.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge.common import C, ahif, file_info, load, read_bundle, sha, write_json
from bridge.projection import engine, selection_for
from bridge.reddit import read_members

def digest_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(65536):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','prior-input','prior-manifest','prior-conversion','prior-converter','engine-root','out']:
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':raise ValueError('run_under_frozen_offline_exec')
    out=a.out.absolute()
    if out.exists() or out.is_relative_to(ROOT) or any(p.is_symlink() for p in [out,*out.parents]):raise ValueError('output_must_be_new_private_directory_outside_repo')
    out.mkdir(mode=0o700,parents=True);(out/'logs').mkdir(mode=0o700)
    receipt={'version':'1.0.0','status':'started','private_do_not_publish':True,'commands':[],
        'network_isolation':os.environ['AHAS_NETWORK_ISOLATION'],'started_utc':datetime.now(timezone.utc).isoformat()}
    # Hashes bind only relevant historical files, no unrelated account corpus read.
    inputs=[a.source,a.prior_input,a.prior_manifest,a.prior_conversion,a.prior_converter]
    before={str(f):digest_file(f) for f in inputs}
    receipt['original_file_hashes']=before
    freeze={str(f.relative_to(a.engine_root)):digest_file(f) for folder in ['src','schemas','config','resources']
        for f in (a.engine_root/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    receipt['engine_boundary_before']=freeze
    def command(name,argv,allowed=(0,)):
        started=time.monotonic()
        result=subprocess.run([str(x) for x in argv],cwd=ROOT,capture_output=True)
        for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]:
            (out/'logs'/f'{name}.{stream}.log').write_bytes(data)
        receipt['commands'].append({'name':name,'argv':[str(x) for x in argv],'cwd':str(ROOT),'exit_code':result.returncode,
            'elapsed_seconds':format(time.monotonic()-started,'.6f'),'stdout_sha256':sha(result.stdout),'stderr_sha256':sha(result.stderr)})
        write_json(out/'execution-receipt.json',receipt)
        if result.returncode not in allowed:raise ValueError('command_failed:'+name)
        return result
    try:
        prior_report=json.loads(a.prior_conversion.read_bytes())
        members=read_members(a.source)
        if not all(sha(raw)==prior_report['source']['members'][name]['sha256'] for name,raw in members.items()):raise ValueError('prior_source_hash_mismatch')
        receipt['matching_source_members']=list(members)
        for label in ['bundle-a','bundle-b']:
            command('normalize-'+label,[sys.executable,'-m','bridge.cli','normalize','--source',a.source,'--out',out/label,
                '--subject','export_subject','--fidelity-out',out/(label+'-fidelity.json')])
        manifest,records,_,_=read_bundle(out/'bundle-a');selection=selection_for(manifest['sources'][0]['source_id'])
        write_json(out/'selection.json',selection)
        for name in ['manifest.json','records.jsonl']:
            if (out/'bundle-a'/name).read_bytes()!=(out/'bundle-b'/name).read_bytes():raise ValueError('normalized_replay_mismatch')
        # Relocation and object-key order check on the selection input.
        (out/'bundle-b').rename(out/'relocated-bundle')
        (out/'selection-reordered.json').write_text(json.dumps(dict(reversed(list(selection.items()))),indent=3)+'\n')
        for label,bundle,selected in [('projection-a','bundle-a','selection.json'),('projection-b','relocated-bundle','selection-reordered.json')]:
            command(label,[sys.executable,'-m','bridge.cli','project','--bundle',out/bundle,'--out',out/label,'--selection',out/selected])
            command('verify-'+label,[sys.executable,'-m','bridge.cli','verify','--bundle',out/bundle,'--output',out/label])
        ra=load((out/'projection-a/projection-receipt.json').read_bytes());rb=load((out/'projection-b/projection-receipt.json').read_bytes())
        if ra['payload']!=rb['payload']:raise ValueError('projection_replay_mismatch')
        receipt['reproducibility']={'canonical_bundle_bytes_equal':True,'projection_payload_equal':True,
            'projection_payload_sha256':ra['payload_sha256'],'paths_and_runtime_timestamps_excluded':True}
        payload=ra['payload'];receipt['counts']=payload['counts'];receipt['decision_reasons']=dict(Counter(d['reason'] for d in payload['decisions']))
        # Independently read actual historical AHAS files through the frozen loader.
        config,loader,thaw,ident=engine()
        old=loader(a.prior_input,a.prior_manifest,config)
        new=loader(out/'projection-a/records.jsonl',out/'projection-a/snapshot.json',config)
        old_by_id={r['id']:thaw(r) for r in old.records}
        native_to_alias={}
        for mapping in payload['aliases']:
            if mapping['type']!='record':continue
            native=mapping['key']['id']
            if native in native_to_alias and native_to_alias[native]!=mapping['alias']:raise ValueError('prior_bare_id_ambiguous')
            native_to_alias[native]=mapping['alias']
        selected=[d for d in payload['decisions'] if d['decision']=='selected']
        expected={r['id']:thaw(r) for r in new.records};prior_remapped=[];comparison=[]
        for decision in selected:
            native=decision['key']['id'];original=old_by_id[native];r=dict(original)
            changes=[]
            for f in ['id','parent_id','thread_id']:
                if r[f] is not None:
                    mapped=native_to_alias[r[f]];changes.append({'field':f,'before':r[f],'after':mapped});r[f]=mapped
            changes.append({'field':'account_id','before':r['account_id'],'after':new.manifest['account_id']});r['account_id']=new.manifest['account_id']
            if r['language'] is None:
                if old.manifest['default_language']!='und':raise ValueError('prior_language_not_unknown')
                changes.append({'field':'language','before':None,'after':'und','reason':'explicit_same_effective_unknown_language'});r['language']='und'
            target=expected[decision['output_id']]
            differences=[k for k in set(r)|set(target) if r.get(k)!=target.get(k)]
            comparison.append({'record_key':decision['key'],'observation_id':decision['observation_id'],'prior_id':native,
                'projection_id':decision['output_id'],'substitutions':changes,'different_fields_after_substitution':differences})
            if differences:raise ValueError('prior_semantic_fields_differ')
            prior_remapped.append(r)
        if not selected:raise ValueError('no_mutually_representable_subset')
        prior_remapped.sort(key=lambda r:(r['created_utc'] or '',r['id']))
        matched=out/'prior-matched-scope';matched.mkdir(mode=0o700)
        (matched/'records.jsonl').write_bytes(b''.join(C(r)+b'\n' for r in prior_remapped))
        # The comparison is deliberately the SAME narrowed scope and metadata,
        # not a replay claim about the full historical report or old coverage.
        (matched/'snapshot.json').write_bytes((out/'projection-a/snapshot.json').read_bytes())
        write_json(out/'prior-comparison.json',{'status':'passed','prior_inputs':{str(f):before[str(f)] for f in inputs[1:]},
            'scope':'Selected metadata-only subset; source/account IDs and effective und explicitly substituted. Snapshot metadata fixed to same projection scope.',
            'full_historical_report_byte_identity_claimed':False,'field_comparisons':comparison,
            'snapshot_fields_set_for_matched_scope':list(new.manifest),'unselected_prior_records':len(old.records)-len(selected)})
        receipt['prior_comparison']={'status':'passed','records':len(selected),'all_record_fields_equal_after_declared_substitutions':True,
            'full_prior_history_or_reports_compared':False}
        ahas=a.engine_root/'.venv/bin/ahas'
        for name,inp in [('projected','projection-a'),('prior-matched','prior-matched-scope')]:
            command('ahas-validate-'+name,[ahas,'validate','--input',out/inp/'records.jsonl','--manifest',out/inp/'snapshot.json'])
            command('ahas-analyze-'+name,[ahas,'analyze','--input',out/inp/'records.jsonl','--manifest',out/inp/'snapshot.json','--out',out/('analysis-'+name)])
        command('ahas-verify-recompute',[ahas,'verify','--input',out/'projection-a/records.jsonl','--manifest',out/'projection-a/snapshot.json',
            '--analysis-dir',out/'analysis-projected','--recompute'])
        # Standard JSON handles AHAS numerical floats; AHIF restricted JSON does not.
        left=json.loads((out/'analysis-projected/results.json').read_bytes());right=json.loads((out/'analysis-prior-matched/results.json').read_bytes())
        if left!=right:raise ValueError('same_scope_numerical_results_differ')
        receipt['numerical_comparison']={'status':'passed','scope':'Entire results.json on matched subset after documented input substitutions',
            'projection_results_sha256':digest_file(out/'analysis-projected/results.json'),
            'prior_matched_results_sha256':digest_file(out/'analysis-prior-matched/results.json'),
            'historical_full_reports_byte_identical':False}
        receipt['engine']=ident
        receipt['source_attribution_is_not_scientific_authorship_validation']=True
        receipt['status']='passed'
    except Exception as e:
        receipt['status']='failed';receipt['error_type']=type(e).__name__
        # Only stable local diagnostic codes; never library exceptions with prose.
        if type(e) is ValueError and str(e).replace(':','').replace('_','').replace('-','').isalnum():receipt['error_code']=str(e)
        raise
    finally:
        receipt['original_files_unchanged']=before=={str(f):digest_file(f) for f in inputs}
        after={str(f.relative_to(a.engine_root)):digest_file(f) for folder in ['src','schemas','config','resources']
            for f in (a.engine_root/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
        receipt['engine_boundary_unchanged']=freeze==after
        if not receipt['original_files_unchanged'] or not receipt['engine_boundary_unchanged']:receipt['status']='failed'
        receipt['finished_utc']=datetime.now(timezone.utc).isoformat();write_json(out/'execution-receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'counts':receipt['counts'],'reasons':receipt['decision_reasons'],
        'prior_comparison':receipt['prior_comparison'],'original_files_unchanged':receipt['original_files_unchanged'],
        'engine_boundary_unchanged':receipt['engine_boundary_unchanged']}))
    return 0 if receipt['status']=='passed' else 2

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,'details':'See private execution receipt.'}))
        raise SystemExit(2)
