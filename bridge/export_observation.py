"""Explicit supplied-field projection; frozen AHIF and conservative policy stay intact."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator

from .common import C, ROOT, ahif, file_info, load, new_destination, profile, read_bundle, sha, write_json
from .projection import alias, engine, equivalence, field, selection_for, time_value, Refusal
from .reddit import EXT, NS, PROFILE_SHA as SOURCE_SHA

PROFILE_DIR = ROOT / 'profiles/reddit-export-observation/1.0.0'
PROFILE, PROFILE_SHA = profile('reddit-export-observation')
SCHEMA = load((PROFILE_DIR / 'receipt.schema.json').read_bytes())
LANGUAGE_SCHEMA = load((PROFILE_DIR / 'language-declaration.schema.json').read_bytes())
if sha(C(LANGUAGE_SCHEMA)) != PROFILE['language_declaration_schema_sha256']:
    raise ValueError('language_declaration_schema_digest_mismatch')
RECEIPT_DOMAIN = b'AHIF:reddit-export-observation-receipt:1.0.0\n'
SNAPSHOT_DOMAIN = b'AHIF:reddit-export-observation:1.0.0\n'


def markup_blockers(text):
    """Known unsupported spellings; this does not recognize every dialect construct."""
    blockers = []
    for name, pattern in PROFILE['unsupported_markup_patterns'].items():
        if re.search(pattern, text, re.IGNORECASE):
            blockers.append(name)
    return sorted(blockers)


def language_input(value, selection, records):
    if value is None:
        return None, None
    ahif.check_values(value)
    Draft202012Validator(LANGUAGE_SCHEMA).validate(value)
    if value['source_id'] != selection['source_id'] or value['account_key'] != selection['account_key']:
        raise ValueError('language_declaration_scope_mismatch')
    ids = value['observation_ids']
    if ids != sorted(set(ids)):
        raise ValueError('language_declaration_scope_not_canonical')
    by_id = {r['observation_id']: r for r in records}
    for identifier in ids:
        r = by_id.get(identifier)
        if r is None or r['source_id'] != value['source_id'] or r['actor'] != value['account_key']:
            raise ValueError('language_declaration_observation_mismatch')
    return value, sha(b'AHIF:export-observation-language:1.0.0\n' + C(value))


def inventory(row):
    """Values not representable by AHAS remain explicit and bound, with no prose copy."""
    names = ('actor', 'lifecycle', 'visibility', 'observed_at', 'created_at', 'updated_at')
    result = {name: row[name] for name in names if name in row}
    if 'content' in row:
        result['content'] = {k: v for k, v in row['content'].items() if k != 'parts'}
        result['parts'] = [{**{k: v for k, v in p.items() if k != 'text'},
                            'text_sha256': sha(p['text'].encode('utf-8'))}
                           for p in row['content']['parts']]
    return result


def choose_fields(r, declared_language):
    content = r['content']
    parts = content['parts']
    common = []
    state = r['lifecycle']['state']
    if state in {'deleted', 'removed', 'restricted'}:
        common.append('known_nonvisible_retained_text_excluded')
    if content['availability'] == 'redacted':
        common.append('redacted_content_excluded')
    if content['completeness'] not in {'complete', 'unknown'}:
        common.append('content_completeness_' + content['completeness'])
    if content['availability'] not in {'present', 'empty'}:
        common.append('content_availability_' + content['availability'])
    if any(p['role'] not in {'body', 'title'} or p['part_id'] != p['role'] for p in parts):
        common.append('source_field_structure_unsupported')
    values = {}
    fields = []
    for source_name, destination, limit in (('body', 'text', 200000), ('title', 'title', 20000)):
        found = [p for p in parts if p['role'] == source_name]
        blockers = list(common)
        if found and source_name == 'title' and r.get('native_kind') != 'submission':
            blockers.append('title_not_supported_for_comment')
        if len(found) != 1:
            blockers.append('source_' + source_name + ('_not_supplied' if not found else '_parts_ambiguous'))
        for p in found:
            if p['attribution']['relation'] != 'record_actor':
                blockers.append('source_attribution_not_selected_actor')
            if p['fidelity'] != 'source_field':
                blockers.append('source_field_fidelity_unestablished')
            permitted = ((source_name == 'body' and
                          ((p['format'] == 'other' and p.get('format_variant') == 'Reddit-export-unknown')
                           or p['format'] == 'commonmark'))
                         or (source_name == 'title' and p['format'] == 'plain'))
            if not permitted:
                blockers.append('source_' + source_name + '_format_unsupported')
            if not p['text']:
                blockers.append('source_' + source_name + '_empty_not_original_absence')
            if source_name == 'body' and p['text'].strip() in {'[removed]', '[deleted]'}:
                blockers.append('body_sentinel_not_prose')
            if len(p['text']) > limit:
                blockers.append('ahas_' + destination + '_length_limit')
            blockers.extend(markup_blockers(p['text']))
        blockers = sorted(set(blockers))
        copied = len(found) == 1 and not blockers
        value = found[0]['text'] if copied else None
        values[destination] = value
        fields.append({'field': 'ahas.' + destination,
                       'disposition': 'copied_literal' if copied else 'omitted',
                       'reason': 'literal_source_field_under_declared_commonmark_analysis_policy' if copied else 'field_not_eligible; originals_retained_in_AHIF',
                       'blockers': blockers, 'source_part_ids': [p['part_id'] for p in found],
                       'source_sha256': sha(found[0]['text'].encode()) if len(found) == 1 else None,
                       'output_sha256': sha(value.encode()) if value is not None else None})
    # AHAS has one language per row for both fields. Refuse contradictory claims
    # to select English, while preserving generic supplied-field measurements.
    retained = [p for p in parts if (p['role'] == 'body' and values['text'] is not None)
                or (p['role'] == 'title' and values['title'] is not None)]
    tags = {p['language']['tag'] for p in retained}
    language = next(iter(tags)) if len(tags) == 1 else 'und'
    language_reason = 'source_part_language' if language != 'und' else 'unknown_or_mixed_source_language_stays_und'
    if declared_language:
        language = declared_language
        language_reason = 'explicit_scope_bound_supplier_confirmation; AHIF_unchanged'
    if not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', language):
        language = 'und'
        language_reason = 'AHAS_language_syntax_unsupported; original_retained'
    fields.append(field('ahas.language', 'mapped' if language != 'und' else 'constant', language_reason))
    values['language'] = language
    return values, fields


def map_record(r, account_id, add_alias, declared_language=None):
    event_blockers = []
    if r['record_key']['namespace'] != NS or r['record_key']['id_type'] != 'native':
        event_blockers.append('source_key_unsupported')
    expected = {'comments': ('reply', 'comment'), 'posts': ('post', 'submission')}.get(r['record_key']['collection'])
    if not expected or (r['kind'], r.get('native_kind')) != expected:
        event_blockers.append('kind_unsupported')
    values, fields = choose_fields(r, declared_language)
    metadata_blockers = []
    times = {}
    for source, target in (('created_at', 'created_utc'), ('updated_at', 'edited_utc')):
        try:
            value, reason = time_value(r[source])
        except Refusal:
            value, reason = None, 'timestamp_precision_unsupported_not_imputed'
        times[target] = value
        if value is None:
            metadata_blockers.append(target + ':' + reason)
        fields.append(field('ahas.' + target, 'mapped' if value else 'omitted', reason))
    if times['created_utc'] and times['edited_utc'] and ahif.utc_ns(times['edited_utc']) < ahif.utc_ns(times['created_utc']):
        event_blockers.append('edit_before_creation')
    parent = None
    relations = [x for x in r.get('relations', []) if x['type'] == 'reply_to']
    targets = {C(x['target_key']): x['target_key'] for x in relations if x['resolution'] == 'known_identity'}
    if len(targets) == 1 and all(x['resolution'] == 'known_identity' for x in relations):
        target = next(iter(targets.values()))
        if target['namespace'] == NS and target['collection'] in {'comments', 'posts'} and target['id_type'] == 'native':
            parent = add_alias(target)
        else:
            metadata_blockers.append('parent_key_unsupported_omitted')
    elif relations:
        metadata_blockers.append('parent_ambiguous_or_unknown_omitted')
    communities = [x for x in r.get('contexts', []) if x['kind'] == 'community']
    subreddit = communities[0].get('label') if len(communities) == 1 else None
    if subreddit is not None and len(subreddit) > 256:
        subreddit = None
        metadata_blockers.append('community_label_length_omitted')
    threads = [x for x in r.get('contexts', []) if x['kind'] == 'thread']
    thread = threads[0]['key'] if len(threads) == 1 else None
    if thread and not (thread['namespace'] == NS and thread['collection'] == 'posts' and thread['id_type'] == 'native'):
        thread = None
        metadata_blockers.append('thread_key_unsupported_omitted')
    permalink = r.get('permalink')
    if permalink is not None and len(permalink) > 4096:
        permalink = None
        metadata_blockers.append('permalink_length_omitted')
    fields.extend([field('ahas.id', 'aliased', 'full_logical_record_key; never_text_identity'),
                   field('ahas.account_id', 'aliased', 'selected_source_local_export_subject; no_personal_authorship_claim'),
                   field('ahas.kind', 'mapped', 'documented_native_collection_kind'),
                   field('ahas.status', 'mapped', 'supplied_analytical_body_availability; lifecycle_and_as_of_remain_in_receipt'),
                   field('ahas.edit_state', 'mapped', 'exact_source_edit_state; no_time_inference'),
                   field('ahas.subreddit', 'mapped' if subreddit else 'omitted', 'single_compatible_source_label_else_null'),
                   field('ahas.parent_id', 'aliased' if parent else 'omitted', 'single_compatible_target_else_null; missing_parent_not_fabricated'),
                   field('ahas.thread_id', 'aliased' if thread else 'omitted', 'single_compatible_source_root_else_null'),
                   field('ahas.parent_created_utc', 'omitted', 'not_selected_from_an_independent_parent_observation'),
                   field('ahas.permalink', 'mapped' if permalink else 'omitted', 'literal_supplied_reference_within_limit'),
                   field('ahif.links', 'receipt_only', 'native_destination_not_appended_to_body_or_title')])
    blockers = sorted(set(event_blockers + metadata_blockers + [b for f in fields for b in f.get('blockers', [])]))
    if event_blockers:
        return None, fields, blockers, sorted(set(event_blockers))
    state = r['lifecycle']['state']
    out = {'schema_version': '1.0.0', 'id': add_alias(r['record_key']), 'account_id': account_id,
           'kind': expected[1], **values, **times, 'edit_state': r['lifecycle']['edit_state'],
           'status': 'present' if values['text'] is not None else state if state in {'deleted', 'removed'} else 'unavailable',
           'subreddit': subreddit, 'parent_id': parent, 'thread_id': add_alias(thread) if thread else None,
           'parent_created_utc': None, 'permalink': permalink}
    return out, fields, blockers, []


def prepare(bundle, selection, stage, language_declaration=None):
    manifest, records, accounts, _ = read_bundle(bundle)
    if selection != selection_for(selection.get('source_id')):
        raise ValueError('selection_contract_unsupported')
    sid = selection['source_id']
    sources = {s['source_id']: s for s in manifest['sources']}
    if sid not in sources:
        raise ValueError('selection_source_missing')
    source = sources[sid]
    source_declaration = source.get('extensions', {}).get(EXT, {})
    if source_declaration.get('profile_sha256') != SOURCE_SHA or source_declaration.get('subject_declaration') != 'export_subject':
        raise ValueError('source_profile_or_subject_unsupported')
    category = source_declaration.get('source_category')
    if category not in {'synthetic', 'user_supplied'}:
        raise ValueError('source_category_unsupported')
    language_declaration, declaration_sha = language_input(language_declaration, selection, records)
    account = selection['account_key']
    account_id = alias('account', {'account_key': account, 'source_id': sid})
    aliases = {account_id: {'type': 'account', 'key': account, 'source_id': sid, 'alias': account_id}}

    def add_alias(k):
        result = alias('record', k)
        entry = {'type': 'record', 'key': k, 'source_id': None, 'alias': result}
        if result in aliases and aliases[result] != entry:
            raise ValueError('alias_collision')
        aliases[result] = entry
        return result

    decisions = {}

    def decide(r, action, blockers, out_id=None, fields=(), row_type='record'):
        finalized_fields = [dict(f) for f in fields]
        if out_id is None:
            for f in finalized_fields:
                if f['field'] in {'ahas.text', 'ahas.title'}:
                    f.update(disposition='omitted', output_sha256=None,
                             reason='no_analytical_event_output; originals_retained_in_AHIF',
                             blockers=sorted(set(f['blockers'] + blockers)))
        decisions[r['observation_id']] = {
            'observation_id': r['observation_id'], 'row_type': row_type, 'source_id': r['source_id'],
            'key': r['record_key' if row_type == 'record' else 'account_key'],
            'locator': r['provenance']['locator'], 'decision': action, 'blockers': sorted(set(blockers)),
            'output_id': out_id, 'equivalence_sha256': equivalence(r),
            'transformations': r['provenance']['transformations'], 'fields': finalized_fields, 'inventory': inventory(r)}

    groups = defaultdict(list)
    for r in records:
        if r['source_id'] == sid:
            groups[C(r['record_key'])].append(r)
        else:
            _, fields, blockers, _ = map_record(r, account_id, add_alias)
            decide(r, 'event_excluded', blockers + ['outside_selected_source; identity_continuity_unestablished'], fields=fields)
    for a in accounts:
        decide(a, 'event_excluded', ['account_profile_not_a_posting_event'], row_type='account')
    projected = []
    for _, observations in sorted(groups.items()):
        observations.sort(key=lambda r: r['observation_id'])
        mapped = {}
        for r in observations:
            lang = (language_declaration['language'] if language_declaration and r['observation_id'] in language_declaration['observation_ids'] else None)
            mapped[r['observation_id']] = map_record(r, account_id, add_alias, lang)
        equivalences = {equivalence(r) for r in observations}
        # A declaration that treats equivalent captures differently is not a
        # license for a lexical tie-break to silently choose the desired language.
        output_languages = {mapped[r['observation_id']][0]['language'] for r in observations if mapped[r['observation_id']][0]}
        if len(equivalences) > 1 or len(output_languages) > 1:
            for r in observations:
                _, fields, blockers, _ = mapped[r['observation_id']]
                decide(r, 'unresolved_conflict', blockers + ['unresolved_observation_conflict'], fields=fields)
            continue
        selected = observations[0]
        out, fields, blockers, event_blockers = mapped[selected['observation_id']]
        if selected['actor'] != account:
            event_blockers.append('actor_unknown' if selected['actor'] is None else 'outside_selected_actor; identity_continuity_unestablished')
        if event_blockers:
            for r in observations:
                _, individual_fields, individual_blockers, _ = mapped[r['observation_id']]
                decide(r, 'event_excluded', individual_blockers + event_blockers, fields=individual_fields)
            continue
        projected.append(out)
        decide(selected, 'accepted' if out['text'] is not None else 'text_excluded', blockers,
               out_id=out['id'], fields=fields)
        for r in observations[1:]:
            _, alternative_fields, alternative_blockers, _ = mapped[r['observation_id']]
            decide(r, 'equivalent_capture', alternative_blockers + ['equivalent_capture_not_another_event'],
                   out_id=out['id'], fields=alternative_fields)
    projected.sort(key=lambda r: (r['created_utc'] is None, r['created_utc'] or '', r['id']))
    # Preserve otherwise valid events when their selected parent time contradicts
    # an internal relationship: omit that uncertain reference rather than invent time.
    by_id = {r['id']: r for r in projected}
    for out in projected:
        parent = by_id.get(out['parent_id'])
        if parent and parent['created_utc'] and out['created_utc'] and ahif.utc_ns(parent['created_utc']) > ahif.utc_ns(out['created_utc']):
            out['parent_id'] = None
            for d in decisions.values():
                if d['output_id'] == out['id']:
                    d['blockers'] = sorted(set(d['blockers'] + ['internal_parent_after_child_reference_omitted']))
                    for f in d['fields']:
                        if f['field'] == 'ahas.parent_id':
                            f.update(disposition='omitted', reason='internal_parent_after_child; timestamps_preserved_reference_omitted')
    snapshot = {'schema_version': '1.0.0', 'account_id': account_id, 'source_category': category,
                'capture_utc': None, 'text_format': 'markdown', 'default_language': 'und',
                'source_notes': 'reddit-export-observation 1.0.0: supplied fields, not verified original or publicly visible wording. See mandatory projection interpretation presentation.',
                'license_notes': None, 'coverage': {'status': 'sampled', 'start_utc': None, 'end_utc': None, 'known_gaps': [],
                'notes': 'All eligible distinct supplied events retained; body/title eligibility separate. Unknown original completeness, content-as-of, visibility and language remain unknown. No completeness percentage.'}}
    identity = {'profile_sha256': PROFILE_SHA, 'selection': selection, 'language_declaration': language_declaration,
                'records': projected, 'snapshot_without_id': snapshot}
    snapshot['snapshot_id'] = 'ahas-observation:' + sha(SNAPSHOT_DOMAIN + C(identity))
    (stage / 'records.jsonl').write_bytes(b''.join(C(r) + b'\n' for r in projected))
    write_json(stage / 'snapshot.json', snapshot)
    config, loader, thaw, engine_info = engine()
    loaded = loader(stage / 'records.jsonl', stage / 'snapshot.json', config)
    engine_info.update(canonical_snapshot_sha256=loaded.canonical_sha256, loader_warnings=thaw(loaded.warnings))
    record_decisions = [d for d in decisions.values() if d['row_type'] == 'record']
    all_keys = {C(r['record_key']) for r in records}
    conflict_keys = {C(d['key']) for d in record_decisions if d['decision'] == 'unresolved_conflict'}
    projected_keys = {C(d['key']) for d in record_decisions if d['decision'] in {'accepted', 'text_excluded'}}
    counts = {'source_observations': len(records), 'distinct_events': len(all_keys),
              'projected_events': len(projected), 'text_bearing_events': sum(r['text'] is not None for r in projected),
              'title_bearing_events': sum(r['title'] is not None for r in projected),
              'text_excluded_events': sum(r['text'] is None for r in projected),
              'event_excluded_events': len(all_keys - projected_keys - conflict_keys),
              'unresolved_conflict_events': len(conflict_keys), 'account_observations': len(accounts),
              'equivalent_capture_observations': sum(d['decision'] == 'equivalent_capture' for d in record_decisions)}
    return {'ahif_version': '0.1.1', 'source_profile': {'id': 'reddit-export-csv', 'version': '1.0.0', 'sha256': SOURCE_SHA},
            'projection_profile': {'id': 'reddit-export-observation', 'version': '1.0.0', 'sha256': PROFILE_SHA},
            'selection': selection, 'language_declaration': language_declaration, 'language_declaration_sha256': declaration_sha,
            'input': {'canonical_manifest_sha256': sha(C(manifest)), 'manifest_bytes': file_info(Path(bundle) / 'manifest.json'),
                      'files': [file_info(Path(bundle) / f['path'], f['path']) for f in sorted(manifest['files'], key=lambda f: f['path'])],
                      'sources': manifest['sources']},
            'decisions': sorted(decisions.values(), key=lambda d: d['observation_id']),
            'aliases': sorted(aliases.values(), key=lambda a: a['alias']), 'counts': counts,
            'snapshot_fields': [field('ahas.' + f, 'mapped', {'capture_utc': 'unknown_not_import_clock',
                  'text_format': 'tested_CommonMark_analysis_interpretation_of_literal_export_fields; not_source_dialect_equivalence',
                  'coverage': 'deliberate_projection_scope; no_full_export_or_website_completeness_claim',
                  'default_language': 'und; per_record_declarations_bound_separately', 'license_notes': 'unknown_no_permission_inferred'}.get(f, 'versioned_projection_rule')) for f in sorted(snapshot)],
            'outputs': [file_info(stage / 'records.jsonl'), file_info(stage / 'snapshot.json')],
            'expanded_records': thaw(loaded.records), 'expanded_snapshot': thaw(loaded.manifest), 'ahas': engine_info}


def validate_receipt(receipt):
    ahif.check_values(receipt)
    Draft202012Validator(SCHEMA).validate(receipt)
    if receipt['payload_sha256'] != sha(RECEIPT_DOMAIN + C(receipt['payload'])):
        raise ValueError('receipt_payload_digest_mismatch')
    p = receipt['payload']
    ds = p['decisions']
    counts = p['counts']
    if len({d['observation_id'] for d in ds}) != len(ds):
        raise ValueError('receipt_duplicate_observation')
    selected = [d for d in ds if d['decision'] in {'accepted', 'text_excluded'}]
    if len({C(d['key']) for d in selected}) != len(selected):
        raise ValueError('receipt_duplicate_event_selection')
    if len(ds) != counts['source_observations'] + counts['account_observations']:
        raise ValueError('receipt_observation_count_mismatch')
    if len(selected) != counts['projected_events'] or len(selected) != len(p['expanded_records']):
        raise ValueError('receipt_output_count_mismatch')
    if counts['text_bearing_events'] + counts['text_excluded_events'] != counts['projected_events']:
        raise ValueError('receipt_text_count_mismatch')
    if sum(counts[k] for k in ('projected_events', 'event_excluded_events', 'unresolved_conflict_events')) != counts['distinct_events']:
        raise ValueError('receipt_event_count_mismatch')
    return receipt


def project(bundle, destination, selection, *, language_declaration=None, executed_at=None):
    with new_destination(destination) as stage:
        payload = prepare(bundle, selection, stage, language_declaration)
        receipt = {'receipt_version': '1.0.0', 'payload': payload,
                   'payload_sha256': sha(RECEIPT_DOMAIN + C(payload)),
                   'operational': {'executed_at': executed_at or datetime.now(timezone.utc).isoformat(),
                                   'bundle_path': str(Path(bundle).absolute()), 'output_path': str(Path(destination).absolute())}}
        validate_receipt(receipt)
        write_json(stage / 'projection-receipt.json', receipt)
    return receipt


def verify_projection(bundle, output):
    output = Path(output)
    receipt = validate_receipt(load((output / 'projection-receipt.json').read_bytes()))
    with TemporaryDirectory() as temp:
        replay = prepare(bundle, receipt['payload']['selection'], Path(temp), receipt['payload']['language_declaration'])
        if replay != receipt['payload']:
            raise ValueError('projection_replay_mismatch')
    for item in replay['outputs']:
        if file_info(output / item['path']) != item:
            raise ValueError('projection_output_digest_mismatch')
    return {'status': 'passed', 'payload_sha256': receipt['payload_sha256'],
            'canonical_snapshot_sha256': replay['ahas']['canonical_snapshot_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('project')
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--language-declaration', type=Path)
    v = commands.add_parser('verify')
    v.add_argument('--bundle', type=Path, required=True)
    v.add_argument('--projection', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'project':
            receipt = project(args.bundle, args.out, load(args.selection.read_bytes()),
                              language_declaration=load(args.language_declaration.read_bytes()) if args.language_declaration else None)
            result = {'status': 'passed', 'counts': receipt['payload']['counts'], 'payload_sha256': receipt['payload_sha256']}
        else:
            result = verify_projection(args.bundle, args.projection)
    except Exception as e:
        code = str(e) if type(e) is ValueError and re.fullmatch(r'[a-z_]+', str(e)) else 'validation_failed'
        print(json.dumps({'status': 'failed', 'error_type': type(e).__name__, 'error_code': code,
                          'details': 'No private exception text emitted.'}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
