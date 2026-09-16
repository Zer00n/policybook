import ipaddress
import socket
from urllib.parse import urlparse


class RenewalSecurityError(Exception):
    """Base exception for renewal security violations."""
    pass


class InvalidURLError(RenewalSecurityError):
    pass


class DomainNotAllowedError(RenewalSecurityError):
    pass


class SSRFSecurityError(RenewalSecurityError):
    pass


def is_ip_private_or_reserved(ip_str: str) -> bool:
    """
    Check if an IP address string is private, loopback, link-local,
    reserved, multicast, carrier-grade NAT, or unspecified.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        # Check standard attributes
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True
        
        # Check carrier-grade NAT (100.64.0.0/10)
        cgnat_net = ipaddress.ip_network("100.64.0.0/10")
        if ip in cgnat_net:
            return True
            
        return False
    except ValueError:
        return True


def is_domain_allowed(hostname: str, allowed_domains: list[str]) -> bool:
    """
    Check if hostname is in allowed_domains or is a subdomain of an allowed domain.
    E.g. for allowed domain 'pingan.com':
    - 'pingan.com' -> True
    - 'www.pingan.com' -> True
    - 'sub.service.pingan.com' -> True
    - 'notpingan.com' -> False
    - 'evilpingan.com' -> False
    """
    hostname = hostname.lower().strip()
    if not hostname:
        return False

    for domain in allowed_domains:
        domain = domain.lower().strip()
        if not domain:
            continue
        if hostname == domain or hostname.endswith(f".{domain}"):
            return True
    return False


def validate_fetch_url(url: str, allowed_domains: list[str]) -> str:
    """
    Validates that a URL is safe for fetching:
    1. Valid scheme (http/https)
    2. Hostname matches domain whitelist
    3. Hostname does not resolve to private, loopback, or reserved IP addresses (SSRF defense)
    Returns normalized URL if safe, raises appropriate RenewalSecurityError on violation.
    """
    if not url or not isinstance(url, str):
        raise InvalidURLError("URL 不能为空")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise InvalidURLError(f"只允许 http 或 https 协议，不支持 '{parsed.scheme}'")

    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError("URL 缺少有效主机名")

    # 1. Whitelist domain check
    if not is_domain_allowed(hostname, allowed_domains):
        raise DomainNotAllowedError(f"域名 '{hostname}' 不在设置的官网与监管披露平台白名单中")

    # 2. SSRF check via DNS resolution
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise SSRFSecurityError(f"DNS 解析失败: {e}")

    for addr in addr_info:
        ip = addr[4][0]
        if is_ip_private_or_reserved(ip):
            raise SSRFSecurityError(f"SSRF 防护拦截：主机 '{hostname}' 解析到私有/保留地址 '{ip}'")

    return url
