"""Explicit source identity must survive product-service delegation and cwd changes."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import authority_library_service as library
from app.services import authority_product_service as product

ROOT = Path(__file__).resolve().parents[1]


def test_product_accepts_only_the_explicit_source_sibling(tmp_path):
    project=tmp_path/'synthetic-source';project.mkdir()
    data=tmp_path/'synthetic-authority'
    service=product.AuthorityProductService(data_root=data,repo_root=project)
    assert service.repo_root==project and service.data_root==data
    assert not data.exists()


def test_explicit_product_source_overrides_environment_without_bypass(tmp_path,monkeypatch):
    project=tmp_path/'synthetic-source';project.mkdir()
    monkeypatch.setenv('NHFL_PROJECT_ROOT',str(tmp_path/'other-source'))
    forbidden=project/'forbidden-data'
    with pytest.raises(ValueError,match='outside the source repository'):
        product.AuthorityProductService(data_root=forbidden,repo_root=project)
    assert not forbidden.exists()


def test_product_default_source_is_not_the_callers_working_directory(tmp_path,monkeypatch):
    monkeypatch.delenv('NHFL_PROJECT_ROOT',raising=False)
    monkeypatch.chdir(tmp_path)
    forbidden=ROOT/'dist/pass08/never-authority'
    with pytest.raises(ValueError,match='outside the source repository'):
        product.AuthorityProductService(data_root=forbidden)
    assert not forbidden.exists()


def test_product_honors_configured_source_from_other_working_directory(tmp_path,monkeypatch):
    project=tmp_path/'synthetic-source';project.mkdir()
    data=tmp_path/'synthetic-data'
    monkeypatch.setenv('NHFL_PROJECT_ROOT',str(project))
    monkeypatch.setenv('NH_FAMILY_LAW_DATA_ROOT',str(data))
    monkeypatch.chdir(ROOT)
    service=product.AuthorityProductService()
    assert service.repo_root==project and service.data_root==data
    assert not data.exists()


def test_product_verifier_receives_the_same_source_identity(tmp_path,monkeypatch):
    project=tmp_path/'synthetic-source';project.mkdir()
    data=tmp_path/'synthetic-data';calls=[]
    def verifier(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(verify=lambda:SimpleNamespace(status='fail',as_dict=lambda:{'status':'fail'}))
    monkeypatch.setattr(product,'AuthorityProductVerifier',verifier)
    service=product.AuthorityProductService(data_root=data,repo_root=project)
    result=service.status()
    assert calls==[{'data_root':data,'repo_root':project}]
    assert result['active'] is False and result['review_required'] is True
    assert not data.exists()


def test_library_delegations_preserve_source_identity(tmp_path,monkeypatch):
    project=tmp_path/'synthetic-source';project.mkdir()
    data=tmp_path/'synthetic-data';calls=[]
    class MissingProduct:
        def __init__(self,**kwargs): calls.append(kwargs)
        def direct_authority_coverage(self): raise FileNotFoundError('fictional-unavailable')
        def _active_product(self,**kwargs): raise FileNotFoundError('fictional-unavailable')
    monkeypatch.setattr(library,'AuthorityProductService',MissingProduct)
    service=library.AuthorityLibraryService(data_root=data,repo_root=project)
    service.status()
    service._source_rows(data)
    assert len(calls)>=2
    assert all(call=={'data_root':data,'repo_root':project} for call in calls)
    assert not data.exists()


def test_cli_refusal_keeps_source_and_filesystem_untouched(tmp_path):
    import os, subprocess, sys
    # Both scripts are invoked by their actual installed source path. No test
    # environment value can exempt the source checkout from their policy.
    for script,mode in [('ingest-nh-authority.py','--dry-run'),
                        ('run-authority-data-product.py','--plan-only')]:
        forbidden=tmp_path/('forbidden-'+script)
        env=dict(os.environ,NHFL_PROJECT_ROOT=str(tmp_path/'fictional-project'))
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/script),
            '--data-root',str(forbidden),mode],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
        assert result.returncode!=0
        assert 'Refusing' in result.stderr
        assert not forbidden.exists()
