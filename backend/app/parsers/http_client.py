"""Bounded HTTPS GET, public DNS pinning, redirects and robots. No retries/bypass."""

import http.client
import ipaddress
import math
import re
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import truststore

from app.parsers.sources import CollectionError


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict
    url: str


def public_addresses(host):
    try:
        addresses = list(dict.fromkeys(
            item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ))
    except OSError:
        raise CollectionError("DNS_ERROR") from None
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise CollectionError("PRIVATE_ADDRESS")
    return addresses


def robots_rules(text, user_agent, url):
    """Longest matching Allow/Disallow; * and $ patterns; explicit UA overrides *."""
    groups, agents, rules = [], [], []
    in_rules = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif key in ("allow", "disallow", "crawl-delay"):
            in_rules = True
            rules.append((key, value))
    groups.append((agents, rules))
    specific = [
        (max(len(a) for a in agents if a != "*" and a in user_agent.lower()), rules)
        for agents, rules in groups
        if any(a != "*" and a in user_agent.lower() for a in agents)
    ]
    if specific:
        longest = max(length for length, _ in specific)
        selected = [rs for length, rs in specific if length == longest]
    else:
        selected = [rs for agents, rs in groups if "*" in agents]
    parsed = urlsplit(url)
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    matches, delay = [], 0.0
    for rs in selected:
        for key, value in rs:
            if key == "crawl-delay":
                try:
                    delay = max(delay, float(value))
                    if not math.isfinite(float(value)) or float(value) < 0:
                        raise ValueError
                except ValueError:
                    raise CollectionError("ROBOTS_INVALID_DELAY") from None
            elif value:
                if len(value) > 1024 or value.count("*") > 16:
                    raise CollectionError("ROBOTS_INVALID")
                pattern = "^" + re.escape(value).replace(r"\*", ".*")
                if value.endswith("$"):
                    pattern = pattern[:-2] + "$"
                if re.search(pattern, path):
                    matches.append((len(value.replace("*", "").rstrip("$")), key))
    if matches:
        length = max(m[0] for m in matches)
        allowed = any(k == "allow" for n, k in matches if n == length)
    else:
        allowed = True
    return allowed, delay


class NewsHTTPClient:
    def __init__(self, settings):
        self.timeout = settings.news_timeout_seconds
        self.max_bytes = settings.news_max_response_bytes
        self.user_agent = settings.news_user_agent
        self.delay = settings.news_request_delay_seconds
        self._robots = {}
        self._last_request = {}
        # Use OS trust roots on macOS and Linux, without disabling TLS verification.
        self.context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    def _request(self, url, max_bytes):
        host = urlsplit(url).hostname
        address = public_addresses(host)[0]
        connection = http.client.HTTPSConnection(host, timeout=self.timeout, context=self.context)
        # Pin the validated address, but keep the original host for Host/SNI/certificate checks.
        connection._create_connection = lambda ignored, timeout, source_address=None: socket.create_connection(
            (address, 443), timeout, source_address
        )
        start = time.monotonic()
        try:
            parsed = urlsplit(url)
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
            connection.request("GET", path, headers={
                "User-Agent": self.user_agent,
                "Accept": "application/rss+xml, application/xml, text/html, text/plain",
                "Accept-Encoding": "identity",
            })
            sock = connection.sock
            response = connection.getresponse()
            headers = {k.lower(): v for k, v in response.getheaders()}
            if response.status != 200:
                return Response(response.status, b"", headers, url)
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise CollectionError("UNSUPPORTED_ENCODING")
            if int(headers.get("content-length", "0")) > max_bytes:
                raise CollectionError("RESPONSE_TOO_LARGE")
            chunks, size = [], 0
            while True:
                remaining = self.timeout - (time.monotonic() - start)
                if remaining <= 0:
                    raise CollectionError("TIMEOUT")
                sock.settimeout(remaining)
                chunk = response.read1(min(65536, max_bytes + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise CollectionError("RESPONSE_TOO_LARGE")
                chunks.append(chunk)
            return Response(response.status, b"".join(chunks), headers, url)
        except CollectionError:
            raise
        except (TimeoutError, socket.timeout):
            raise CollectionError("TIMEOUT") from None
        except ssl.SSLError:
            raise CollectionError("TLS_ERROR") from None
        except (OSError, http.client.HTTPException, ValueError):
            raise CollectionError("HTTP_PROTOCOL_ERROR") from None
        finally:
            connection.close()

    def _pace(self, host, delay):
        # Do not sleep indefinitely for an unusual site crawl-delay.
        if delay > 60:
            raise CollectionError("ROBOTS_DELAY_TOO_LONG")
        wait = delay - (time.monotonic() - self._last_request.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def _check_robots(self, url):
        host = urlsplit(url).hostname
        if host not in self._robots:
            response = self._request("https://" + host + "/robots.txt", min(self.max_bytes, 300000))
            if response.status == 404:
                self._robots[host] = ""
            elif response.status == 200:
                if b"<html" in response.body.lower() or b"<!doctype" in response.body.lower():
                    raise CollectionError("ROBOTS_INVALID")
                try:
                    self._robots[host] = response.body.decode("utf-8-sig", errors="strict")
                except UnicodeError:
                    raise CollectionError("ROBOTS_INVALID") from None
            else:
                raise CollectionError("ROBOTS_UNAVAILABLE", response.status, response.headers.get("retry-after"))
            self._last_request[host] = time.monotonic()
        allowed, delay = robots_rules(self._robots[host], self.user_agent, url)
        if not allowed:
            raise CollectionError("ROBOTS_DENIED")
        self._pace(host, max(delay, self.delay))

    def get(self, url, source, *, feed=False):
        url = source.url(url, feed=feed)
        for _ in range(4):
            self._check_robots(url)
            response = self._request(url, self.max_bytes)
            if response.status in (301, 302, 303, 307, 308):
                target = urljoin(url, response.headers.get("location", ""))
                if urlsplit(target).scheme != "https":
                    raise CollectionError("REDIRECT_NOT_ALLOWED")
                url = source.url(target, feed=feed)
                continue
            if response.status != 200:
                raise CollectionError("HTTP_STATUS", response.status, response.headers.get("retry-after"))
            return response
        raise CollectionError("TOO_MANY_REDIRECTS")
