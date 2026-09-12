#!/usr/bin/env python3
"""Offline UI fixtures: not a live-browser, real-court, or full accessibility test.

Inline the actual shipped HTML/CSS/JS and images, then stub fetch with synthetic
responses from the local behavior engine. No HTTP navigation or network service
is used. All writable browser data stays inside repository/dist.
"""
from __future__ import annotations
import argparse
import base64
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', default=shutil.which('chromium'))
    args = parser.parse_args()
    work = ROOT / 'dist/pass08-offline-ui'
    work.mkdir(parents=True, exist_ok=True)
    for key in ('TMPDIR', 'TMP', 'TEMP', 'XDG_CACHE_HOME'):
        path = work / key.lower(); path.mkdir(exist_ok=True); os.environ[key] = str(path)
    output = ROOT / 'artifacts/pass-08/offline-ui.json'
    evidence = output.parent
    evidence.mkdir(parents=True, exist_ok=True)
    from legal.nh_family_law.authorities import AuthorityGate
    from legal.nh_family_law.engine import NewHampshireLegalBehaviorEngine
    from nh_family_law_llm.local_workbench_ui import render_nh_review_html
    from playwright.sync_api import sync_playwright
    gate = AuthorityGate(as_of=date(2026, 9, 11))
    engine = NewHampshireLegalBehaviorEngine()
    # Nothing here describes a real person or proceeding.
    analysis = engine.analyze({'question': 'Review a parenting-plan and child-support modification', 'as_of_date': '2026-09-11', 'parenting': {'permanent_order': True}})
    if hasattr(analysis, 'to_dict'): analysis = analysis.to_dict()
    elif hasattr(analysis, 'model_dump'): analysis = analysis.model_dump(mode='json')
    sources = gate.available_sources()
    fixture = {'status': gate.desktop_status(), 'analysis': analysis,
               'sources': {s['authority_id']: gate.source_capsule(s['authority_id']) for s in sources if s.get('retrieval_eligible')}}
    # An untrusted response must render as text, never HTML.
    fixture['analysis']['findings'][0]['explanation'] += ' <img src=x onerror="window.__unsafeExecuted=true">'
    ui = ROOT / 'src/nh_family_law_llm/ui'
    html = render_nh_review_html()
    html = html.replace('<link rel="stylesheet" href="/ui-assets/nh-review.css">', '<style>' + (ui / 'nh-review.css').read_text() + '</style>')
    html = html.replace('<script src="/ui-assets/nh-review.js" defer></script>', '')
    for name, mime in [('nh-mark.svg', 'image/svg+xml'), ('nh-banner.png', 'image/png')]:
        html = html.replace('/ui-assets/brand/' + name, 'data:' + mime + ';base64,' + base64.b64encode((ui / 'brand' / name).read_bytes()).decode())
    stub = 'window.__fixtures=' + json.dumps(fixture, ensure_ascii=True).replace('</', '<\\/') + ';\n' + r'''
window.__fixtureDelay = 0; window.__fixtureFail = false;
window.fetch = async function(path, options) {
  const delay = window.__fixtureDelay;
  if (delay) await new Promise(resolve => setTimeout(resolve, delay));
  if (window.__fixtureFail) return {ok:false, json:async()=>({detail:{message:'Synthetic unavailable fixture'}})};
  let value;
  if (path.includes('/status?')) value=window.__fixtures.status;
  else if (path.includes('/sources/')) value=window.__fixtures.sources[decodeURIComponent(path.split('/sources/')[1].split('?')[0])];
  else if (path.endsWith('/analyze')) value=window.__fixtures.analysis;
  else throw new Error('Unexpected offline request: '+path);
  return {ok:!!value,json:async()=>structuredClone(value)};
};
'''
    html = html.replace('</body>', '<script>' + stub + '</script><script>' + (ui / 'nh-review.js').read_text() + '</script></body>')
    path = work / 'offline-review-fixture.html'; path.write_text(html, encoding='utf-8')
    record = {'status':'not_run','mode':'offline_fixture_only','live_browser_qualified':False,
              'authority_promotions':0,'as_of_date':'2026-09-11','checks':[], 'errors':[],
              'source_asset_sha256': {name:hashlib.sha256((ui/name).read_bytes()).hexdigest() for name in ('nh-review.html','nh-review.css','nh-review.js')}}
    def checked(name): record['checks'].append(name)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.browser, headless=True, args=['--no-sandbox'])
            try:
                context = browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
                page = context.new_page(); page_errors=[]; requests=[]
                page.on('pageerror', lambda exc:page_errors.append(str(exc)))
                page.on('request', lambda req:requests.append(req.url) if req.url.startswith(('http:', 'https:')) else None)
                page.goto(path.as_uri(),wait_until='load')
                page.locator('#as-of').fill('2026-09-11');page.locator('#as-of').dispatch_event('change')
                page.locator('#question').fill('Review the synthetic parenting and support modification scenario.')
                page.locator('#analyze').click();page.wait_for_function('!document.getElementById("export").disabled')
                checked('real_UI_renders_fixture_analysis')
                assert page.locator('#results img').count()==0
                assert page.evaluate('window.__unsafeExecuted === undefined')
                assert '<img src=x' in page.locator('#results').inner_text()
                checked('untrusted_response_is_text_not_HTML')
                page.screenshot(path=str(evidence/'offline-desktop.png'))
                with page.expect_download() as event:page.locator('#export').click()
                target=work/'synthetic-review-export.json';event.value.save_as(target)
                saved=json.loads(target.read_text())
                assert saved['metadata']['filing_ready'] is False and saved['metadata']['jurisdiction']=='NH'
                serialized=page.evaluate('(report)=>JSON.stringify(report)',saved['report'])
                assert hashlib.sha256(serialized.encode()).hexdigest()==saved['report_sha256']
                record['export_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
                checked('export_download_and_report_hash')
                page.locator('#results .source button:enabled').first.click()
                page.wait_for_function('document.getElementById("source-text").textContent.length>0')
                assert 'not the official statute text' in page.locator('#source-notice').inner_text()
                page.locator('#close-source').click();checked('source_dialog_and_nonverbatim_warning')
                page.locator('#question').fill('Changed review input');assert page.locator('#export').is_disabled()
                checked('input_change_invalidates_export')
                page.locator('details').evaluate('(node)=>node.open=true')
                page.locator('#facts').fill('[]');page.locator('#analyze').click()
                assert page.locator('#error').is_visible() and page.locator('#export').is_disabled()
                checked('malformed_facts_do_not_submit')
                page.locator('#facts').fill('');page.evaluate('window.__fixtureDelay=350')
                page.locator('#analyze').click();page.locator('#question').fill('Change while request is pending')
                page.wait_for_timeout(550);assert page.locator('#export').is_disabled()
                checked('late_response_cannot_restore_invalidated_export')
                page.evaluate('window.__fixtureDelay=0;window.__fixtureFail=true')
                page.locator('#analyze').click();page.wait_for_function('!document.getElementById("error").hidden')
                assert page.locator('#export').is_disabled();checked('service_error_never_enables_export')
                page.evaluate('window.__fixtureFail=false');page.locator('#clear').click()
                assert not page.locator('#question').input_value()
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1')
                page.screenshot(path=str(evidence/'offline-mobile.png'));checked('mobile_layout_has_no_horizontal_overflow')
                page.reload(wait_until='load')
                assert not page.locator('#question').input_value() and page.locator('#export').is_disabled()
                checked('reload_does_not_restore_case_inputs')
                assert not page_errors, page_errors
                assert not requests, requests
                checked('no_script_errors_or_HTTP_requests')
                record['status']='pass';record['browser_version']=browser.version
            finally:browser.close()
    except Exception as exc:
        record['status']='blocked' if 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc) else 'fail'
        record['errors'].append(f'{type(exc).__name__}: {exc}')
    output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2));return 0 if record['status']=='pass' else 1

if __name__=='__main__':raise SystemExit(main())
