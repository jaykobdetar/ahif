"""Small offline normalization/projection CLI. Outputs may be private."""
import argparse
import json
import re
from pathlib import Path
from .common import load, new_destination, write_json
from .reddit import normalize, verify_fidelity
from .projection import project, selection_for, verify_projection

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    n=sub.add_parser('normalize');n.add_argument('--source',type=Path,required=True);n.add_argument('--out',type=Path,required=True)
    n.add_argument('--subject',choices=['export_subject','unknown'],required=True)
    n.add_argument('--category',choices=['user_supplied','synthetic'],default='user_supplied')
    n.add_argument('--fidelity-out',type=Path,required=True)
    q=sub.add_parser('project');q.add_argument('--bundle',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
    x=q.add_mutually_exclusive_group(required=True);x.add_argument('--source-id');x.add_argument('--selection',type=Path)
    v=sub.add_parser('verify');v.add_argument('--bundle',type=Path,required=True);v.add_argument('--output',type=Path,required=True)
    f=sub.add_parser('fidelity');f.add_argument('--source',type=Path,required=True);f.add_argument('--bundle',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='normalize':
            if args.fidelity_out.exists() or args.fidelity_out.is_symlink():raise ValueError('fidelity_output_exists')
            if args.fidelity_out.absolute().is_relative_to(args.out.absolute()):raise ValueError('receipt_must_be_outside_bundle')
            result=normalize(args.source,args.out,subject=args.subject,category=args.category)
            # Exclusive create; retain the validated bundle if receipt output fails.
            with args.fidelity_out.open('xb') as out:
                from .common import C
                out.write(C(result['fidelity'])+b'\n')
            summary={'status':'passed','source_id':result['source_id'],'counts':result['check'],'text_fields_checked':len(result['fidelity']['fields'])}
        elif args.command=='project':
            selection=load(args.selection.read_bytes()) if args.selection else selection_for(args.source_id)
            result=project(args.bundle,args.out,selection)
            summary={'status':'passed','counts':result['payload']['counts'],'payload_sha256':result['payload_sha256']}
        elif args.command=='verify':summary=verify_projection(args.bundle,args.output)
        else:
            result=verify_fidelity(args.source,args.bundle);summary={'status':'passed','text_fields_checked':len(result['fields'])}
    except Exception as e:
        # Library exceptions may contain private source text; never echo them.
        code=getattr(e,'code',None)
        if code is None and type(e) is ValueError and re.fullmatch(r'[a-z_]+',str(e)):code=str(e)
        if not isinstance(code,str) or not re.fullmatch(r'[a-z_]+',code):code='validation_failed'
        print(json.dumps({'status':'failed','error_type':type(e).__name__,'error_code':code,'details':'No private exception text emitted.'}))
        return 2
    print(json.dumps(summary,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
