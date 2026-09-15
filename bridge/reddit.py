"""Exact observed-layout Reddit CSV normalization; source profile 1.0.0."""
from __future__ import annotations
import csv
import io
import re
import stat
import zipfile
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlsplit
from .common import C, ahif, profile, sha, new_destination, write_bundle

PROFILE, PROFILE_SHA = profile('reddit-export-csv')
NS = PROFILE['namespace']
EXT = 'org.ahif.bridge:reddit-export-csv'

def unknown(reason='not_supplied'):
    return {'status':'unknown','reason':reason}

def key(collection, identifier, kind='native'):
    return {'namespace':NS,'collection':collection,'id_type':kind,'id':identifier}

def parse_time(raw):
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC',raw):
        try:
            datetime.strptime(raw,'%Y-%m-%d %H:%M:%S UTC')
            return {'status':'known','value':raw[:10]+'T'+raw[11:19]+'Z','precision':'second',
                    'basis':'source_documented_conversion','raw':raw}
        except ValueError:pass
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',raw):
        try:
            date.fromisoformat(raw)
            return {'status':'date_only','value':raw,'utc_offset':None,'basis':'source','raw':raw}
        except ValueError:pass
    return {**unknown('unrecognized_or_absent_export_date'),'raw':raw}

def read_members(source):
    """Read just two bounded members; never extract an archive or follow links."""
    source=Path(source)
    if source.is_symlink():raise ValueError('source_symlink')
    names=PROFILE['members']
    limit=PROFILE['limits']['member_bytes']
    result={}
    if source.is_dir():
        for name in names:
            path=source/name
            if path.is_symlink() or not path.is_file():raise ValueError('source_member_not_regular')
            with path.open('rb') as f: result[name]=f.read(limit+1)
    else:
        with zipfile.ZipFile(source) as z:
            for name in names:
                matches=[i for i in z.infolist() if i.filename==name]
                if len(matches)!=1:raise ValueError('missing_or_duplicate_selected_member')
                info=matches[0]
                if info.file_size>limit:raise ValueError('source_member_byte_limit')
                mode=info.external_attr >> 16
                if info.is_dir() or stat.S_ISLNK(mode) or info.flag_bits & 1:raise ValueError('unsupported_selected_member')
                with z.open(info) as f:result[name]=f.read(limit+1)
    if any(len(b)>limit for b in result.values()):raise ValueError('source_member_byte_limit')
    return result

def parse_members(members):
    result={}
    previous=csv.field_size_limit()
    csv.field_size_limit(PROFILE['limits']['field_codepoints'])
    try:
        for name,raw in members.items():
            if raw.startswith(b'\xef\xbb\xbf'):raise ValueError('source_bom_unsupported')
            reader=csv.reader(io.StringIO(raw.decode('utf-8'),newline=''),strict=True)
            if next(reader,None)!=PROFILE['members'][name]:raise ValueError('source_header_mismatch')
            rows=[]
            for row in reader:
                if len(row)!=len(PROFILE['members'][name]):raise ValueError('source_row_width')
                value={f:v for f,v in zip(PROFILE['members'][name],row) if f not in PROFILE['ignored_columns']}
                row.clear()
                if not re.fullmatch(r'[0-9a-z]+',value['id']):raise ValueError('source_id_invalid')
                rows.append(value)
                if len(rows)>PROFILE['limits']['rows_per_member']:raise ValueError('source_row_limit')
            result[name]=rows
    finally:csv.field_size_limit(previous)
    return result

def thread_key(row, collection):
    try:u=urlsplit(row['permalink'])
    except ValueError:return None
    if u.scheme!='https' or u.netloc not in {'reddit.com','www.reddit.com','old.reddit.com'} or u.query or u.fragment:return None
    m=re.fullmatch(r'/r/([^/]+)/comments/([0-9a-z]+)/[^/]+/(?:([0-9a-z]+)/)?',u.path)
    if not m or m[1]!=row['subreddit']:return None
    if (collection=='comments' and m[3]!=row['id']) or (collection=='posts' and (m[2]!=row['id'] or m[3])):return None
    if collection=='comments' and row.get('link'):
        try:link=urlsplit(row['link'])
        except ValueError:return None
        lm=re.fullmatch(r'/r/([^/]+)/comments/([0-9a-z]+)(?:/[^/]+/)?',link.path)
        if link.scheme!='https' or link.netloc not in {'reddit.com','www.reddit.com','old.reddit.com'} or link.query or link.fragment or not lm or (lm[1],lm[2])!=(m[1],m[2]):return None
    return key('posts',m[2])

def make_observations(members, subject, category):
    if subject not in {'export_subject','unknown'}:raise ValueError('subject_declaration_required')
    if category not in {'user_supplied','synthetic'}:raise ValueError('source_category_unsupported')
    raw_rows=parse_members(members)
    source={'mode':'synthetic' if category=='synthetic' else 'account_export',
      'description':'Supplied comments.csv and posts.csv under Reddit CSV profile 1.0.0; authenticity not established.',
      'acquired_at':unknown(),'content_as_of':unknown(),'access':'unknown',
      'redistribution':{'status':'unknown','basis':'No rights declaration supplied.'},
      'artifacts':[{'sha256':sha(raw),'byte_length':len(raw),'media_type':'text/csv','label':name,'included_path':None}
                   for name,raw in sorted(members.items())],
      'extensions':{EXT:{'profile_sha256':PROFILE_SHA,'subject_declaration':subject,'source_category':category}}}
    source['source_id']=ahif.bound_id('source',source)
    sid=source['source_id']
    actor=key('accounts',sid+'#export-subject','source_local') if subject=='export_subject' else None
    config={'profile_sha256':PROFILE_SHA,'subject':subject,'source_category':category}
    rows=[]
    for name, data in raw_rows.items():
        collection=PROFILE['collections'][name]
        for n,raw in enumerate(data,1):
            def locator(column=None):return {'kind':'csv_row','value':f'{name}#row={n}'+('' if column is None else ';column='+column),'artifact_sha256':sha(members[name])}
            sentinel=PROFILE['sentinels'].get(raw['body'])
            parts=[]
            for field in (['title','body'] if collection=='posts' else ['body']):
                if (field=='body' and sentinel) or raw[field]=='':continue
                parts.append({'part_id':field,'role':field,'attribution':{'relation':'record_actor' if actor else 'unknown','account_key':None},
                   'format':'plain' if field=='title' else 'other','format_variant':None if field=='title' else 'Reddit-export-unknown',
                   'text':raw[field],'fidelity':'source_field','language':{'tag':'und','basis':'unknown'},'locator':locator(field)})
            content=({'availability':'present','completeness':'unknown','reason':'export_does_not_declare_text_completeness','parts':parts}
                if parts else {'availability':'unavailable','completeness':'not_applicable','reason':sentinel or 'blank_field_not_proof_of_absence','parts':[]})
            row={'format_version':'0.1.1','record_key':key(collection,raw['id']),'source_id':sid,
                'observed_at':unknown(),'actor':actor,'kind':'reply' if collection=='comments' else 'post',
                'native_kind':'comment' if collection=='comments' else 'submission','created_at':parse_time(raw['date']),
                'updated_at':unknown(),'lifecycle':{'state':sentinel or 'unknown','edit_state':'unknown','native_revision_id':None},
                'visibility':'unknown','content':content,'permalink':raw['permalink'] or None,
                'provenance':{'locator':locator(),'normalizer':{'name':'ahif-reddit-export-csv','version':'1.0.0','configuration_sha256':sha(C(config))},
                    'transformations':[{'operation':'csv_transport_decode','version':'1.0.0'},
                        {'operation':'reddit_export_time_parse','version':'1.0.0','input_locator':locator('date')}],
                    'notes':'Only contribution columns; no IP, profile, messages or credential ingestion.'},
                'contexts':[],'relations':[],'links':[],
                'extensions':{EXT:{'member':name,'row':n,'parent':raw.get('parent'), 'link':raw.get('link'),
                    'body_marker':raw['body'] if sentinel else None,'empty_fields':[f for f in ('body','title') if f in raw and raw[f]==''],
                    'ignored_columns':[f for f in PROFILE['ignored_columns'] if f in PROFILE['members'][name]]}}}
            if sentinel:row['provenance']['transformations'].append({'operation':'exact_export_unavailability_marker','version':'1.0.0','input_locator':locator('body'),'parameters':{'literal':raw['body']}})
            if raw['subreddit']:row['contexts'].append({'kind':'community','key':key('communities',raw['subreddit'],'handle'),'label':raw['subreddit'],'basis':'source'})
            thread=thread_key(raw,collection)
            if thread:row['contexts'].append({'kind':'thread','key':thread,'basis':'derived'})
            if collection=='comments':
                parent=raw['parent']
                target=None
                if parent:
                    if not re.fullmatch(r'[0-9a-z]+',parent):raise ValueError('source_parent_invalid')
                    if thread:target=key('posts' if thread['id']==parent else 'comments',parent)
                row['relations'].append({'type':'reply_to','target_type':'record','target_key':target,'target_url':None,
                    'resolution':'known_identity' if target else 'unknown','source_field':'parent'})
            if raw.get('url'):
                row['links'].append({'link_id':'destination','role':'native_destination','url_as_supplied':raw['url'],
                    'resolved_url':None,'resolution_basis':'not_attempted','source_field':'url'})
            row['observation_id']=ahif.bound_id('record',row)
            rows.append(row)
    manifest={'format':'AHIF','format_version':'0.1.1','dataset_id':'reddit-csv-'+sid[7:], 'sources':[source],
      'coverage':[{'source_id':sid,'account_key':actor,'scope_description':'Rows supplied in comments.csv and posts.csv.',
      'status':'unknown','basis':'The export supplies no independently established completeness declaration.',
      'selection_description':'Two contribution members only; source retrieval/filter history unknown.',
      'start':unknown(),'end':unknown(),'known_gaps':[],'reported_totals':[]}], 'files':[]}
    return manifest,rows

def verify_fidelity(source, bundle):
    """Independent locator lookup: compare every exported body/title, not just parts."""
    from .common import read_bundle
    members=read_members(source); raw=parse_members(members)
    manifest,records,accounts,_=read_bundle(bundle)
    expected={(name,n) for name,rows in raw.items() for n in range(1,len(rows)+1)}
    seen=set(); fields=[]
    for r in records:
        e=r['extensions'][EXT]; name=e['member']; n=e['row']; native=raw[name][n-1]
        if (name,n) in seen:raise ValueError('fidelity_duplicate_locator')
        seen.add((name,n))
        expected_parts={f for f in ('body','title') if f in native and native[f]!=''
            and not (f=='body' and native[f] in PROFILE['sentinels'])}
        actual_parts=r['content']['parts']
        if {p['part_id'] for p in actual_parts}!=expected_parts or len(actual_parts)!=len(expected_parts):
            raise ValueError('fidelity_unexpected_text_part')
        for field in ('body','title'):
            if field not in native:continue
            part=next((p for p in r['content']['parts'] if p['part_id']==field),None)
            value=part['text'] if part else (e['body_marker'] if field=='body' and e['body_marker'] is not None else '')
            if value!=native[field]:raise ValueError('fidelity_text_mismatch')
            locator={'kind':'csv_row','value':f'{name}#row={n};column={field}','artifact_sha256':sha(members[name])}
            if part and part['locator']!=locator:raise ValueError('fidelity_locator_mismatch')
            if not part and value=='' and field not in e['empty_fields']:raise ValueError('fidelity_empty_unaccounted')
            fields.append({'observation_id':r['observation_id'],'locator':locator,'utf8_sha256':sha(value.encode()),
                'codepoints':len(value),'representation':'source_field' if part else 'sentinel_marker' if value else 'empty_field',
                'conversion':'CSV transport decode only; exact decoded Unicode string'})
    if seen!=expected or accounts:raise ValueError('fidelity_row_inventory')
    artifacts={a['label']:a['sha256'] for s in manifest['sources'] for a in s['artifacts']}
    if artifacts!={name:sha(data) for name,data in members.items()}:raise ValueError('fidelity_source_hash')
    return {'status':'passed','source_profile_sha256':PROFILE_SHA,'fields':sorted(fields,key=lambda f:(f['observation_id'],f['locator']['value']))}

def normalize(source,destination,*,subject,category='user_supplied'):
    members=read_members(source)
    manifest,rows=make_observations(members,subject,category)
    with new_destination(destination) as stage:
        checked=write_bundle(stage,manifest,rows)
        fidelity=verify_fidelity(source,stage)
    return {'check':checked,'fidelity':fidelity,'source_id':manifest['sources'][0]['source_id']}
