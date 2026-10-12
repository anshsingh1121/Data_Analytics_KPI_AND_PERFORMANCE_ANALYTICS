import os
import sys
import pytest
from src.connectors.ssl_helper import (
    get_windows_certificates,
    build_enterprise_ca_bundle,
    configure_session_ssl,
    diagnose_ssl_error
)
from src.connectors.service_now_client import normalize_instance_url, ServiceNowClient
import requests

def test_normalize_instance_url():
    # Test standard subpath stripping
    assert normalize_instance_url("https://company.service-now.com/navpage.do") == "https://company.service-now.com"
    assert normalize_instance_url("https://company.service-now.com/now/nav/ui/home") == "https://company.service-now.com"
    assert normalize_instance_url("company.service-now.com") == "https://company.service-now.com"
    assert normalize_instance_url("https://company.service-now.com/") == "https://company.service-now.com"
    assert normalize_instance_url('"https://company.service-now.com"') == "https://company.service-now.com"
    assert normalize_instance_url("   https://company.service-now.com/   ") == "https://company.service-now.com"

def test_ssl_helper_functions(tmp_path):
    session = requests.Session()
    # 1. Insecure mode
    mode = configure_session_ssl(session, verify_tls=False)
    assert session.verify is False
    assert "DISABLED" in mode

    # 2. Windows enterprise bundle generation
    if sys.platform == "win32":
        bundle_path = str(tmp_path / "test_bundle.pem")
        res_path = build_enterprise_ca_bundle(output_path=bundle_path)
        assert os.path.exists(res_path)
        assert os.path.getsize(res_path) > 1000

        # Configure session with enterprise mode
        session2 = requests.Session()
        mode2 = configure_session_ssl(session2, verify_tls=True)
        assert "Enterprise Windows CA Store" in mode2

def test_diagnose_ssl_error():
    fake_error = Exception("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1006)")
    diag = diagnose_ssl_error(fake_error, "https://instance.service-now.com")
    assert diag["is_ssl_error"] is True
    assert "Corporate SSL Proxy" in diag["category"]
    assert len(diag["actionable_steps"]) >= 2
