#!/usr/bin/env python3
"""Promote a reviewed NH source snapshot from PENDING_REVIEW to CURRENT_AUTHORITY."""
from __future__ import annotations
import argparse, hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; MANIFEST=ROOT/'corpus/manifest/nh_authorities.json'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('authority_id'); ap.add_argument('--effective-date',required=True); ap.add_argument('--amendment-date'); ap.add_argument('--reviewer',required=True); ap.add_argument('--notes',required=True); args=ap.parse_args()
    p=json.loads(MANIFEST.read_text(encoding='utf-8')); a=next((x for x in p['authorities'] if x['authority_id']==args.authority_id),None)
    if not a: raise SystemExit('unknown authority_id')
    if not a.get('local_filename'): raise SystemExit('authority has no acquired snapshot')
    src=ROOT/a['local_filename'];
    if not src.exists(): raise SystemExit('snapshot missing')
    if hashlib.sha256(src.read_bytes()).hexdigest()!=a.get('sha256'): raise SystemExit('checksum mismatch')
    dst=ROOT/'corpus/CURRENT_AUTHORITY'/src.name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.move(src,dst)
    a.update({'local_filename':str(dst.relative_to(ROOT)).replace('\\','/'),'effective_date':args.effective_date,'amendment_date':args.amendment_date,'status':'current_verified','retrieval_eligible':True,'reviewed_by':args.reviewer,'reviewed_at':datetime.now(timezone.utc).isoformat(),'review_notes':args.notes})
    p['generated_at']=datetime.now(timezone.utc).isoformat(); MANIFEST.write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8')
    print(f'promoted {a["authority_id"]} -> {a["local_filename"]}')
if __name__=='__main__': main()
