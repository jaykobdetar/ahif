"""Versioned metadata-only projection into the actual frozen AHAS loader."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from jsonschema import Draft202012Validator
from .common import C, ROOT, ahif, file_info, load, new_destination, profile, read_bundle, sha, write_json
from .reddit import EXT, NS, PROFILE_SHA as SOURCE_SHA, key

PROFILE, PROFILE_SHA=profile('ahas-conservative')
SCHEMA=load((ROOT/'profiles/ahas-conservative/1.0.0/receipt.schema.json').read_bytes())

def alias(kind,identity):
    domain='record-key' if kind=='record' else 'account-key'
    return ('ahas-r:' if kind=='record' else 'ahas-a:')+sha(('AHIF:projection-'+domain+':1\n').encode()+C(identity))

def equivalence(row):
    # Remove only capture positions, not text, IDs, actors, times, metrics or state.
    value={k:v for k,v in row.items() if k not in {'observation_id','observed_at','provenance'}}
    if 'content' in value:
        value['content']={**value['content'],'parts':[{k:v for k,v in p.items() if k!='locator'} for p in value['content']['parts']]}
    if EXT in value.get('extensions',{}):
        value['extensions']={**value['extensions'],EXT:{k:v for k,v in value['extensions'][EXT].items() if k!='row'}}
    return sha(C(value))

def selection_for(source_id):
    return {'version':'1.0.0','source_id':source_id,'account_key':key('accounts',source_id+'#export-subject','source_local'),
            'scope':'all_supplied_records_non_temporal','as_of':'selected_observations_no_common_instant'}

def field(path,disposition,reason):
    return {'field':path,'disposition':disposition,'reason':reason}

class Refusal(ValueError):pass

def time_value(t):
    if t['status']=='unknown':return None,'unknown_not_imputed'
    if t['status'] in {'date_only','interval'}:return None,'coarse_time_omitted'
    if t['precision']=='nanosecond' or re.search(r'\.[0-9]{7,}Z$',t['value']):raise Refusal('timestamp_precision_unsupported')
    return t['value'],'exact_utc; original_basis_precision_and_raw_retained_in_evidence'

def map_record(r,account_id,add_alias):
    if r['record_key']['namespace']!=NS or r['record_key']['id_type']!='native':raise Refusal('source_key_unsupported')
    expected={'comments':('reply','comment'),'posts':('post','submission')}.get(r['record_key']['collection'])
    if not expected or (r['kind'],r.get('native_kind'))!=expected:raise Refusal('kind_unsupported')
    content=r['content']; state=r['lifecycle']['state']
    if content['parts']:
        raise Refusal('lifecycle_content_unrepresentable' if state!='visible' else 'text_projection_unsupported')
    if content['availability']!='unavailable':raise Refusal('body_incomplete_or_text_profile_unsupported')
    created,created_reason=time_value(r['created_at']); edited,edited_reason=time_value(r['updated_at'])
    fields=[]
    def put(name,value,disposition,reason):
        fields.append(field('ahas.'+name,disposition,reason)); return value
    parent=None
    relations=[x for x in r.get('relations',[]) if x['type']=='reply_to']
    targets={C(x['target_key']):x['target_key'] for x in relations if x['resolution']=='known_identity'}
    if len(targets)>1 or (targets and any(x['resolution']!='known_identity' for x in relations)):raise Refusal('parent_ambiguous')
    if targets:parent=add_alias(next(iter(targets.values())))
    communities=[x for x in r.get('contexts',[]) if x['kind']=='community']
    subreddit=communities[0].get('label') if len(communities)==1 else None
    if subreddit is not None and len(subreddit)>256:subreddit=None
    threads=[x for x in r.get('contexts',[]) if x['kind']=='thread']
    thread=threads[0]['key'] if len(threads)==1 else None
    if thread and not (thread['namespace']==NS and thread['collection']=='posts' and thread['id_type']=='native'):thread=None
    permalink=r.get('permalink')
    if permalink is not None and len(permalink)>4096:permalink=None
    out={
      'schema_version':put('schema_version','1.0.0','constant','AHAS input contract version'),
      'id':put('id',add_alias(r['record_key']),'aliased','full_record_key_domain_separated_hash'),
      'account_id':put('account_id',account_id,'aliased','selected_source_local_identity'),
      'kind':put('kind',expected[1],'mapped','declared_Reddit_native_collection_kind'),
      'text':put('text',None,'mapped','unavailable_content; no_authored_text_projected'),
      'status':put('status',state if state in {'deleted','removed'} else 'unavailable','mapped','lifecycle_and_availability_collapsed; originals_bound_in_AHIF'),
      'created_utc':put('created_utc',created,'mapped' if created else 'omitted',created_reason),
      'edited_utc':put('edited_utc',edited,'mapped' if edited else 'omitted',edited_reason),
      'edit_state':put('edit_state',r['lifecycle']['edit_state'],'mapped','exact_edit_state; revision_token_receipt_only'),
      'language':put('language','und','constant','no_selected_body_language_evidence'),
      'title':put('title',None,'mapped','no_retained_parts; no_title_invented'),
      'subreddit':put('subreddit',subreddit,'mapped' if subreddit else 'omitted','single_compatible_source_label_else_null; scoped_identity_not_preserved'),
      'parent_id':put('parent_id',parent,'aliased' if parent else 'omitted','single_known_target_else_unknown; missing_target_rows_not_created'),
      'thread_id':put('thread_id',add_alias(thread) if thread else None,'aliased' if thread else 'omitted','documented_post_root_mapping_else_unknown'),
      'parent_created_utc':put('parent_created_utc',None,'omitted','no_parent_observation_time_selected'),
      'permalink':put('permalink',permalink,'mapped' if permalink else 'omitted','exact_supplied_metadata_if_within_limit_else_null'),
    }
    return out,fields

def engine():
    import account_history_analyzer as package
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.io import canonical_bytes, load_snapshot, thaw
    from account_history_analyzer.pipeline import implementation_identity
    if package.__version__!='1.0.4':raise ValueError('ahas_version_unsupported')
    config=AnalysisConfig.from_toml()
    fingerprint,env,resources=implementation_identity()
    root=Path(package.__file__).parent
    contracts={n:sha((root/'contracts'/n).read_bytes()) for n in ['record.schema.json','snapshot.schema.json']}
    cfg=canonical_bytes(config.analytical())
    return config,load_snapshot,thaw,{'version':package.__version__,'implementation_sha256':fingerprint,'environment':env,
        'resources':resources,'contracts':contracts,'config_sha256':sha(cfg),'config_json':cfg.decode()}

def prepare(bundle,selection,stage):
    manifest,records,accounts,checked=read_bundle(bundle)
    if selection!=selection_for(selection.get('source_id')):raise ValueError('selection_contract_unsupported')
    sources={s['source_id']:s for s in manifest['sources']}
    sid=selection['source_id']
    if sid not in sources:raise ValueError('selection_source_missing')
    source=sources[sid]; declaration=source.get('extensions',{}).get(EXT,{})
    if declaration.get('profile_sha256')!=SOURCE_SHA or declaration.get('subject_declaration')!='export_subject':raise ValueError('source_profile_or_subject_unsupported')
    category=declaration.get('source_category')
    if category not in {'synthetic','user_supplied'}:raise ValueError('source_category_unsupported')
    account=selection['account_key']; account_id=alias('account',{'account_key':account,'source_id':sid})
    aliases={account_id:{'type':'account','key':account,'source_id':sid,'alias':account_id}}
    def add_alias(k):
        result=alias('record',k)
        entry={'type':'record','key':k,'source_id':None,'alias':result}
        if result in aliases and aliases[result]!=entry:raise ValueError('alias_collision')
        aliases[result]=entry
        return result
    decisions={};groups=defaultdict(list);source_groups=defaultdict(list)
    for r in records:
        if r['source_id']==sid:source_groups[C(r['record_key'])].append(r)
    def decide(r,action,reason,row_type='record',out_id=None,fields=()):
        preserved=[field('ahif.'+name,'receipt_only','exact_value_bound_by_observation_and_input_inventory') for name in sorted(r)]
        decisions[r['observation_id']]={'observation_id':r['observation_id'],'row_type':row_type,'source_id':r['source_id'],
            'key':r['record_key' if row_type=='record' else 'account_key'],'locator':r['provenance']['locator'],
            'decision':action,'reason':reason,'output_id':out_id,'equivalence_sha256':equivalence(r),
            'transformations':r['provenance']['transformations'],'fields':preserved+list(fields)}
    for r in accounts:decide(r,'excluded','account_profile_not_a_posting_event','account')
    for r in records:
        if r['actor'] is None:decide(r,'excluded','actor_unknown')
        elif r['source_id']!=sid:decide(r,'excluded','outside_selected_source; identity_continuity_unestablished')
        elif r['actor']!=account:decide(r,'excluded','outside_selected_actor; identity_continuity_unestablished')
        else:groups[C(r['record_key'])].append(r)
    projected=[]
    for k,observations in sorted(groups.items()):
        # A same-source competing actor claim for an otherwise selected key is
        # a conflict, even if that alternative initially fell outside the actor filter.
        observations=source_groups[k]
        observations.sort(key=lambda r:r['observation_id'])
        if len({equivalence(r) for r in observations})>1:
            for r in observations:decide(r,'quarantined','unresolved_observation_conflict')
            continue
        selected=observations[0]
        try:out,fields=map_record(selected,account_id,add_alias)
        except Refusal as e:
            for r in observations:decide(r,'quarantined',str(e))
            continue
        projected.append(out)
        decide(selected,'selected','sole_observation' if len(observations)==1 else 'equivalent_observation_min_id',out_id=out['id'],fields=fields)
        for r in observations[1:]:decide(r,'excluded','equivalent_alternative_retained',out_id=out['id'])
    projected.sort(key=lambda r:(r['created_utc'] or '',r['id']))
    snapshot={'schema_version':'1.0.0','account_id':account_id,'source_category':category,'capture_utc':None,
        'text_format':'plain','default_language':'und','source_notes':'AHIF 0.1.1 metadata-only Reddit export projection 1.0.0. See private projection receipt.',
        'license_notes':None,'coverage':{'status':'sampled','start_utc':None,'end_utc':None,'known_gaps':[],
        'notes':'Deliberate metadata-only projection of supplied rows; completeness, temporal scope and undocumented gaps remain unknown.'}}
    identity={'profile_sha256':PROFILE_SHA,'selection':selection,'records':projected,'snapshot_without_id':snapshot}
    snapshot['snapshot_id']='ahas-p:'+sha(b'AHIF:projection:1.0.0\n'+C(identity))
    (stage/'records.jsonl').write_bytes(b''.join(C(r)+b'\n' for r in projected))
    write_json(stage/'snapshot.json',snapshot)
    config,loader,thaw,engine_info=engine()
    loaded=loader(stage/'records.jsonl',stage/'snapshot.json',config)
    engine_info.update(canonical_snapshot_sha256=loaded.canonical_sha256,loader_warnings=thaw(loaded.warnings))
    counts=Counter(d['decision'] for d in decisions.values())
    payload={'ahif_version':'0.1.1','source_profile':{'id':'reddit-export-csv','version':'1.0.0','sha256':SOURCE_SHA},
        'projection_profile':{'id':'ahas-conservative','version':'1.0.0','sha256':PROFILE_SHA},'selection':selection,
        'input':{'canonical_manifest_sha256':sha(C(manifest)),
            'manifest_bytes':file_info(Path(bundle)/'manifest.json'),
            'files':[file_info(Path(bundle)/f['path'],f['path']) for f in sorted(manifest['files'],key=lambda f:f['path'])],
            'sources':manifest['sources']},
        'decisions':sorted(decisions.values(),key=lambda d:d['observation_id']), 'aliases':sorted(aliases.values(),key=lambda a:a['alias']),
        'counts':{'record_observations':len(records),'account_observations':len(accounts),'logical_record_keys':len({C(r['record_key']) for r in records}),
            'selected_records':len(projected),'excluded_observations':counts['excluded'],'quarantined_observations':counts['quarantined']},
        'snapshot_fields':[field('ahas.'+f,'constant' if f not in {'snapshot_id','account_id','source_category'} else 'mapped',
            {'capture_utc':'no_common_source_as_of; no_acquisition_substitution','license_notes':'unknown; no_permission_inferred',
             'coverage':'deliberate_selection; all_original_scope_endpoints_gaps_and_claims_bound_by_manifest',
             'text_format':'no_retained_text; no_markup_relabeling','default_language':'unknown_stays_und'}.get(f,'versioned_projection_rule')) for f in sorted(snapshot)],
        'outputs':[file_info(stage/'records.jsonl'),file_info(stage/'snapshot.json')],
        'expanded_records':thaw(loaded.records),'expanded_snapshot':thaw(loaded.manifest),'ahas':engine_info}
    return payload

def validate_receipt(receipt):
    ahif.check_values(receipt)
    Draft202012Validator(SCHEMA).validate(receipt)
    if receipt['payload_sha256']!=sha(b'AHIF:projection-receipt:1.0.0\n'+C(receipt['payload'])):raise ValueError('receipt_payload_digest_mismatch')
    p=receipt['payload'];d=p['decisions'];counts=p['counts']
    if len({x['observation_id'] for x in d})!=len(d):raise ValueError('receipt_duplicate_observation')
    selected=[x for x in d if x['decision']=='selected']
    if len({C(x['key']) for x in selected})!=len(selected):raise ValueError('receipt_duplicate_event_selection')
    if len(d)!=counts['record_observations']+counts['account_observations'] or len(selected)!=counts['selected_records']:raise ValueError('receipt_count_mismatch')
    if len(selected)!=len(p['expanded_records']):raise ValueError('receipt_output_count_mismatch')
    return receipt

def project(bundle,destination,selection,*,executed_at=None):
    with new_destination(destination) as stage:
        payload=prepare(bundle,selection,stage)
        receipt={'receipt_version':'1.0.0','payload':payload,
            'payload_sha256':sha(b'AHIF:projection-receipt:1.0.0\n'+C(payload)),
            'operational':{'executed_at':executed_at or datetime.now(timezone.utc).isoformat(),
                'bundle_path':str(Path(bundle).absolute()),'output_path':str(Path(destination).absolute())}}
        validate_receipt(receipt)
        write_json(stage/'projection-receipt.json',receipt)
    return receipt

def verify_projection(bundle,output):
    output=Path(output)
    receipt=validate_receipt(load((output/'projection-receipt.json').read_bytes()))
    with TemporaryDirectory() as temp:
        replay=prepare(bundle,receipt['payload']['selection'],Path(temp))
        if replay!=receipt['payload']:raise ValueError('projection_replay_mismatch')
    for f in replay['outputs']:
        if file_info(output/f['path'])!=f:raise ValueError('projection_output_digest_mismatch')
    return {'status':'passed','payload_sha256':receipt['payload_sha256'],'canonical_snapshot_sha256':replay['ahas']['canonical_snapshot_sha256']}
