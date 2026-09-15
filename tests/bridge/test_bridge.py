from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import shutil
import zipfile
import pytest
from bridge.common import C, ahif, file_info, load, read_bundle, sha, write_bundle, write_json
from bridge.reddit import EXT, PROFILE, make_observations, normalize, parse_members, parse_time, read_members, verify_fidelity
from bridge.projection import alias, engine, project, selection_for, validate_receipt, verify_projection

FIX=Path(__file__).parent/'fixtures'
EXPECTED=json.loads((FIX/'expected.json').read_text())

@pytest.fixture
def normalized(tmp_path):
    out=tmp_path/'bundle'
    result=normalize(FIX/'tiny',out,subject='export_subject',category='synthetic')
    return out,result

def rewrite(bundle,records,manifest=None,accounts=()):
    if manifest is None:manifest=load((bundle/'manifest.json').read_bytes())
    write_bundle(bundle,manifest,records,accounts)

def run_projection(bundle,tmp_path,name='projection'):
    m,*_=read_bundle(bundle)
    return project(bundle,tmp_path/name,selection_for(m['sources'][0]['source_id']))

def test_literal_fidelity_and_source_semantics(normalized):
    bundle,result=normalized
    m,rows,_,check=read_bundle(bundle)
    by_id={r['record_key']['id']:r for r in rows}
    assert len(rows)==EXPECTED['record_observations']
    assert check['distinct_record_keys']==EXPECTED['logical_keys']
    raw=list(csv.DictReader((FIX/'tiny/comments.csv').open(newline='')))
    assert by_id[raw[0]['id']]['content']['parts'][0]['text']==raw[0]['body']
    assert '\r\n' in raw[0]['body'] and 'e\u0301' in raw[0]['body'] and '```py' in raw[0]['body']
    assert by_id[raw[0]['id']]['created_at']['value']==EXPECTED['created_known']
    assert by_id['b3']['created_at']['status']=='date_only'
    assert by_id['b3']['created_at']['value']==EXPECTED['coarse_date']
    assert by_id['b4']['created_at']['status']=='unknown'
    assert by_id['b4']['created_at']['raw']==EXPECTED['unsupported_offset_raw']
    assert by_id['b7']['content']['parts'][0]['text']==' [removed] '
    assert by_id['b2']['relations'][0]['target_key']['id']=='absent1'
    assert all(r['lifecycle']['edit_state']=='unknown' for r in rows)
    assert all(p['language']=={'tag':'und','basis':'unknown'} for r in rows for p in r['content']['parts'])
    assert len(result['fidelity']['fields'])==13
    assert all(a['included_path'] is None for a in m['sources'][0]['artifacts'])
    assert {p.name for p in bundle.iterdir()}=={'manifest.json','records.jsonl'}
    assert all('ip' not in r for records in parse_members(read_members(FIX/'tiny')).values() for r in records)

def test_real_loader_receipt_and_exclusions(normalized,tmp_path):
    bundle,_=normalized;r=run_projection(bundle,tmp_path);p=r['payload']
    ids={d['key']['id'] for d in p['decisions'] if d['decision']=='selected'}
    assert ids==set(EXPECTED['selected_native_ids'])
    assert {d['key']['id'] for d in p['decisions'] if d['decision']=='quarantined'}==set(EXPECTED['quarantined_native_ids'])
    assert p['counts']['selected_records']==4
    assert all(x['language']=='und' and x['text'] is None and x['title'] is None for x in p['expanded_records'])
    assert p['expanded_snapshot']['coverage']['status']=='sampled'
    assert p['expanded_snapshot']['capture_utc'] is None
    assert p['ahas']['version']=='1.0.4'
    assert verify_projection(bundle,tmp_path/'projection')['status']=='passed'
    selected=next(d for d in p['decisions'] if d['key']['id']=='b3')
    assert any(f['reason']=='coarse_time_omitted' for f in selected['fields'])

def test_relocation_key_order_clock_reproducibility(normalized,tmp_path):
    bundle,result=normalized
    first=run_projection(bundle,tmp_path,'first')
    other=tmp_path/'other';normalize(FIX/'tiny',other,subject='export_subject',category='synthetic')
    assert (bundle/'manifest.json').read_bytes()==(other/'manifest.json').read_bytes()
    assert (bundle/'records.jsonl').read_bytes()==(other/'records.jsonl').read_bytes()
    # JSON key order/whitespace may change physical evidence bytes, not AHAS identity.
    m=load((other/'manifest.json').read_bytes())
    (other/'manifest.json').write_text(json.dumps(m,indent=3))
    selection=selection_for(result['source_id']);selection=dict(reversed(list(selection.items())))
    second=project(other,tmp_path/'second',selection,executed_at='different operational clock')
    assert first['payload']['ahas']['canonical_snapshot_sha256']==second['payload']['ahas']['canonical_snapshot_sha256']
    assert first['payload']['input']['manifest_bytes']!=second['payload']['input']['manifest_bytes']
    clock_only=project(bundle,tmp_path/'clock',selection,executed_at='changed clock only')
    assert clock_only['payload_sha256']==first['payload_sha256']
    assert first['operational']!=second['operational']
    for name in ['records.jsonl','snapshot.json']:
        assert (tmp_path/'first'/name).read_bytes()==(tmp_path/'second'/name).read_bytes()

def test_repeat_and_conflict_no_text_dedup(normalized,tmp_path):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle)
    target=next(r for r in rows if r['record_key']['id']=='b2')
    duplicate=deepcopy(target);duplicate['observed_at']={'status':'known','value':'2026-03-01T00:00:00Z','precision':'second','basis':'source'}
    duplicate['observation_id']=ahif.bound_id('record',duplicate);rows.append(duplicate)
    rewrite(bundle,rows,m)
    p=run_projection(bundle,tmp_path)['payload']
    assert p['counts']['record_observations']==11 and p['counts']['logical_record_keys']==10
    assert p['counts']['selected_records']==4
    assert any(d['reason']=='equivalent_alternative_retained' for d in p['decisions'])
    # Matching wording at different native IDs still gives two distinct decisions.
    assert len([d for d in p['decisions'] if d['key']['id'] in ['b5','b6']])==2
    duplicate['created_at']=parse_time('2026-02-05 04:05:06 UTC');duplicate['observation_id']=ahif.bound_id('record',duplicate)
    rewrite(bundle,rows,m)
    p=run_projection(bundle,tmp_path,'conflict')['payload']
    assert p['counts']['selected_records']==3
    assert sum(d['reason']=='unresolved_observation_conflict' for d in p['decisions'])==2

def test_duplicate_csv_rows_are_observations(tmp_path):
    members=read_members(FIX/'tiny')
    lines=list(csv.reader(io.StringIO(members['comments.csv'].decode(),newline='')))
    lines.append(lines[2]);s=io.StringIO(newline='');csv.writer(s).writerows(lines);members['comments.csv']=s.getvalue().encode()
    m,rows=make_observations(members,'export_subject','synthetic');out=tmp_path/'bundle';out.mkdir();write_bundle(out,m,rows)
    p=run_projection(out,tmp_path)['payload']
    assert p['counts']['record_observations']==11 and p['counts']['selected_records']==4
    assert sum(d['reason']=='equivalent_alternative_retained' for d in p['decisions'])==1

def test_unknown_actor_preserved_and_excluded(normalized,tmp_path):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle)
    r=next(r for r in rows if r['record_key']['id']=='b2');r['actor']=None;r['observation_id']=ahif.bound_id('record',r)
    rewrite(bundle,rows,m);p=run_projection(bundle,tmp_path)['payload']
    assert any(d['reason']=='actor_unknown' for d in p['decisions'])
    anonymous=tmp_path/'anonymous';normalize(FIX/'tiny',anonymous,subject='unknown',category='synthetic')
    assert all(r['actor'] is None for r in read_bundle(anonymous)[1])
    with pytest.raises(ValueError,match='subject_unsupported'):run_projection(anonymous,tmp_path,'no-subject')

def test_no_handle_or_cross_capture_continuity(normalized,tmp_path):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle)
    r=next(r for r in rows if r['record_key']['id']=='b2');r['actor']={'namespace':'urn:ahif:service:reddit','collection':'accounts','id_type':'handle','id':'fictional'}
    r['observation_id']=ahif.bound_id('record',r);rewrite(bundle,rows,m)
    p=run_projection(bundle,tmp_path)['payload']
    assert any('identity_continuity_unestablished' in d['reason'] for d in p['decisions'])
    old=m['sources'][0];new=deepcopy(old);new['description']+=' Different capture.';new['source_id']=ahif.bound_id('source',new)
    r=deepcopy(next(r for r in rows if r['record_key']['id']=='b3'));r['source_id']=new['source_id'];r['actor']['id']=new['source_id']+'#export-subject';r['observation_id']=ahif.bound_id('record',r)
    m['sources'].append(new);cov=deepcopy(m['coverage'][0]);cov['source_id']=new['source_id'];cov['account_key']=r['actor'];m['coverage'].append(cov);rows.append(r);rewrite(bundle,rows,m)
    p=project(bundle,tmp_path/'cross',selection_for(old['source_id']))['payload']
    assert any(d['reason'].startswith('outside_selected_source') for d in p['decisions'])

def test_namespace_and_collection_aliases():
    k={'namespace':'https://one.example','collection':'posts','id_type':'native','id':'900719925474099312345'}
    assert alias('record',k)!=alias('record',{**k,'namespace':'https://two.example'})
    assert alias('record',k)!=alias('record',{**k,'collection':'comments'})

@pytest.mark.parametrize('change,reason',[
    ('visible','text_projection_unsupported'),('html','lifecycle_content_unrepresentable'),
    ('bbcode','lifecycle_content_unrepresentable'),('quote','lifecycle_content_unrepresentable'),
    ('signature','lifecycle_content_unrepresentable'),('partial','lifecycle_content_unrepresentable'),
    ('redacted','lifecycle_content_unrepresentable'),('repost','kind_unsupported')])
def test_unsupported_text_is_quarantined(normalized,tmp_path,change,reason):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle);r=next(r for r in rows if r['record_key']['id']=='b5')
    if change=='visible':r['lifecycle']['state']='visible';r['content']['completeness']='complete'
    elif change in ['html','bbcode']:r['content']['parts'][0]['format']=change
    elif change in ['quote','signature']:
        r['content']['parts'][0]['role']=change;r['content']['parts'][0]['attribution']['relation']='unknown'
    elif change=='partial':r['content']['completeness']='partial'
    elif change=='redacted':r['content'].update(availability='redacted',completeness='partial',reason='fixture_withheld')
    elif change=='repost':
        r['kind']='repost';r['content']={'availability':'empty','completeness':'complete','reason':None,'parts':[]}
    r['observation_id']=ahif.bound_id('record',r);rewrite(bundle,rows,m)
    p=run_projection(bundle,tmp_path)['payload']
    assert next(d['reason'] for d in p['decisions'] if d['key']['id']=='b5')==reason

def test_native_link_not_invented_prose(normalized,tmp_path):
    p=run_projection(normalized[0],tmp_path)['payload']
    r=next(r for r in p['expanded_records'] if r['id']==alias('record',{'namespace':'urn:ahif:service:reddit','collection':'posts','id_type':'native','id':'p3'}))
    assert r['text'] is None
    d=next(d for d in p['decisions'] if d['key']['id']=='p3')
    assert any(f['field']=='ahif.links' and f['disposition']=='receipt_only' for f in d['fields'])

@pytest.mark.parametrize('raw',['2026-02-30 00:00:00 UTC','2026-01-01 00:00 UTC','2026-01-01T00:00:00.000000001Z','yesterday'])
def test_bad_or_unsupported_time(raw,status=None):
    assert parse_time(raw)=={'status':'unknown','reason':'unrecognized_or_absent_export_date','raw':raw}

def test_precision_refusal_and_loader_chronology(normalized,tmp_path):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle);r=next(r for r in rows if r['record_key']['id']=='b2')
    r['created_at']={'status':'known','value':'2026-01-01T00:00:00.000000001Z','precision':'nanosecond','basis':'source'};r['observation_id']=ahif.bound_id('record',r);rewrite(bundle,rows,m)
    p=run_projection(bundle,tmp_path)['payload'];assert any(d['reason']=='timestamp_precision_unsupported' for d in p['decisions'])
    r['created_at']=parse_time('2026-02-03 04:05:06 UTC');r['updated_at']=parse_time('2026-02-01 00:00:00 UTC');r['lifecycle']['edit_state']='edited';r['observation_id']=ahif.bound_id('record',r);rewrite(bundle,rows,m)
    with pytest.raises(Exception):run_projection(bundle,tmp_path,'chronology')
    assert not (tmp_path/'chronology').exists()

@pytest.mark.parametrize('case',['header','width','utf8','bom','id','duplicate_member','oversize'])
def test_invalid_source_fails_atomically(tmp_path,case):
    members=read_members(FIX/'tiny')
    if case=='header':members['comments.csv']=members['comments.csv'].replace(b'permalink',b'permaLINK',1)
    if case=='width':members['comments.csv']+=b'one,two\n'
    if case=='utf8':members['comments.csv']+=b'\xff'
    if case=='bom':members['comments.csv']=b'\xef\xbb\xbf'+members['comments.csv']
    if case=='id':members['comments.csv']=members['comments.csv'].replace(b'900719925474099312345,',b'Bad-ID,',1)
    if case=='oversize':members['comments.csv']=b'X'*(PROFILE['limits']['member_bytes']+1)
    archive=tmp_path/'input.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for name,data in members.items():z.writestr(name,data)
        if case=='duplicate_member':
            with pytest.warns(UserWarning,match='Duplicate name'):z.writestr('comments.csv',members['comments.csv'])
        z.writestr('private_messages.csv',b'not valid csv and must never be parsed')
    with pytest.raises(Exception):normalize(archive,tmp_path/'bad',subject='export_subject')
    assert not (tmp_path/'bad').exists()

def test_archive_scope_and_symlink(tmp_path):
    archive=tmp_path/'input.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for name,data in read_members(FIX/'tiny').items():z.writestr(name,data)
        z.writestr('../credentials',b'never opened or extracted')
    result=normalize(archive,tmp_path/'ok',subject='export_subject',category='synthetic')
    assert result['check']['record_observations']==10
    assert not (tmp_path/'credentials').exists()
    (tmp_path/'link').symlink_to(archive)
    with pytest.raises(ValueError,match='symlink'):read_members(tmp_path/'link')

def test_fidelity_and_receipt_tamper_detected(normalized,tmp_path):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle)
    r=next(r for r in rows if r['record_key']['id']=='b5');r['content']['parts'][0]['text']='silently rewritten';r['observation_id']=ahif.bound_id('record',r);rewrite(bundle,rows,m)
    with pytest.raises(ValueError,match='text_mismatch'):verify_fidelity(FIX/'tiny',bundle)
    receipt=run_projection(bundle,tmp_path)
    receipt['payload']['counts']['selected_records']=99
    with pytest.raises(ValueError,match='digest'):validate_receipt(receipt)
    receipt['payload_sha256']=sha(b'AHIF:projection-receipt:1.0.0\n'+C(receipt['payload']))
    with pytest.raises(ValueError,match='count'):validate_receipt(receipt)
    (tmp_path/'projection/records.jsonl').write_text('')
    with pytest.raises(ValueError,match='output_digest'):verify_projection(bundle,tmp_path/'projection')

def test_existing_output_untouched(normalized,tmp_path):
    bundle,_=normalized;before={p.name:p.read_bytes() for p in bundle.iterdir()}
    with pytest.raises(ValueError,match='output_exists'):normalize(FIX/'tiny',bundle,subject='export_subject')
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}

def test_competing_actor_claim_quarantines_key(normalized,tmp_path):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle)
    r=deepcopy(next(r for r in rows if r['record_key']['id']=='b2'));r['actor']=None;r['observation_id']=ahif.bound_id('record',r);rows.append(r);rewrite(bundle,rows,m)
    p=run_projection(bundle,tmp_path)['payload']
    assert sum(d['reason']=='unresolved_observation_conflict' for d in p['decisions'])==2
    assert p['counts']['selected_records']==3

def test_unresolved_thread_does_not_invent_parent_collection(tmp_path):
    members=read_members(FIX/'tiny');raw=parse_members(members)['comments.csv'][1]
    from bridge.reddit import thread_key
    raw['link']='https://www.reddit.com/r/fictional/comments/other/fictional/'
    assert thread_key(raw,'comments') is None

def test_account_observation_excluded(normalized,tmp_path):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle);r=rows[0]
    account={'format_version':'0.1.1','account_key':r['actor'],'source_id':r['source_id'],'observed_at':r['observed_at'],
        'aliases':[],'provenance':r['provenance']};account['observation_id']=ahif.bound_id('account',account)
    rewrite(bundle,rows,m,[account]);p=run_projection(bundle,tmp_path)['payload']
    assert p['counts']['account_observations']==1
    assert p['counts']['selected_records']==4
    assert any(d['reason']=='account_profile_not_a_posting_event' for d in p['decisions'])

def test_receipt_schema_and_selection_reject_unknown_core_fields(normalized,tmp_path):
    bundle,_=normalized;m,*_=read_bundle(bundle);s=selection_for(m['sources'][0]['source_id']);s['allow_text']=True
    with pytest.raises(ValueError,match='selection_contract'):project(bundle,tmp_path/'bad-selection',s)
    r=run_projection(bundle,tmp_path);r['unexpected']=True
    with pytest.raises(Exception):validate_receipt(r)

def test_observed_short_native_thread_link(normalized):
    from bridge.reddit import thread_key
    row=parse_members(read_members(FIX/'tiny'))['comments.csv'][1]
    row['link']='https://www.reddit.com/r/fictional/comments/p1'
    assert thread_key(row,'comments')=={'namespace':'urn:ahif:service:reddit','collection':'posts','id_type':'native','id':'p1'}

def test_ahas_does_not_accept_ahif_directly(normalized,tmp_path):
    from account_history_analyzer.io import load_snapshot
    bundle,_=normalized;run_projection(bundle,tmp_path)
    with pytest.raises(Exception):load_snapshot(bundle/'records.jsonl',tmp_path/'projection/snapshot.json')


def test_fidelity_checks_every_normalized_part(normalized):
    bundle,_=normalized;m,rows,_,_=read_bundle(bundle)
    r=next(r for r in rows if r['record_key']['id']=='b5')
    extra=deepcopy(r['content']['parts'][0]);extra.update(part_id='invented',role='quote',text='Never supplied by CSV')
    extra['attribution']['relation']='unknown';r['content']['parts'].append(extra)
    r['observation_id']=ahif.bound_id('record',r);rewrite(bundle,rows,m)
    with pytest.raises(ValueError,match='unexpected_text_part'):verify_fidelity(FIX/'tiny',bundle)
