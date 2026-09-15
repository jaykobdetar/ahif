#!/usr/bin/env python3
"""Offline one-export engineering regression; all evidence stays outside repos.

Run under the frozen AHAS scripts/offline_exec.py. Original bundles, receipts,
source files and engine files are read-only inputs. Failures retain new receipts.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.common import C, file_info, load, read_bundle, sha, write_json
from bridge.reddit import normalize
from bridge.projection import engine, verify_projection as verify_conservative
from bridge.observation_presentation import present, COUNT_LABELS
from direct_observation_baseline import build as baseline


def inventory(root):
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(Path(root).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def source_inventory(source):
    # Bind only selected members for directory inputs, the original archive for ZIP.
    if source.is_dir():
        return {name: sha((source / name).read_bytes()) for name in ('comments.csv', 'posts.csv')}
    return sha(source.read_bytes())


def reordered(value):
    if isinstance(value, dict):
        return {k: reordered(v) for k, v in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reordered(v) for v in value]
    return value


def main():
    from bridge.export_observation import project, selection_for, verify_projection
    from verify_observation_fidelity import verify as fidelity
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'existing-bundle', 'existing-conservative', 'engine-root', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise ValueError('run_under_frozen_offline_exec')
    out = args.out.absolute()
    if out.exists() or any(out.is_relative_to(p.resolve()) for p in (ROOT, args.engine_root)) or any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError('new_private_output_outside_repositories_required')
    out.mkdir(mode=0o700, parents=True)
    (out / 'logs').mkdir(mode=0o700)
    receipt = {'version': '1.0.0', 'status': 'started', 'private_do_not_publish': True,
               'started_utc': datetime.now(timezone.utc).isoformat(), 'commands': [], 'checks': {},
               'network_isolation': os.environ['AHAS_NETWORK_ISOLATION'],
               'rerun_argv': [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
               'validation_scripts': {p.name: sha(p.read_bytes()) for p in (Path(__file__), Path(__file__).with_name('direct_observation_baseline.py'), Path(__file__).with_name('verify_observation_fidelity.py'))}}
    originals = {str(args.source): source_inventory(args.source),
                 str(args.existing_bundle): inventory(args.existing_bundle),
                 str(args.existing_conservative): inventory(args.existing_conservative)}
    frozen = {folder: inventory(args.engine_root / folder) for folder in ('src', 'schemas', 'config', 'resources')}
    frozen_contract = {folder: inventory(ROOT / folder) for folder in ('docs/ahif', 'profiles/ahas-conservative', 'profiles/reddit-export-csv')}
    implementation = {folder: inventory(ROOT / folder) for folder in ('bridge', 'profiles/reddit-export-observation')}
    receipt['original_inventory'] = originals
    receipt['engine_inventory'] = frozen
    receipt['frozen_contract_inventory'] = frozen_contract
    receipt['projection_implementation_inventory'] = implementation

    def command(name, argv):
        start = time.monotonic()
        run = subprocess.run([str(x) for x in argv], cwd=ROOT, capture_output=True)
        for stream, data in (('stdout', run.stdout), ('stderr', run.stderr)):
            (out / 'logs' / (name + '.' + stream + '.log')).write_bytes(data)
        receipt['commands'].append({'name': name, 'argv': [str(x) for x in argv], 'exit_code': run.returncode,
                                    'elapsed_seconds': format(time.monotonic() - start, '.6f'),
                                    'stdout_sha256': sha(run.stdout), 'stderr_sha256': sha(run.stderr)})
        write_json(out / 'execution-receipt.json', receipt)
        if run.returncode:
            raise ValueError('command_failed_' + name)

    try:
        receipt['checks']['historical_conservative_replay'] = verify_conservative(args.existing_bundle, args.existing_conservative)
        first = normalize(args.source, out / 'bundle-a', subject='export_subject')
        normalize(args.source, out / 'relocated-bundle', subject='export_subject')
        if inventory(out / 'bundle-a') != inventory(out / 'relocated-bundle') or inventory(out / 'bundle-a') != inventory(args.existing_bundle):
            raise ValueError('unchanged_normalized_observation_replay_failed')
        receipt['checks']['normalized_bytes_equal_to_historical_and_relocated'] = True
        selection = selection_for(first['source_id'])
        write_json(out / 'selection.json', selection)
        a = project(out / 'bundle-a', out / 'projection-a', selection, executed_at='2026-01-01T00:00:00Z')
        b = project(out / 'relocated-bundle', out / 'projection-relocated', reordered(selection), executed_at='2036-01-01T00:00:00Z')
        if a['payload'] != b['payload'] or a['operational'] == b['operational']:
            raise ValueError('relocation_or_operational_clock_mismatch')
        for label, bundle in (('projection-a', 'bundle-a'), ('projection-relocated', 'relocated-bundle')):
            receipt['checks']['verify_' + label] = verify_projection(out / bundle, out / label)
        # Rewrite transport property order while keeping observation IDs fixed.
        transport = out / 'reordered-transport'
        shutil.copytree(out / 'bundle-a', transport)
        manifest = load((transport / 'manifest.json').read_bytes())
        for entry in manifest['files']:
            if entry['role'] not in {'records', 'accounts'}:
                continue
            path = transport / entry['path']
            rows = [load(line) for line in path.read_bytes().splitlines()]
            path.write_text(''.join(json.dumps(reordered(r), ensure_ascii=False, separators=(', ', ': ')) + '\n' for r in rows))
            entry.update(sha256=sha(path.read_bytes()), byte_length=path.stat().st_size)
        (transport / 'manifest.json').write_text(json.dumps(reordered(manifest), ensure_ascii=False, indent=2) + '\n')
        c = project(transport, out / 'projection-reordered', reordered(selection), executed_at='2046-01-01T00:00:00Z')
        for name in ('records.jsonl', 'snapshot.json'):
            if (out / 'projection-a' / name).read_bytes() != (out / 'projection-reordered' / name).read_bytes():
                raise ValueError('json_property_order_changed_analysis')
        if a['payload_sha256'] == c['payload_sha256']:
            raise ValueError('raw_transport_not_bound_in_receipt')
        receipt['checks']['verify_reordered'] = verify_projection(transport, out / 'projection-reordered')
        receipt['checks']['identity_contract'] = {'relocation_and_clock_payload_equal': True,
            'property_order_analytical_bytes_equal': True, 'property_order_raw_receipt_changes': True,
            'operational_clock_values_are_test_inputs_not_capture_times': True}
        fidelity_receipt = fidelity(args.source, out / 'bundle-a', out / 'projection-a')
        write_json(out / 'private-field-fidelity.json', fidelity_receipt)
        snapshot = load((out / 'projection-a/snapshot.json').read_bytes())
        independent = baseline(args.source, selection, snapshot, out / 'direct-baseline')
        config, loader, thaw, engine_info = engine()
        candidate = loader(out / 'projection-a/records.jsonl', out / 'projection-a/snapshot.json', config)
        direct = loader(out / 'direct-baseline/records.jsonl', out / 'direct-baseline/snapshot.json', config)
        left = {r['id']: thaw(r) for r in candidate.records}
        right = {r['id']: thaw(r) for r in direct.records}
        mismatches = {identifier: sorted(k for k in set(left.get(identifier, {})) | set(right.get(identifier, {}))
                                       if left.get(identifier, {}).get(k) != right.get(identifier, {}).get(k))
                      for identifier in set(left) | set(right) if left.get(identifier) != right.get(identifier)}
        independent.update(status='passed' if not mismatches else 'failed', field_mismatches=mismatches,
                           all_analytical_record_fields_compared=True,
                           compared_candidate_records=len(left), compared_baseline_records=len(right))
        write_json(out / 'private-direct-baseline-comparison.json', independent)
        if mismatches:
            raise ValueError('independent_direct_input_fields_differ')
        ahas = args.engine_root / '.venv/bin/ahas'
        for label, inp in (('projected', 'projection-a'), ('direct', 'direct-baseline')):
            command('validate-' + label, [ahas, 'validate', '--input', out / inp / 'records.jsonl', '--manifest', out / inp / 'snapshot.json'])
            command('analyze-' + label, [ahas, 'analyze', '--input', out / inp / 'records.jsonl', '--manifest', out / inp / 'snapshot.json', '--out', out / ('analysis-' + label)])
            command('verify-' + label, [ahas, 'verify', '--input', out / inp / 'records.jsonl', '--manifest', out / inp / 'snapshot.json', '--analysis-dir', out / ('analysis-' + label), '--recompute'])
        results = json.loads((out / 'analysis-projected/results.json').read_bytes())
        if results != json.loads((out / 'analysis-direct/results.json').read_bytes()):
            raise ValueError('same_scope_numerical_results_differ')
        checksums = json.loads((out / 'analysis-projected/checksums.json').read_bytes())
        if checksums != json.loads((out / 'analysis-direct/checksums.json').read_bytes()):
            raise ValueError('same_scope_canonical_artifacts_differ')
        receipt['checks']['independent_baseline'] = {'all_record_fields_equal': True, 'entire_results_equal': True,
            'all_canonical_artifacts_equal': True, 'canonical_artifact_count': len(checksums),
            'snapshot_metadata_deliberately_shared': True, 'historical_full_analysis_equality_claimed': False}
        modules = results['modules']
        words = modules['text']['payload']['body']['counts']['retained_words']
        if words <= 0 or modules['coverage']['payload']['usable_body_records'] <= 0:
            raise ValueError('no_usable_prose')
        counts = a['payload']['counts']
        context = {'profile_id': 'reddit-export-observation', 'profile_version': '1.0.0',
                   'projection_payload_sha256': a['payload_sha256'], 'counts': {k: counts[k] for k in COUNT_LABELS},
                   'language_policy': 'und; no language declaration supplied. Generic measurements run; English-specific style abstains.',
                   'chronology_policy': 'One source-field extraction regime, ordered by supplied creation dates; observation time and edit state remain unknown.',
                   'limitations': [
                       'Present means supplied body availability; AHIF lifecycle and visibility remain unchanged and may be unknown.',
                       'Unknown completeness allows source-field counts, not verified complete contribution lengths. Fidelity verifies copying, not platform export completeness.',
                       'Export-subject attribution is a supplied account proxy, not proof of personal authorship or source authenticity.',
                       'Literal body and separate title strings receive the explicitly declared frozen CommonMark interpretation; Reddit dialect identity is not claimed.',
                       'Known removed/deleted/restricted writing and recognized unsupported markup are excluded from text measurements; sound metadata events remain in activity.',
                       'Explicit quotes/code are excluded from body measurements; unmarked quotations or copied material cannot all be detected. Link metadata can include excluded spans.',
                       'Source native destination URLs remain in AHIF and are not appended to prose or projected into AHAS link statistics.',
                       'Activity covers projected distinct supplied events, not a verified complete account history. No completeness percentage is inferred.',
                       'Titles are separate measurements; a title-only snapshot can have an insufficient overall body text module.',
                       'Known source restrictions and retention obligations are independent of technical representability; no consent or redistribution license is inferred.'
                   ]}
        present(out / 'analysis-projected', out / 'presentation', context)
        write_json(out / 'presentation-context.json', context)
        safe = {'profile': 'reddit-export-observation 1.0.0', 'status': 'passed', 'counts': counts,
                'observation_decisions': dict(Counter(d['decision'] for d in a['payload']['decisions'])),
                'blockers': dict(Counter(reason for d in a['payload']['decisions'] for reason in d['blockers'])),
                'body_words': words, 'title_words': modules['text']['payload']['titles']['counts']['retained_words'],
                'usable_body_records': modules['coverage']['payload']['usable_body_records'],
                'style_eligible_records': modules['coverage']['payload']['eligible_style_records'],
                'activity_events': modules['activity']['payload']['event_count'],
                'modules': {name: {'status': m['status'], 'reason_codes': m['reason_codes']} for name, m in modules.items()},
                'finding_count': len(results['findings']),
                'finding_types': dict(Counter(f['method_id'] if 'method_id' in f else f.get('kind', 'unspecified') for f in results['findings'])),
                'reuse': {k: len(modules['reuse']['payload'][k]) for k in ('exact_groups', 'pairs', 'connected_groups')},
                'independent_baseline': receipt['checks']['independent_baseline'],
                'identity_contract': receipt['checks']['identity_contract'],
                'engine': {'version': engine_info['version'], 'implementation_sha256': engine_info['implementation_sha256'], 'config_sha256': engine_info['config_sha256']},
                'language_declaration_supplied': False, 'analysis_is_scientific_pilot': False}
        write_json(out / 'safe-aggregate.json', safe)
        receipt['checks']['prose_utility'] = {'body_words': words, 'text_bearing_events': counts['text_bearing_events']}
        receipt['status'] = 'passed'
    except Exception as exc:
        receipt['status'] = 'failed'
        receipt['error_type'] = type(exc).__name__
        if type(exc) is ValueError and str(exc).replace('_', '').replace('-', '').isalnum():
            receipt['error_code'] = str(exc)
        raise
    finally:
        receipt['preservation'] = {
            'originals_unchanged': originals == {str(args.source): source_inventory(args.source), str(args.existing_bundle): inventory(args.existing_bundle), str(args.existing_conservative): inventory(args.existing_conservative)},
            'engine_unchanged': frozen == {folder: inventory(args.engine_root / folder) for folder in frozen},
            'frozen_contracts_unchanged': frozen_contract == {folder: inventory(ROOT / folder) for folder in frozen_contract},
            'projection_implementation_unchanged_during_run': implementation == {folder: inventory(ROOT / folder) for folder in implementation}}
        if not all(receipt['preservation'].values()):
            receipt['status'] = 'failed'
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(out / 'execution-receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'preservation': receipt['preservation'], 'checks': receipt['checks'].get('prose_utility')}))
    return 0 if receipt['status'] == 'passed' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__, 'details': 'See the new private execution receipt and logs.'}))
        raise SystemExit(2)
