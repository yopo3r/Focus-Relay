"""Consulta (solo cuando el usuario lo pide) si hay una versión nueva publicada en GitHub."""
import json
import re
import urllib.request

REPO = "yopo3r/Focus-Relay"
REPO_URL = f"https://github.com/{REPO}"
RELEASES_URL = f"{REPO_URL}/releases"
ISSUES_URL = f"{REPO_URL}/issues"
BUG_URL = f"{REPO_URL}/issues/new?template=bug_report.md"
IDEA_URL = f"{REPO_URL}/issues/new?template=feature_request.md"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"


def parse_version(text):
    """'v3.21.2' / '3.21.2-beta' -> (3, 21, 2). Devuelve () si no hay números."""
    nums = re.findall(r"\d+", str(text or "").split("-")[0])
    return tuple(int(n) for n in nums[:4])


def is_newer(remote, local):
    r, l_ = parse_version(remote), parse_version(local)
    return bool(r) and r > l_


def fetch_latest(timeout=6):
    """Devuelve (versión, url) de la última publicación, o None si no hay ninguna. Lanza OSError/ValueError si falla."""
    req = urllib.request.Request(API_LATEST, headers={"Accept": "application/vnd.github+json", "User-Agent": "FocusRelay"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    tag = data.get("tag_name") or data.get("name") or ""
    return (tag, data.get("html_url") or RELEASES_URL) if tag else None
