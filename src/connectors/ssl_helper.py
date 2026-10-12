"""
Enterprise SSL & TLS Helper Module.

Provides:
- Automatic extraction and caching of Windows OS Root & Intermediate Certificate Authorities
- Seamless integration with requests and certifi so corporate proxies (Zscaler, Netskope, etc.)
  are trusted automatically without disabling SSL verification.
- Explicit CA bundle configuration support (API_CA_BUNDLE).
- Safe SSL verification disable toggle with warning suppression when explicitly authorized.
- In-depth SSL error diagnostic analyzer.
"""

import os
import sys
import ssl
import logging
from typing import Optional, Dict, Any, List
import certifi
import urllib3

logger = logging.getLogger(__name__)

# Cached path for Windows enterprise bundle
DEFAULT_ENTERPRISE_BUNDLE_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "enterprise_ca_bundle.pem"
))


def get_windows_certificates() -> List[str]:
    """
    Extracts Root and Intermediate CA certificates from Windows Certificate Store.
    Returns list of PEM-encoded certificate strings.
    """
    pem_certs = []
    if sys.platform != "win32" or not hasattr(ssl, "enum_certificates"):
        return pem_certs

    # Stores to inspect: ROOT (Trusted Root CAs) and CA (Intermediate CAs)
    stores = ["ROOT", "CA"]
    for store_name in stores:
        try:
            for cert_der, encoding, trust in ssl.enum_certificates(store_name):
                if encoding == "x509_asn":
                    try:
                        pem = ssl.DER_cert_to_PEM_cert(cert_der)
                        pem_certs.append(pem)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Could not read Windows certificate store '{store_name}': {e}")

    logger.debug(f"Retrieved {len(pem_certs)} certificates from Windows Certificate Stores ({', '.join(stores)}).")
    return pem_certs


def build_enterprise_ca_bundle(output_path: Optional[str] = None, force_refresh: bool = False) -> str:
    """
    Builds a unified CA bundle combining Mozilla's certifi store with the Windows OS certificate store.
    This enables seamless HTTPS connectivity through corporate SSL inspection proxies
    while maintaining 100% cryptographic TLS verification.
    """
    bundle_path = output_path or DEFAULT_ENTERPRISE_BUNDLE_PATH

    # On non-Windows platforms, fallback directly to certifi
    if sys.platform != "win32" or not hasattr(ssl, "enum_certificates"):
        return certifi.where()

    # Reuse cached bundle if available and valid
    if not force_refresh and os.path.exists(bundle_path) and os.path.getsize(bundle_path) > 1000:
        logger.debug(f"Using cached enterprise CA bundle at: {bundle_path}")
        return bundle_path

    try:
        os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
        windows_pems = get_windows_certificates()
        if not windows_pems:
            return certifi.where()

        with open(certifi.where(), "r", encoding="utf-8") as f:
            certifi_content = f.read()

        combined_bundle = certifi_content + "\n# --- Windows Enterprise System Certificates ---\n" + "\n".join(windows_pems)

        with open(bundle_path, "w", encoding="utf-8") as f:
            f.write(combined_bundle)

        logger.info(f"Built enterprise CA bundle with {len(windows_pems)} Windows certificates at: {bundle_path}")
        return bundle_path
    except Exception as e:
        logger.warning(f"Could not construct combined enterprise CA bundle: {e}. Falling back to certifi default.")
        return certifi.where()


def configure_session_ssl(
    session: Any,
    verify_tls: bool = True,
    ca_bundle: Optional[str] = None
) -> str:
    """
    Configures SSL/TLS verification on a requests.Session instance.

    Returns:
        A human-readable status string describing the active SSL mode.
    """
    if not verify_tls:
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logger.warning(
            "[SECURITY ALERT] SSL verification is disabled (verify_tls=False). "
            "HTTPS traffic is encrypted, but server certificate validation is bypassed."
        )
        return "TLS Verification DISABLED (Insecure Mode)"

    # 1. Custom CA bundle provided in config/env
    if ca_bundle and os.path.exists(ca_bundle):
        session.verify = os.path.abspath(ca_bundle)
        logger.info(f"Using custom CA bundle from: {session.verify}")
        return f"Custom CA Bundle ({os.path.basename(ca_bundle)})"

    # 2. Check standard environment variable REQUESTS_CA_BUNDLE or CURL_CA_BUNDLE
    env_bundle = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("CURL_CA_BUNDLE")
    if env_bundle and os.path.exists(env_bundle):
        session.verify = os.path.abspath(env_bundle)
        logger.info(f"Using environment CA bundle from: {session.verify}")
        return f"Environment CA Bundle ({os.path.basename(env_bundle)})"

    # 3. Enterprise Windows OS Store Integration
    if sys.platform == "win32":
        enterprise_bundle = build_enterprise_ca_bundle()
        session.verify = enterprise_bundle
        return "Enterprise Windows CA Store + Mozilla Certifi"

    # 4. Standard certifi fallback
    session.verify = certifi.where()
    return "Standard Mozilla Certifi"


def diagnose_ssl_error(error: Exception, target_url: str) -> Dict[str, Any]:
    """
    Analyzes an SSL/TLS exception and returns structured diagnostics with actionable fixes.
    """
    err_str = str(error)
    err_lower = err_str.lower()

    diag = {
        "is_ssl_error": False,
        "category": "Unknown",
        "description": err_str,
        "actionable_steps": []
    }

    if "certificatetruncated" in err_lower or "ssl" in err_lower or "certificate" in err_lower:
        diag["is_ssl_error"] = True

    if "unable to get local issuer certificate" in err_lower or "self signed certificate" in err_lower or "self-signed" in err_lower:
        diag["category"] = "Corporate SSL Proxy / Self-Signed Root Certificate Interception"
        diag["description"] = (
            "Your company network uses an SSL inspection proxy (e.g., Zscaler, Netskope, Blue Coat) "
            "or your ServiceNow instance uses an internal enterprise certificate authority. "
            "Python's default certificate store does not recognize the internal corporate Root CA."
        )
        diag["actionable_steps"] = [
            "Automatic Fix: The system now reads your Windows OS Trusted Root Store directly into data/enterprise_ca_bundle.pem.",
            "If still encountering issues, ask your IT/Security team for your corporate root certificate (.cer or .pem) and set 'API_CA_BUNDLE=C:\\path\\to\\corp_ca.pem' in .env.",
            "Temporary/Testing Fallback: Set 'API_VERIFY_TLS=false' in your .env file to bypass certificate chain verification."
        ]
    elif "certificate has expired" in err_lower or "certificate is not valid yet" in err_lower:
        diag["category"] = "Expired or Invalid Certificate Date"
        diag["description"] = "The SSL certificate for the target instance has expired or your system clock is incorrect."
        diag["actionable_steps"] = [
            "Verify your local system date and time are synchronized.",
            "Contact your ServiceNow administrator to renew the SSL certificate."
        ]
    elif "hostname doesn't match" in err_lower or "host name mismatch" in err_lower:
        diag["category"] = "SSL Hostname Mismatch"
        diag["description"] = f"The SSL certificate does not match the host in your URL: {target_url}."
        diag["actionable_steps"] = [
            "Check API_BASE_URL in .env. Ensure it matches the exact instance hostname (e.g., https://your-instance.service-now.com without extra subpaths)."
        ]
    elif diag["is_ssl_error"]:
        diag["category"] = "General SSL/TLS Handshake Failure"
        diag["actionable_steps"] = [
            "Verify you are connected to your corporate VPN.",
            "Set 'API_VERIFY_TLS=false' in .env if testing within an internal secure network.",
            "Check if an enterprise HTTP proxy is required (set HTTP_PROXY and HTTPS_PROXY in .env)."
        ]

    return diag
