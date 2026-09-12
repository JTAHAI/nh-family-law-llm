#!/usr/bin/env python3
"""Download allowlisted official NH sources into PENDING_REVIEW and update provenance."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/nh_authority_sources.json'
MANIFEST=ROOT/'corpus/manifest/nh_authorities.json'

def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')[:90]
def allowed(host, domains): return any(host==d or host.endswith('.'+d) for d in domains)

def fetch(item,cfg,timeout,max_bytes):
    url=item['source_url']; host=(urlparse(url).hostname or '').lower()
    if not allowed(host,set(cfg['official_domain_allowlist'])): return item['authority_id'],None,f'domain not allowlisted: {host}'
    try:
        req=Request(url,headers={'User-Agent':cfg['user_agent'],'Accept':'text/html,application/pdf,text/plain,*/*;q=.5'})
        with urlopen(req,timeout=timeout) as r:
            body=r.read(max_bytes+1); final=r.geturl(); ctype=r.headers.get('Content-Type','')
        if len(body)>max_bytes: raise RuntimeError(f'response exceeds {max_bytes} bytes')
        if not body: raise RuntimeError('empty response')
        ext='.pdf' if ('pdf' in ctype.lower() or final.lower().split('?')[0].endswith('.pdf')) else '.html'
        return item['authority_id'],{'body':body,'final_url':final,'content_type':ctype,'ext':ext},None
    except Exception as e: return item['authority_id'],None,f'{type(e).__name__}: {e}'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--download',action='store_true'); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--only'); ap.add_argument('--timeout',type=int,default=30); ap.add_argument('--workers',type=int,default=6); ap.add_argument('--max-bytes',type=int,default=30_000_000); args=ap.parse_args()
    cfg=json.loads(CONFIG.read_text(encoding='utf-8')); payload=json.loads(MANIFEST.read_text(encoding='utf-8')); items=payload['authorities']
    if args.only: items=[a for a in items if args.only.lower() in f"{a.get('authority_id')} {a.get('citation')} {a.get('title')}".lower()]
    dest=ROOT/cfg['pending_directory']; dest.mkdir(parents=True,exist_ok=True)
    if args.dry_run or not args.download:
        for a in items: print(f"QUEUE {a['authority_id']} {a['citation']}: {a['source_url']}")
        return 0
    successes={}; failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futures=[ex.submit(fetch,a,cfg,args.timeout,args.max_bytes) for a in items]
        for f in concurrent.futures.as_completed(futures):
            aid,result,error=f.result()
            if error: failures.append({'authority_id':aid,'error':error}); continue
            a=next(x for x in items if x['authority_id']==aid)
            fn=f"{aid}--{slug(a['citation'])}{result['ext']}"; path=dest/fn; path.write_bytes(result['body'])
            successes[aid]={
                'source_url':result['final_url'],'local_filename':str(path.relative_to(ROOT)).replace('\\','/'),
                'retrieval_date':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(result['body']).hexdigest(),
                'content_type':result['content_type'],'status':'acquired_pending_effective_date_review','retrieval_eligible':False,
            }
    for a in payload['authorities']:
        if a['authority_id'] in successes: a.update(successes[a['authority_id']])
    payload['generated_at']=datetime.now(timezone.utc).isoformat(); MANIFEST.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    logdir=ROOT/'corpus/acquisition_logs'; logdir.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (logdir/f'acquisition-{stamp}.json').write_text(json.dumps({'successes':successes,'failures':failures},indent=2),encoding='utf-8')
    print(json.dumps({'downloaded':len(successes),'failed':len(failures),'failures':failures},indent=2))
    return 0 if successes else 1
if __name__=='__main__': raise SystemExit(main())
