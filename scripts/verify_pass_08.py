#!/usr/bin/env python3
"""Pass 8 source/packaging gate. This does not qualify a Windows installation."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/pass-08/source-gate.json')
    args = parser.parse_args()
    from nh_family_law_llm.version import VERSION, PACKAGE_VERSION, BUILD_NUMBER
    scope = json.loads((ROOT / 'configs/v8010_release_scope.json').read_text())
    errors=[];checked=[]
    def require(ok, description):
        (checked if ok else errors).append(description)
    require((VERSION, PACKAGE_VERSION, BUILD_NUMBER)==('8.0.10','8.0.10.0',80), 'canonical version')
    for flag in ['production_ready','filing_ready','attorney_reviewed','windows_frozen_verified','msix_verified','signing_verified','wack_verified','clean_machine_verified','dependency_resolved_environment_verified']:
        require(scope.get(flag) is False, 'no unearned claim: '+flag)
    require(scope.get('authority_promotions')==0, 'no authority promotion in desktop pass')
    require(scope.get('remaining_planned_passes')==4, 'four planned passes remain')
    required=[
      'nh_family_law_llm/ui/nh-review.html','nh_family_law_llm/ui/nh-review.css','nh_family_law_llm/ui/nh-review.js',
      'nh_family_law_llm/ui/brand/nh-mark.svg','nh_family_law_llm/ui/brand/nh-banner.png',
      'nh_family_law_llm/resources/brand-kit/css/tokens.css',
      'nh_family_law_llm/resources/brand-kit/assets/favicon/favicon.svg',
      'nh_family_law_llm/resources/runtime/configs/nh_deliberation_state_machine.json',
      'nh_family_law_llm/resources/runtime/configs/nh_model_roles.json',
      'nh_family_law_llm/resources/runtime/configs/nh_model_admission_policy.json',
      'nh_family_law_llm/resources/runtime/configs/release_feature_truth.json',
      'nh_family_law_llm/resources/runtime/configs/v8010_release_scope.json',
      'nh_family_law_llm/data/authority_snapshot/manifest/nh_authorities.json',
      'nh_family_law_llm/desktop.py','nh_family_law_llm/activation.py','nh_family_law_llm/runtime_resources.py',
    ]
    for name in required:
        require((ROOT / 'src' / name).is_file(), 'source package file '+name)
    for name in ['nh-review.html','nh-review.css','nh-review.js']:
        require((ROOT/'src/nh_family_law_llm/ui'/name).read_bytes()==(ROOT/'nh_family_law_llm/ui'/name).read_bytes(), 'compatibility UI mirror '+name)
    for path in (ROOT/'src/nh_family_law_llm/resources/runtime/configs').glob('*.json'):
        require(path.read_bytes()==(ROOT/'configs'/path.name).read_bytes(), 'runtime config byte parity '+path.name)
    js=(ROOT/'src/nh_family_law_llm/ui/nh-review.js').read_text()
    require('innerHTML' not in js and 'localStorage' not in js, 'new UI does not use HTML sinks or case persistence')
    require((ROOT/'store/msix/AppxManifest.xml.in').read_bytes()==(ROOT/'packaging/windows/AppxManifest.template.xml').read_bytes(), 'single MSIX template')
    identity=json.loads((ROOT/'store/msix/identity.example.json').read_text())
    require(identity.get('production_identity_confirmed') is False, 'example identity not represented as Store registration')
    for path in [ROOT/'src',ROOT/'app',ROOT/'legal',ROOT/'scripts',ROOT/'tests']:
        for py in path.rglob('*.py'):
            try:ast.parse(py.read_text(encoding='utf-8-sig'),filename=str(py))
            except (SyntaxError, UnicodeError) as exc:errors.append(f'{py.relative_to(ROOT)}: {exc}')
    wheel_receipt=None
    wheel_integrity=None
    if args.wheel:
        wheel=args.wheel.absolute()
        if not wheel.resolve().is_relative_to(ROOT): raise SystemExit('wheel must be inside repository')
        from legal.release.wheel_integrity import audit_wheel
        wheel_integrity = audit_wheel(wheel, source_root=ROOT)
        require(wheel_integrity['status'] == 'pass', 'complete wheel source/resource integrity')
        errors.extend(wheel_integrity['blockers'])
        wheel_receipt={'filename':wheel.name,'sha256':wheel_integrity['wheel_sha256'],
                       'members':wheel_integrity.get('member_count',0),
                       'integrity_status':wheel_integrity['status']}
    report={'pass':8,'status':'pass' if not errors else 'fail','scope':'source and wheel packaging only','check_count':len(checked),'checks':checked,'errors':errors,'wheel':wheel_receipt,'wheel_integrity':wheel_integrity,'windows_qualified':False,'production_ready':False,'authority_promotions':0}
    out=args.output.absolute()
    if not out.is_relative_to(ROOT): raise SystemExit('output must stay inside this repository')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'checks':len(checked),'errors':errors,'wheel':wheel_receipt},indent=2))
    return 0 if not errors else 1

if __name__=='__main__':raise SystemExit(main())
