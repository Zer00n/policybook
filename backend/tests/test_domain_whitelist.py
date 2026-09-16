import socket
from unittest.mock import patch
import pytest

from app.renewal.config import config_loader
from app.renewal.security import (
    DomainNotAllowedError,
    InvalidURLError,
    SSRFSecurityError,
    is_domain_allowed,
    is_ip_private_or_reserved,
    validate_fetch_url,
)


def test_allowed_domains_loaded():
    domains = config_loader.get_allowed_domains()
    assert "pingan.com" in domains
    assert "cbirc.gov.cn" in domains
    assert "nfra.gov.cn" in domains
    assert "cpic.com.cn" in domains
    assert len(domains) >= 10


def test_is_domain_allowed():
    allowed = ["pingan.com", "cpic.com.cn"]
    assert is_domain_allowed("pingan.com", allowed) is True
    assert is_domain_allowed("www.pingan.com", allowed) is True
    assert is_domain_allowed("open.api.pingan.com", allowed) is True
    assert is_domain_allowed("cpic.com.cn", allowed) is True
    assert is_domain_allowed("mall.cpic.com.cn", allowed) is True
    
    # Negative cases
    assert is_domain_allowed("evilpingan.com", allowed) is False
    assert is_domain_allowed("pingan.com.evil.com", allowed) is False
    assert is_domain_allowed("google.com", allowed) is False
    assert is_domain_allowed("localhost", allowed) is False


def test_is_ip_private_or_reserved():
    # Loopback
    assert is_ip_private_or_reserved("127.0.0.1") is True
    assert is_ip_private_or_reserved("127.0.1.1") is True
    assert is_ip_private_or_reserved("::1") is True

    # Private RFC 1918
    assert is_ip_private_or_reserved("10.0.0.1") is True
    assert is_ip_private_or_reserved("192.168.1.100") is True
    assert is_ip_private_or_reserved("172.16.0.1") is True
    assert is_ip_private_or_reserved("172.31.255.254") is True

    # Link local
    assert is_ip_private_or_reserved("169.254.169.254") is True
    assert is_ip_private_or_reserved("fe80::1") is True

    # Carrier-grade NAT (100.64.0.0/10)
    assert is_ip_private_or_reserved("100.64.0.1") is True

    # Unspecified / 0.0.0.0
    assert is_ip_private_or_reserved("0.0.0.0") is True

    # Public safe IP (e.g. DNS or public servers)
    assert is_ip_private_or_reserved("8.8.8.8") is False
    assert is_ip_private_or_reserved("1.1.1.1") is False
    assert is_ip_private_or_reserved("114.114.114.114") is False


def test_validate_fetch_url_scheme_and_domain():
    allowed = ["pingan.com"]

    # Invalid scheme
    with pytest.raises(InvalidURLError):
        validate_fetch_url("ftp://pingan.com/doc.pdf", allowed)

    with pytest.raises(InvalidURLError):
        validate_fetch_url("file:///etc/passwd", allowed)

    # Domain not in whitelist
    with pytest.raises(DomainNotAllowedError):
        validate_fetch_url("https://untrusted-insurance.com/doc.pdf", allowed)


def test_validate_fetch_url_ssrf_intercepted():
    allowed = ["pingan.com"]

    # Simulate DNS resolving pingan.com to an internal IP (DNS rebinding / SSRF attempt)
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
        with pytest.raises(SSRFSecurityError) as exc_info:
            validate_fetch_url("https://pingan.com/product/clause.pdf", allowed)
        assert "127.0.0.1" in str(exc_info.value)

    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.5", 443))
        ]
        with pytest.raises(SSRFSecurityError) as exc_info:
            validate_fetch_url("https://pingan.com/product/clause.pdf", allowed)
        assert "192.168.1.5" in str(exc_info.value)


def test_validate_fetch_url_valid():
    allowed = ["pingan.com"]
    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("120.52.148.118", 443))
        ]
        safe_url = validate_fetch_url("https://pingan.com/product/clause.pdf", allowed)
        assert safe_url == "https://pingan.com/product/clause.pdf"
