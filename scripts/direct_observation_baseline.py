"""Independent direct CSV baseline for the bounded export-observation check.

Does not call either projection mapper, select rows from their decisions, or
copy projected record values. It deliberately shares experimental snapshot
metadata after checking the parser/language/scope, so full numerical results
can be compared on identical inputs. This is validation code, not a second
general-purpose converter. Only the observed CSV layout is supported.
"""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile


def canonical(value):
    # All identity keys here are ASCII; no numbers or Unicode property names.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def alias(kind, value):
    domain = 'record-key' if kind == 'record' else 'account-key'
    digest = hashlib.sha256(('AHIF:projection-' + domain + ':1\n').encode() + canonical(value)).hexdigest()
    return ('ahas-r:' if kind == 'record' else 'ahas-a:') + digest


def key(collection, identifier):
    return {'namespace': 'urn:ahif:service:reddit', 'collection': collection,
            'id_type': 'native', 'id': identifier}


def unsupported(text):
    reasons = []
    if re.search(r'<!--|</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*|\s*/?)>', text):
        reasons.append('html')
    if re.search(r'\[/?(?:quote|code|url|img)(?:\]|=|\s)', text, re.I):
        reasons.append('bbcode')
    if '>!' in text or '!<' in text:
        reasons.append('spoiler')
    if '~~' in text:
        reasons.append('strikethrough')
    return reasons


def build(source, selection, snapshot, destination):
    """Return baseline row inventory; no candidate analytical rows are inputs."""
    if snapshot['text_format'] != 'markdown' or snapshot['default_language'] != 'und':
        raise ValueError('baseline_requires_declared_markdown_und')
    if snapshot['capture_utc'] is not None or snapshot['coverage']['status'] != 'sampled':
        raise ValueError('baseline_snapshot_scope')
    account = alias('account', {'account_key': selection['account_key'], 'source_id': selection['source_id']})
    if snapshot['account_id'] != account:
        raise ValueError('baseline_account_binding')
    source = Path(source)
    # Whitelist two members; unrelated export data never enters this process.
    if source.is_dir():
        members = {name: (source / name).read_bytes() for name in ('comments.csv', 'posts.csv')}
    else:
        with zipfile.ZipFile(source) as archive:
            members = {name: archive.read(name) for name in ('comments.csv', 'posts.csv')}
    result = []
    inventory = []
    seen = set()
    for member, raw in members.items():
        collection = 'comments' if member == 'comments.csv' else 'posts'
        rows = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True)
        for ordinal, r in enumerate(rows, 1):
            native = r['id']
            if (collection, native) in seen:
                raise ValueError('baseline_duplicate_requires_separate_conflict_review')
            seen.add((collection, native))
            if not re.fullmatch(r'[a-z0-9]+', native):
                raise ValueError('baseline_source_id')
            stamp = r['date']
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC', stamp):
                raise ValueError('baseline_requires_exact_observed_timestamp_layout')
            created = datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S UTC').strftime('%Y-%m-%dT%H:%M:%SZ')
            lifecycle = {'[removed]': 'removed', '[deleted]': 'deleted'}.get(r['body'])
            body_reasons = ([lifecycle] if lifecycle else ['empty_source_field'] if r['body'] == '' else unsupported(r['body']))
            text = None if body_reasons else r['body']
            title = r.get('title') or None
            title_reasons = ([lifecycle] if lifecycle and title else unsupported(title) if title else ['absent_title'])
            if title_reasons:
                title = None
            thread = None
            url = urlsplit(r['permalink'])
            matched = re.fullmatch(r'/r/([^/]+)/comments/([a-z0-9]+)/[^/]+/(?:([a-z0-9]+)/)?', url.path)
            if (url.scheme == 'https' and url.netloc in {'reddit.com', 'www.reddit.com', 'old.reddit.com'}
                    and not url.query and not url.fragment and matched and matched[1] == r['subreddit']
                    and ((collection == 'comments' and matched[3] == native)
                         or (collection == 'posts' and matched[2] == native and not matched[3]))):
                thread = matched[2]
                if collection == 'comments' and r['link']:
                    link = urlsplit(r['link'])
                    lm = re.fullmatch(r'/r/([^/]+)/comments/([a-z0-9]+)(?:/[^/]+/)?', link.path)
                    if not (link.scheme == 'https' and link.netloc in {'reddit.com', 'www.reddit.com', 'old.reddit.com'}
                            and not link.query and not link.fragment and lm and (lm[1], lm[2]) == (matched[1], matched[2])):
                        thread = None
            parent = r.get('parent')
            parent_id = alias('record', key('posts' if parent == thread else 'comments', parent)) if parent and thread else None
            out = {'schema_version': '1.0.0', 'id': alias('record', key(collection, native)), 'account_id': account,
                   'kind': 'comment' if collection == 'comments' else 'submission',
                   'status': 'present' if text is not None else lifecycle or 'unavailable', 'text': text, 'title': title,
                   'created_utc': created, 'edited_utc': None, 'edit_state': 'unknown', 'language': 'und',
                   'subreddit': r['subreddit'] if 0 < len(r['subreddit']) <= 256 else None,
                   'parent_id': parent_id, 'thread_id': alias('record', key('posts', thread)) if thread else None,
                   'parent_created_utc': None, 'permalink': r['permalink'] if 0 < len(r['permalink']) <= 4096 else None}
            result.append(out)
            inventory.append({'member': member, 'row': ordinal, 'key': key(collection, native), 'output_id': out['id'],
                              'body_exclusion_reasons': body_reasons, 'title_exclusion_reasons': title_reasons})
    result.sort(key=lambda r: (r['created_utc'] or '', r['id']))
    destination = Path(destination)
    destination.mkdir(mode=0o700)
    (destination / 'records.jsonl').write_bytes(b''.join(canonical(r) + b'\n' for r in result))
    # Shared experiment identity/coverage explicitly; every record field above
    # was independently derived from source columns and stated policy.
    (destination / 'snapshot.json').write_bytes(canonical(snapshot) + b'\n')
    return {'record_count': len(result), 'records': inventory,
            'shared_snapshot_metadata': 'Same experimental identity and scope; markdown and und explicitly verified.',
            'source_members': {name: hashlib.sha256(raw).hexdigest() for name, raw in members.items()}}
