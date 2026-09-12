#!/usr/bin/env python3
"""Exercise the real production gateway in a child process, then restart it.

No model download or case data is used. All mutable paths must live in repo/dist.
Use --installed with an installed wheel interpreter; -I and an empty PYTHONPATH
prevent the qualification from accidentally exercising the source checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
OPENER = build_opener(ProxyHandler({}))
HEADERS = {"X-User-Role":"reviewer", "X-Tenant-Id":"synthetic-pass08"}
AS_OF = "2026-09-11"


def request(origin, path, *, payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode()
    request_headers = {**HEADERS, "Origin":origin, **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    req = Request(origin+path, data=body, headers=request_headers)
    try:
        response = OPENER.open(req, timeout=15)
    except HTTPError as exc:
        response = exc
    with response:
        raw=response.read()
        return response.status, dict(response.headers), raw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--work-dir', default=str(ROOT/'dist/pass08-source-e2e'))
    parser.add_argument('--output', default=str(ROOT/'artifacts/pass-08/source-e2e.json'))
    args=parser.parse_args()
    work=Path(args.work_dir).resolve()
    if not work.is_relative_to((ROOT/'dist').resolve()) or work == (ROOT/'dist').resolve():
        raise SystemExit('work-dir must be a dedicated directory under repository/dist')
    work.mkdir(parents=True,exist_ok=True)
    output=Path(args.output).resolve()
    if not output.is_relative_to(ROOT): raise SystemExit('output must stay inside this repository')
    env=os.environ.copy()
    for name in ('PYTHONPATH','PYTHONHOME','NHFL_AUTHORITY_MANIFEST'):
        env.pop(name,None)
    for name in ('HOME','USERPROFILE','LOCALAPPDATA','XDG_CACHE_HOME','XDG_CONFIG_HOME','TMP','TEMP','TMPDIR'):
        dest=work/name.lower();dest.mkdir(exist_ok=True);env[name]=str(dest)
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['NHFL_PROJECT_ROOT']=str(work/'empty-project') if args.installed else str(ROOT)
    env['NHFL_RUNTIME_MODE']='source'
    records=[];launches=[];errors=[];browser_record={'status':'not_run'}
    source_prefix='' if args.installed else f'import sys; sys.path.insert(0,{str(ROOT)!r}); sys.path.insert(0,{str(ROOT / "src")!r}); '
    probe=source_prefix+'''import json, nh_family_law_llm; from nh_family_law_llm.authority_snapshot import default_manifest_path; from nh_family_law_llm.version import VERSION; print(json.dumps({'module':nh_family_law_llm.__file__,'manifest':str(default_manifest_path()),'version':VERSION}))'''
    import_probe=subprocess.run([args.python,'-I','-c',probe],cwd=work,env=env,capture_output=True,text=True,timeout=15)
    if import_probe.returncode: raise RuntimeError('Import probe failed: '+import_probe.stderr)
    probe_result=json.loads(import_probe.stdout.strip())
    if args.installed:
        assert 'site-packages' in probe_result['module'], probe_result
        assert 'data/authority_snapshot/manifest' in Path(probe_result['manifest']).as_posix(), probe_result
    expected_version=probe_result['version']
    for cycle in range(2):
        log=work/f'service-{cycle}.log'
        code=source_prefix+f'from nh_family_law_llm.cli import main; raise SystemExit(main(["desktop","--port","0","--data-root",{str(work / "runtime")!r}]))'
        start=time.monotonic()
        with log.open('w') as stream:
            process=subprocess.Popen([args.python,'-I','-u','-c',code],cwd=work,env=env,stdout=stream,stderr=stream)
            try:
                launch=None
                for _ in range(150):
                    for line in log.read_text(errors='replace').splitlines():
                        if line.startswith('{'):
                            try:
                                value=json.loads(line)
                                if value.get('event')=='nhfl_starting':launch=value
                            except json.JSONDecodeError: pass
                    if launch:break
                    if process.poll() is not None:raise RuntimeError('Startup process exited: '+log.read_text()[-3000:])
                    time.sleep(.1)
                if not launch:raise TimeoutError('No startup handshake')
                assert launch['version']==expected_version
                origin=f'http://127.0.0.1:{launch["port"]}'
                for _ in range(200):
                    try:
                        status,health_headers,_=request(origin,'/api/health')
                        if status==200:break
                    except (URLError, TimeoutError, OSError):pass
                    if process.poll() is not None:raise RuntimeError('Production server exited: '+log.read_text()[-3000:])
                    time.sleep(.1)
                else:raise TimeoutError('Health deadline exceeded')
                observed={k.lower():v for k,v in health_headers.items()}
                assert observed.get('x-nhfl-service-instance')==launch['instance_id'],observed
                # The CLI may be launched through a Python wrapper on Windows.
                # Bind the health response to the desktop service PID emitted
                # by its startup handshake, not to that wrapper's PID.
                assert int(observed.get('x-nhfl-service-pid','0'))==launch['pid']
                launches.append({'cycle':cycle,'instance_id':launch['instance_id'],'pid':process.pid,'startup_seconds':round(time.monotonic()-start,3)})
                paths=['/', '/nh-review','/api/runtime/ui-manifest','/api/runtime/release-scope','/ui-assets/nh-review.js','/ui-assets/nh-review.css','/ui-assets/brand/nh-banner.png','/brand-assets/assets/favicon/favicon.svg',f'/api/nh-review/status?as_of_date={AS_OF}']
                for path in paths:
                    status,resp_headers,raw=request(origin,path)
                    assert status==200,(path,status,raw[:300])
                    if path == '/api/runtime/release-scope':
                        ledger=json.loads(raw)
                        assert ledger['store_feature_claim_eligible'] is False
                        assert ledger['release']['product_version']==expected_version
                        assert 'capability_78_nh_review_desk' in ledger['legacy_reachable_feature_ids']
                    if path == '/api/runtime/ui-manifest':
                        ui=json.loads(raw)
                        assert ui['status']=='pass' and ui['asset_count']==9
                    records.append({'cycle':cycle,'path':path,'status':status,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
                payload={'question':'Review a possible parenting-plan modification and child-support order','as_of_date':AS_OF,'parenting':{'permanent_order':True}}
                status,_,raw=request(origin,'/api/legal-behavior/analyze',payload=payload)
                assert status==200,raw
                result=json.loads(raw)
                assert result['review_required'] is True and result['filing_ready'] is False and result['legal_advice'] is False
                ref=next(item for item in result['authority_references'] if item['retrieval_eligible'])
                status,_,raw=request(origin,f'/api/nh-review/sources/{ref["authority_id"]}?as_of_date={AS_OF}')
                assert status==200
                capsule=json.loads(raw)
                assert hashlib.sha256(capsule['text'].encode()).hexdigest()==capsule['sha256']
                assert capsule['safe_for_direct_quote'] is False
                assert request(origin,'/api/legal-behavior/analyze',payload={'question':'x'},headers={'Origin':'https://other.example'})[0]==403
                assert request(origin,'/api/legal-behavior/analyze',payload={'parenting':[]})[0]==422
                records.append({'cycle':cycle,'check':'analysis_source_hash_origin_and_invalid_input','status':'pass'})
                if args.browser and cycle==0:
                    browser_record=run_browser(origin,work,output.parent)
            except Exception as exc:
                # Qualification failures must identify the failed acceptance
                # assertion.  Bare AssertionError text otherwise turns a
                # reproducible desktop regression into an unactionable gate.
                errors.append(traceback.format_exc().strip())
                break
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        if process.poll() is None:errors.append('Owned child process did not stop')
    if len(launches)!=2:errors.append('Restart journey not completed')
    elif launches[0]['instance_id']==launches[1]['instance_id']:errors.append('Restart reused its service instance nonce')
    report={'schema':'nhfl.pass08.desktop-qualification.v1','status':'pass' if not errors else 'fail','version':expected_version,'mode':'installed_wheel' if args.installed else 'source','import_probe':probe_result,'launches':launches,'checks':records,'browser':browser_record,'errors':errors,'uses_synthetic_input_only':True,'windows_binary_qualification':False}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'mode':report['mode'],'checks':len(records),'launches':len(launches),'browser':browser_record.get('status'),'errors':errors},indent=2))
    return 0 if not errors else 1


def run_browser(origin,work,evidence):
    from playwright.sync_api import sync_playwright
    errors=[];off_origin=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
        try:
            context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
            page=context.new_page()
            page.on('pageerror',lambda exc:errors.append(str(exc)))
            page.on('request',lambda req: off_origin.append(req.url) if not req.url.startswith(origin+'/') else None)
            page.goto(origin+'/nh-review',wait_until='networkidle')
            page.locator('#as-of').fill(AS_OF)
            page.locator('#as-of').dispatch_event('change')
            page.locator('#question').fill('Review my child-support order and parenting-plan modification. What evidence is missing?')
            page.locator('details > summary').click()
            page.locator('#facts').fill('{"parenting":{"permanent_order":true}}')
            page.locator('#analyze').click()
            # Locator waits do not inject a string-evaluated predicate, which
            # would be blocked by the production CSP during a real browser run.
            page.locator('#export:not([disabled])').wait_for()
            assert page.locator('#results').inner_text().find('human review')>=0 or page.locator('#results').inner_text().find('blocked')>=0
            evidence.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(evidence/'browser-desktop.png'))
            with page.expect_download() as event:page.locator('#export').click()
            download=event.value;target=work/'synthetic-review-export.json';download.save_as(target)
            exported=json.loads(target.read_text())
            assert exported['metadata']['jurisdiction']=='NH' and exported['metadata']['filing_ready'] is False
            # Preserve the browser's compact serialization, rather than reordering JSON keys.
            assert page.evaluate('async () => { const a = document.querySelectorAll("#results .source button"); return a.length; }')>0
            page.locator('#results .source button:enabled').first.click()
            page.locator('#source-text:not(:empty)').wait_for()
            assert 'not the official statute text' in page.locator('#source-notice').inner_text()
            page.locator('#close-source').click()
            page.locator('#question').fill('Changed input')
            assert page.locator('#export').is_disabled()
            page.locator('details').evaluate('(node) => node.open = true')
            page.locator('#facts').fill('[]')
            page.locator('#analyze').click()
            assert page.locator('#error').is_visible() and page.locator('#export').is_disabled()
            page.locator('#clear').click()
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(evidence/'browser-mobile.png'),full_page=False)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
            page.reload(wait_until='networkidle')
            assert page.locator('#question').input_value()=='' and page.locator('#export').is_disabled()
            assert not errors,errors
            assert not off_origin,off_origin
            return {'status':'pass','engine':'Chromium','desktop_viewport':[1440,1000],'mobile_viewport':[390,844],'page_errors':errors,'off_origin_requests':off_origin,'export_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'export_bytes':target.stat().st_size,'export_invalidates_after_input_change':True,'source_drilldown':True,'reload_clears_review':True,'horizontal_mobile_overflow':False}
        finally:browser.close()


if __name__=='__main__':raise SystemExit(main())
