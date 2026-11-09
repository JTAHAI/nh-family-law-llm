"""Native WACK report shapes, not an assertion of Microsoft certification."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from legal.release.wack_qualification import parse_wack_report

ROOT = Path(__file__).resolve().parents[1]


def native_report(overall='PASS', result='PASS', extra=''):
    return ('<?xml version="1.0" encoding="utf-16"?>'
            '<REPORT NAME="Microsoft.Windows.SoftwareLogo.Tests.TestResultReport">'
            f'<OVERALL_RESULT>{overall}</OVERALL_RESULT>'
            '<TEST NAME="Fictional application inventory">'
            f'<RESULT>{result}</RESULT>{extra}</TEST></REPORT>').encode('utf-16')


def evaluate(tmp_path, payload, execution='completed'):
    candidate=tmp_path/'synthetic.msix'
    candidate.write_bytes(b'fictional candidate bytes')
    output=tmp_path/'native-report';output.mkdir()
    (output/'report.xml').write_bytes(payload)
    return parse_wack_report(package=candidate, output_root=output, execution_status=execution)


def test_native_child_result_format_counts_explicit_passes(tmp_path):
    report=evaluate(tmp_path,native_report())
    assert report['status']=='pass'
    assert report['report']['passed_test_count']==1


@pytest.mark.parametrize('overall,result', [
    ('FAIL','PASS'),('UNKNOWN','PASS'),('','PASS'),('SKIP','PASS'),
    ('PASS','FAIL'),('PASS','SKIP'),('PASS','UNKNOWN'),('PASS',''),
])
def test_incomplete_or_failed_native_status_is_never_a_pass(tmp_path,overall,result):
    report=evaluate(tmp_path,native_report(overall,result))
    assert report['status']=='blocked' and report['store_release_blocked'] is True


def test_contradictory_native_result_nodes_fail_closed(tmp_path):
    report=evaluate(tmp_path,native_report(extra='<RESULT>FAIL</RESULT>'))
    assert report['status']=='blocked'


def test_failed_native_child_test_case_cannot_be_hidden_by_parent(tmp_path):
    report=evaluate(tmp_path,native_report(extra='<TESTCASE NAME="Synthetic"><RESULT>SKIP</RESULT></TESTCASE>'))
    assert report['status']=='blocked'


def test_utf16_xml_declarations_are_not_expanded(tmp_path):
    payload=('<?xml version="1.0" encoding="utf-16"?>'
             '<!DOCTYPE Results [<!ENTITY sample "PASS">]>'
             '<Results><TestResult Status="Pass">&sample;</TestResult></Results>').encode('utf-16')
    report=evaluate(tmp_path,payload)
    assert 'wack_report_unparseable' in report['blockers']


def test_parser_cli_does_not_import_optional_application_dependencies(tmp_path):
    package=tmp_path/'synthetic.msix';package.write_bytes(b'fictional')
    output=tmp_path/'reports';output.mkdir()
    (output/'native.xml').write_bytes(native_report('FAIL','FAIL'))
    receipt=tmp_path/'receipt.json'
    completed=subprocess.run([sys.executable,'-I','-S','-B',str(ROOT/'scripts/parse-wack-report.py'),
        '--package',str(package),'--output-root',str(output),'--execution-status','failed',
        '--output',str(receipt)],capture_output=True,text=True,timeout=20)
    assert completed.returncode==1
    assert receipt.is_file(), completed.stderr
    report=json.loads(receipt.read_text())
    assert report['status']=='blocked'
    assert 'wack_failures_present' in report['blockers']
    assert 'ModuleNotFoundError' not in completed.stderr
