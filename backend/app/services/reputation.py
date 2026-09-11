import ipaddress
import socket
import ssl
import time
from functools import lru_cache

import httpx

PRIVATE_BLOCKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]


def is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return False
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        return is_public_ip(str(ip.ipv4_mapped))
    for block in PRIVATE_BLOCKS:
        if ip.version == block.version and ip in block:
            return False
    return True


def basic_domain_checks(domain: str) -> dict:
    result = {"dns_resolves": False, "https_reachable": False, "tls_ok": False, "error": None}
    try:
        infos = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return result

    ips = {info[4][0] for info in infos}
    if not ips:
        return result
    if any(not is_public_ip(ip) for ip in ips):
        result["error"] = "域名解析到内网/保留地址，已阻止连接（SSRF 防护）"
        return result
    result["dns_resolves"] = True

    try:
        ip = sorted(ips)[0]
        ctx = ssl.create_default_context()
        with socket.create_connection((ip, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                ssock.getpeercert()
                result["https_reachable"] = True
                result["tls_ok"] = True
    except OSError as exc:
        result["error"] = str(exc)
    return result


@lru_cache(maxsize=512)
def _cached_checks(domain: str, bucket: int) -> dict:
    return basic_domain_checks(domain)


def domain_checks_cached(domain: str, ttl_seconds: int = 60) -> dict:
    return _cached_checks(domain, int(time.time()) // ttl_seconds)


def _resolve_public_ips(domain: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    ips = sorted({info[4][0] for info in infos})
    return [ip for ip in ips if is_public_ip(ip)]


def check_dns_txt(domain: str, token: str) -> bool:
    try:
        r = httpx.get(
            "https://cloudflare-dns.com/dns-query",
            params={"name": domain, "type": "TXT"},
            headers={"Accept": "application/dns-json"},
            timeout=10,
        )
        data = r.json()
        answers = data.get("Answer") or []
        for a in answers:
            text = str(a.get("data", "")).strip('"')
            if f"odr-verify={token}" in text:
                return True
        return False
    except Exception:
        return False


def check_well_known(domain: str, token: str) -> bool:
    ips = _resolve_public_ips(domain)
    if not ips:
        return False
    ip = ips[0]
    if ":" in ip:
        ip = f"[{ip}]"
    try:
        r = httpx.get(
            f"https://{ip}/.well-known/odr-verification.txt",
            headers={"Host": domain},
            extensions={"sni_hostname": domain},
            timeout=10,
            follow_redirects=False,
        )
        return r.status_code == 200 and token in r.text
    except Exception:
        return False
