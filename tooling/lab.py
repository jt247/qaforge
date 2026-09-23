#!/usr/bin/env python3
"""QAForge local QA orchestration. Standard library only; a smoke check never implies full QA.

product.json contract (validated by validate_config; there is no separate JSON Schema):
  schema_version: int, must be 1
  name: non-empty string
  slug: non-empty string, [a-z0-9-]+
  priority, kind, requirements_status, security_target: free strings (informational)
  environments.staging / environments.production: objects with
    url: string ("" until configured)
    enabled: bool
    allowed_hosts: list[str]
    approved_actions: list, subset of ACTIONS, always includes "read-only" once configured
    build: string ("unknown" until pinned)
    scope_notes: string
  An enabled environment additionally requires:
    authorized_by: string   who authorized this assessment
    auth_method: string     how ownership/authorization was confirmed
    granted_at: ISO 8601 string
    expires_at: ISO 8601 string   (configure sets this to granted_at + SCOPE_TTL_DAYS)
    insecure: bool          true only when configured with --allow-insecure (permits http://)
    allow_private: bool     true only when configured with --allow-private (permits RFC1918/loopback targets)
"""
import argparse
import hashlib
import ipaddress
import socket
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ('codex', 'claude')
STATUSES = ('passed', 'failed', 'blocked', 'not-run', 'not-applicable')
ACTIONS = ('read-only', 'fixture-write', 'messaging', 'sandbox-payment')
SCOPE_TTL_DAYS = 14
SMOKE_CASE = 'WEB-001'  # every product catalog must contain this id; smoke records against it
METADATA_ADDRS = {'169.254.169.254', 'fd00:ec2::254', '100.100.100.200'}
METADATA_NAMES = {'metadata', 'metadata.google.internal', 'metadata.goog'}
SECRET_PATTERNS = [re.compile(p, re.I) for p in (
    r'bearer\s+[a-z0-9._\-]{12,}',
    r'\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*\S',
    r'AKIA[0-9A-Z]{16}',
    r'\bgh[pousr]_[A-Za-z0-9]{20,}',
    r'\bsk-[A-Za-z0-9]{20,}',
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
)]
CARD_RUN = re.compile(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)')

def luhn_ok(digits):
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9: d -= 9
        total += d
    return total % 10 == 0

def card_like(text):
    """A 13-19 digit run only counts as card-like if it passes Luhn; timestamps and ids rarely do."""
    for m in CARD_RUN.finditer(text or ''):
        digits = re.sub(r'[ -]', '', m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits): return True
    return False

def now(): return datetime.now(timezone.utc).isoformat()
def read(path): return json.loads(path.read_text())
def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.replace(path)
def fail(message): raise ValueError(message)
def product(slug):
    if not re.fullmatch(r'_?[a-z0-9][a-z0-9-]*', slug): fail('Invalid product slug')
    path = ROOT / 'products' / slug
    if not (path / 'product.json').is_file(): fail('Unknown product')
    return path

def validate_config(c):
    errors = []
    if c.get('schema_version') != 1: errors.append('schema_version must be 1')
    for field in ('name', 'slug'):
        if not isinstance(c.get(field), str) or not c[field]: errors.append(f'Missing {field}')
    for name in ('staging', 'production'):
        env = c.get('environments', {}).get(name)
        if not isinstance(env, dict):
            errors.append(f'Missing environment {name}'); continue
        if not isinstance(env.get('enabled'), bool): errors.append(f'{name}: enabled must be boolean')
        if not isinstance(env.get('url'), str): errors.append(f'{name}: URL must be a string')
        if not isinstance(env.get('build'), str): errors.append(f'{name}: build must be a string')
        if not isinstance(env.get('allowed_hosts'), list): errors.append(f'{name}: hosts must be a list')
        if not isinstance(env.get('approved_actions'), list) or any(a not in ACTIONS for a in env.get('approved_actions', [])):
            errors.append(f'{name}: invalid approved actions')
        if env.get('enabled'):
            for f in ('authorized_by', 'auth_method', 'granted_at', 'expires_at'):
                if not isinstance(env.get(f), str) or not env[f]:
                    errors.append(f'{name}: enabled scope missing {f}')
            try: check_target(env.get('url', ''), env)
            except ValueError as e: errors.append(f'{name}: {e}')
    return errors

def check_target(url, env):
    """Offline URL-shape and policy check. Network resolution is check_host_safety."""
    u = urlparse(url)
    if u.scheme not in ('https', 'http') or not u.hostname: fail('A valid HTTP(S) URL is required')
    if u.scheme == 'http' and not env.get('insecure'): fail('HTTPS is required; re-run configure with --allow-insecure for a plaintext target')
    if u.username or u.password or u.query or u.fragment: fail('Use a base URL without credentials, query, or fragment')
    if u.hostname.lower() not in env.get('allowed_hosts', []): fail('Target host is outside approved hosts')
    return url

def check_host_safety(hostname, env):
    """Resolve hostname and reject metadata, private, loopback, link-local, CGNAT, and reserved targets.

    --allow-private (env['allow_private']) permits RFC1918/loopback/link-local for local staging.
    Cloud metadata endpoints are rejected regardless of any flag.
    """
    h = (hostname or '').lower().rstrip('.')
    if not h: fail('Target host is missing')
    allow_private = bool(env.get('allow_private'))
    if h in METADATA_NAMES: fail('Cloud metadata endpoint is never an allowed target')
    if not allow_private and (h == 'localhost' or h.endswith('.internal') or h.endswith('.local')):
        fail(f'Internal hostname {h} requires configure --allow-private')
    try:
        infos = socket.getaddrinfo(h, None)
    except socket.gaierror:
        fail(f'Target host {h} does not resolve; refusing an uncheckable scope')
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if str(ip) in METADATA_ADDRS: fail(f'Target resolves to a cloud metadata address ({ip})')
        cgnat = ip.version == 4 and ip in ipaddress.ip_network('100.64.0.0/10')
        if not allow_private and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or cgnat):
            fail(f'Target resolves to a private or reserved address ({ip}); use configure --allow-private for a local target')

def scope_active(env):
    exp = env.get('expires_at')
    if not exp: return
    if datetime.now(timezone.utc) > datetime.fromisoformat(exp):
        fail(f'Scope expired at {exp}. Re-run configure with fresh authorization before continuing.')

def secret_hit(text):
    for pat in SECRET_PATTERNS:
        if pat.search(text or ''): return True
    if card_like(text): return True
    identity = ROOT / 'local/identity.json'
    if identity.exists():
        try: ident = read(identity)
        except (ValueError, OSError): return False
        for value in (ident.get('gmail_address', ''), ident.get('phone_number', '')):
            if value and value in (text or ''): return True
    return False

def scan_secret(text):
    if secret_hit(text): fail('Text appears to contain a secret, key, or a value from local/identity.json; redact before recording')

def run_path(p, rid):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', rid): fail('Invalid run ID')
    r = p / 'runs' / rid
    if not (r / 'manifest.json').is_file(): fail('Unknown run')
    return r

def require_owner(r, agent):
    m = read(r / 'manifest.json')
    if m['status'] != 'open': fail('Run is closed; create a linked retest run')
    if m['agent'] != agent: fail('Run belongs to a different agent')
    if not (r / '.claim' / 'owner.json').exists(): fail('Claim the run before recording or executing')
    if read(r / '.claim' / 'owner.json')['agent'] != agent: fail('Claim belongs to another agent')
    return m

def claim(r, agent):
    m = read(r / 'manifest.json')
    if m['agent'] != agent or m['status'] != 'open': fail('Only the assigned agent can claim an open run')
    try: (r / '.claim').mkdir()
    except FileExistsError: fail('Run already claimed; inspect ownership and handoff before releasing')
    save(r / '.claim' / 'owner.json', {'agent': agent, 'claimed_at': now()})

def record(r, agent, case, status, note, evidence):
    require_owner(r, agent)
    scan_secret(note)
    cases = {c['id'] for c in read(r / 'cases.json')}
    if case not in cases: fail('Case is absent from the frozen run catalog')
    if status not in STATUSES: fail('Invalid result status')
    if status in ('passed', 'failed') and not evidence: fail('Passed/failed results require local evidence')
    if not note.strip(): fail('Every result requires an explanation')
    for ref in evidence:
        target = (r / ref).resolve()
        if not target.is_relative_to(r.resolve()) or not target.is_file(): fail('Evidence must resolve to a file inside this run')
        if target.stat().st_size == 0: fail(f'Evidence file is empty: {ref}')
    folder = r / 'results' / agent
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    save(folder / f'{case}_{stamp}.json', {'case': case, 'status': status, 'note': note, 'evidence': evidence, 'agent': agent, 'recorded_at': now()})

class ScopedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, env): self.env = env
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_target(newurl, self.env)
        check_host_safety(urlparse(newurl).hostname, self.env)
        if urlparse(req.full_url).scheme == 'https' and urlparse(newurl).scheme != 'https': fail('HTTPS downgrade blocked')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def smoke(r, agent):
    m = require_owner(r, agent)
    env = m['scope']
    if not env['enabled'] or 'read-only' not in env['approved_actions']: fail('Read-only scope is not enabled')
    scope_active(env)
    check_target(env['url'], env)
    check_host_safety(urlparse(env['url']).hostname, env)
    opener = urllib.request.build_opener(ScopedRedirect(env))
    started = now()
    try:
        request = urllib.request.Request(env['url'], headers={'User-Agent': 'QAForge/1.0 (authorized-read-only-smoke)'})
        with opener.open(request, timeout=15) as response:
            code = response.status
            response.read(1024)  # bounded read; page content is deliberately not persisted
        status = 'passed' if 200 <= code < 300 else 'failed'
        note = f'HTTP {code}; reachability only. Browser behavior and product requirements were not assessed.'
    except urllib.error.HTTPError as e:
        status, note = 'failed', f'HTTP {e.code}; public reachability check failed; root cause requires investigation.'
    except (urllib.error.URLError, ValueError, TimeoutError, OSError) as e:
        status, note = 'blocked', f'Check blocked ({type(e).__name__}); inspect target, network, certificate, or redirect scope. No broader conclusion.'
    ref = f'evidence/http-smoke-{datetime.now(timezone.utc).strftime("%H%M%S%f")}.json'
    save(r / ref, {'started_at': started, 'finished_at': now(), 'status': status, 'note': note})
    record(r, agent, SMOKE_CASE, status, note, [ref])
    print(note)
    return 0 if status == 'passed' else 2

ONBOARDING_MARKERS = {
    'docs/requirements.md': 'No source requirements imported',
    'guides/role-permission-matrix.md': 'Pending product confirmation',
    'guides/threat-model.md': 'Identify assets, actors, trust boundaries',
}

def onboarding_gaps(p):
    return [rel for rel, marker in ONBOARDING_MARKERS.items()
            if (p / rel).is_file() and marker in (p / rel).read_text()]

def report(r):
    m = read(r / 'manifest.json')
    latest = {}
    for f in sorted((r / 'results').glob('*/*.json')):
        item = read(f)
        if item['case'] not in latest or item['recorded_at'] > latest[item['case']]['recorded_at']:
            latest[item['case']] = item
    scope = m['scope']
    auth = f'Authorization: {scope.get("authorized_by", "unrecorded")} via {scope.get("auth_method", "unrecorded")}; expires {scope.get("expires_at", "n/a")}'
    lines = [f'# {m["product_name"]} — {r.name}', '', '**Release readiness: NOT ESTABLISHED.**', '',
             'This report summarizes recorded execution. Independent review, requirement coverage, unresolved findings, and owner decisions must be assessed separately.', '',
             f'Environment: {m["environment"]} | Build: {scope["build"]} | Agent: {m["agent"]}', '', auth, '',
             '| Case | Status | Notes |', '|---|---|---|']
    counts = {s: 0 for s in STATUSES}
    for c in read(r / 'cases.json'):
        item = latest.get(c['id'], {'status': 'not-run', 'note': 'No execution recorded'})
        counts[item['status']] = counts.get(item['status'], 0) + 1
        note = item['note']
        if secret_hit(note): note = '[redacted: matched a secret pattern; inspect the raw result file]'
        note = note.replace('|', '\\|').replace('\n', ' ')
        lines.append(f'| {c["id"]} | {item["status"]} | {note} |')
    lines += ['', 'Counts: ' + ', '.join(f'{s}={counts.get(s, 0)}' for s in STATUSES), '',
              'See peer-review.md, product findings/, and cleanup.md before a release decision. A passing HTTP check is not a passing product assessment.']
    (r / 'report.md').write_text('\n'.join(lines) + '\n')
    print(str(r / 'report.md'))

def template_text(name, fallback):
    path = ROOT / 'templates' / name
    return path.read_text() if path.is_file() else fallback

def write_run_docs(r, p, c, a, env):
    """Copy the run plan and session brief templates into the run, prefilled from the confirmed chat brief."""
    head = (f'Goal: {a.goal}\nConfirmed by: {a.confirmed_by}\nLead agent: {a.agent}\n'
            f'Product: {c["name"]}\nEnvironment: {a.env}\nURL: {env["url"]}\nBuild: {env["build"]}\n'
            f'Retest of: {a.retest_of or "none"}\nReview of: {a.review_of or "none"}\n')
    gaps = onboarding_gaps(p)
    gap_line = ('\nOnboarding incomplete: ' + ', '.join(gaps) + '. Only baseline lab cases are justified.\n') if gaps else ''
    plan = template_text('run-plan.md', '# Run plan\n')
    brief = template_text('session-brief.md', '# Testing session brief\n')
    (r / 'plan.md').write_text(plan.rstrip('\n') + '\n\n## Confirmed in chat\n' + head + gap_line)
    (r / 'brief.md').write_text(brief.rstrip('\n') + '\n\n## Confirmed in chat\n' + head)

FINDINGS_INDEX_HEADER = ('# Findings index\n| ID | Severity | Status | First run | Retest run | Title |\n|---|---|---|---|---|---|\n')

def ensure_findings_index(p):
    index = p / 'findings' / 'INDEX.md'
    if not index.exists():
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(template_text('findings-index.md', FINDINGS_INDEX_HEADER))

def cmd_init():
    import shutil, subprocess
    ok = True
    def line(good, text):
        nonlocal ok
        ok = ok and good
        print(('OK   ' if good else 'MISSING ') + text)
    line(sys.version_info >= (3, 10), f'Python {sys.version.split()[0]} (need 3.10+)')
    line(shutil.which('git') is not None, 'git on PATH')
    settings = Path.home() / '.claude' / 'settings.json'
    ecc = False
    if settings.is_file():
        try: ecc = bool(read(settings).get('enabledPlugins', {}).get('ecc@ecc'))
        except (ValueError, OSError): ecc = False
    print(('OK   ' if ecc else 'INFO ') + ('ECC plugin enabled for Claude Code' if ecc else 'ECC plugin not detected for Claude Code; install with: npx ecc-universal setup'))
    blobs = ''
    for f in (Path.home() / '.claude.json', settings, ROOT / '.mcp.json', Path.home() / '.codex' / 'config.toml'):
        if f.is_file():
            try: blobs += f.read_text()
            except OSError: pass
    browser = ('chrome-devtools' in blobs) or ('playwright' in blobs.lower())
    print(('OK   ' if browser else 'INFO ') + ('browser MCP configured (chrome-devtools or playwright)' if browser else 'no browser MCP detected; agents cannot run browser cases until one is configured'))
    line(shutil.which('claude') is not None, 'claude CLI on PATH (Claude Code)')
    line(shutil.which('codex') is not None, 'codex CLI on PATH (Codex)')
    identity = ROOT / 'local' / 'identity.json'
    if not identity.exists():
        identity.parent.mkdir(parents=True, exist_ok=True)
        identity.write_text(template_text('identity.example.json', '{}\n'))
        print('CREATED local/identity.json from template; fill gmail_address and phone_number before account-creation flows')
    else:
        print('OK   local/identity.json present')
    try:
        main(['validate']); print('OK   product configurations valid')
    except ValueError as e:
        ok = False; print(f'FAIL validate: {e}')
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests')], capture_output=True, text=True)
    line(tests.returncode == 0, 'unit tests ' + ('pass' if tests.returncode == 0 else 'FAIL:\n' + tests.stderr[-2000:]))
    print('\nREADY' if ok else '\nNOT READY: fix the MISSING/FAIL items above, then re-run init.')
    return 0 if ok else 2

def session_prompt(p, c, agent):
    return (f'Read AGENTS.md and {"CLAUDE.md" if agent == "claude" else "CODEX.md"} first. '
            f'Start a QAForge testing session for the product "{c["name"]}" (slug {p.name}). '
            'Read its coordination/state.md, coordination/session-log.md, and latest run. '
            'Then state the goal and the full session brief (templates/session-brief.md fields) in chat '
            'and wait for my explicit confirmation before running configure, preflight, new-run, or any browser action.')

def cmd_session(p, agent, print_only):
    import os, shutil
    c = read(p / 'product.json')
    prompt = session_prompt(p, c, agent)
    if print_only:
        print(prompt); return 0
    cli = 'claude' if agent == 'claude' else 'codex'
    if shutil.which(cli) is None:
        fail(f'{cli} CLI not found on PATH. Install and sign in first: '
             + ('https://docs.anthropic.com/claude-code' if cli == 'claude' else 'https://github.com/openai/codex') + '. '
             'Or pass --print-only and paste the prompt into the desktop app.')
    os.chdir(ROOT)
    os.execvp(cli, [cli, prompt])

def append_session_log(p, agent, confirmed_by, env, rid, goal):
    log = p / 'coordination/session-log.md'
    if not log.exists():
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('# Session log\nDated, append-only record of every confirmed testing session for this product.\n\n')
    with log.open('a') as f:
        f.write(f'- {now()} | {agent} | run {rid} | env {env} | confirmed by {confirmed_by} | goal: {goal}\n')

def cmd_runs(p):
    rows = []
    runs_dir = p / 'runs'
    for d in sorted(runs_dir.iterdir()) if runs_dir.is_dir() else []:
        mf = d / 'manifest.json'
        if not mf.is_file(): continue
        m = read(mf)
        owner_file = d / '.claim' / 'owner.json'
        owner = read(owner_file)['agent'] if owner_file.exists() else '-'
        rows.append(f'{d.name}\t{m["agent"]}\t{m["environment"]}\t{m["status"]}\t{m["created_at"][:10]}\tclaim:{owner}\tgoal: {m.get("goal", "")}')
    print('\n'.join(rows) if rows else 'No runs yet.')

def latest_results(p):
    """Latest result per case across every run of the product, any agent."""
    latest = {}
    runs_dir = p / 'runs'
    for d in sorted(runs_dir.iterdir()) if runs_dir.is_dir() else []:
        if not (d / 'manifest.json').is_file(): continue
        for f in (d / 'results').glob('*/*.json'):
            item = read(f) | {'run': d.name}
            if item['case'] not in latest or item['recorded_at'] > latest[item['case']]['recorded_at']:
                latest[item['case']] = item
    return latest

def cmd_status(p, c):
    latest = latest_results(p)
    lines = [f'# {c["name"]} status', '', 'Latest recorded result per case across all runs and both agents. Not a release decision.', '',
             '| Case | Status | Run | Agent | Recorded | Note |', '|---|---|---|---|---|---|']
    counts = {s: 0 for s in STATUSES}
    for case in read(p / 'cases/catalog.json'):
        item = latest.get(case['id'])
        status = item['status'] if item else 'not-run'
        counts[status] = counts.get(status, 0) + 1
        note = '' if not item else ('[redacted]' if secret_hit(item['note']) else item['note'].replace('|', '\\|').replace('\n', ' '))
        lines.append(f'| {case["id"]} | {status} | {item["run"] if item else "-"} | {item["agent"] if item else "-"} | {item["recorded_at"][:19] if item else "-"} | {note} |')
    lines += ['', 'Counts: ' + ', '.join(f'{s}={counts.get(s, 0)}' for s in STATUSES), '', f'Generated {now()}']
    out = p / 'coordination' / 'latest-status.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines)); print(f'\nWritten to {out}')

def cmd_doctor(p, c):
    print(f'# {c["name"]} ({p.name})')
    for name in ('staging', 'production'):
        env = c['environments'].get(name, {})
        if not env.get('enabled'):
            print(f'{name}: not configured'); continue
        try: scope_active(env); state = f'active until {env.get("expires_at", "?")}'
        except ValueError: state = f'EXPIRED at {env.get("expires_at", "?")}'
        print(f'{name}: {env["url"]} | build {env["build"]} | actions {",".join(env["approved_actions"])} | {state}')
    gaps = onboarding_gaps(p)
    print('onboarding: ' + ('complete' if not gaps else 'incomplete (' + ', '.join(gaps) + ')'))
    runs_dir = p / 'runs'
    runs = [d for d in sorted(runs_dir.iterdir()) if (d / 'manifest.json').is_file()] if runs_dir.is_dir() else []
    open_claims = [d.name for d in runs if (d / '.claim' / 'owner.json').exists()]
    print(f'runs: {len(runs)} total | open claims: {", ".join(open_claims) if open_claims else "none"}')
    for agent in AGENTS:
        mine = [d for d in runs if read(d / 'manifest.json')['agent'] == agent]
        print(f'last {agent} run: {mine[-1].name if mine else "none"}')
    index = p / 'findings' / 'INDEX.md'
    rows = [l for l in index.read_text().splitlines() if l.startswith('|') and not l.startswith('|---') and not l.startswith('| ID')] if index.is_file() else []
    print(f'findings indexed: {len(rows)}')
    identity = ROOT / 'local' / 'identity.json'
    print('identity: ' + ('present' if identity.exists() else 'missing (run init)'))

def cmd_verify_sources(r):
    saved = read(r / 'source-hashes.json')
    changed = []
    for rel, digest in saved.items():
        f = ROOT / rel
        if not f.is_file(): changed.append(f'{rel}: MISSING'); continue
        if hashlib.sha256(f.read_bytes()).hexdigest() != digest: changed.append(f'{rel}: CHANGED')
    if changed:
        print('Source drift since run creation:'); print('\n'.join(changed)); return 2
    print('All recorded sources unchanged since run creation.'); return 0

def main(argv=None):
    ap = argparse.ArgumentParser(description='QAForge orchestration; see module docstring for the product.json contract.')
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('list'); sub.add_parser('validate')
    rp = sub.add_parser('runs'); rp.add_argument('product')
    for name, help_text in (('doctor', 'readiness: env scope, expiry, onboarding gaps, claims, last runs, findings'),
                            ('status', 'rollup: latest result per case across all runs and agents')):
        sp = sub.add_parser(name, help=help_text); sp.add_argument('product')
    sub.add_parser('init', help='first-run bootstrap: check tools, create local/identity.json, validate, run tests')
    ss = sub.add_parser('session', help='start your Claude Code or Codex CLI in this repo with the session brief preloaded')
    ss.add_argument('product'); ss.add_argument('--agent', choices=AGENTS, required=True)
    ss.add_argument('--print-only', action='store_true', help='print the starting prompt instead of launching the CLI')
    cfg = sub.add_parser('configure')
    cfg.add_argument('product'); cfg.add_argument('--env', choices=['staging', 'production'], required=True)
    cfg.add_argument('--url', required=True); cfg.add_argument('--build', default='unknown')
    cfg.add_argument('--allow-host', action='append', default=[])
    cfg.add_argument('--allow-action', choices=ACTIONS, action='append', default=[])
    cfg.add_argument('--authorized-by', required=True, help='who authorized this assessment')
    cfg.add_argument('--auth-method', required=True, help='how ownership/authorization was confirmed')
    cfg.add_argument('--allow-insecure', action='store_true', help='permit an http:// target (local staging only)')
    cfg.add_argument('--allow-private', action='store_true', help='permit an RFC1918/loopback target (local staging only)')
    cfg.add_argument('--scope-notes', default='URL supplied for this testing session')
    dis = sub.add_parser('disable'); dis.add_argument('product')
    dis.add_argument('--env', choices=['staging', 'production'], required=True)
    for command in ('preflight', 'new-run'):
        sp = sub.add_parser(command); sp.add_argument('product'); sp.add_argument('--env', choices=['staging', 'production'], required=True)
        if command == 'new-run':
            sp.add_argument('--agent', choices=AGENTS, required=True); sp.add_argument('--retest-of', help='run id this run retests after a fix')
            sp.add_argument('--review-of', help='run id this run independently reviews on the same build')
            sp.add_argument('--goal', required=True, help='what is being tested and why; stated and confirmed in chat before this run')
            sp.add_argument('--confirmed-by', required=True, help='who confirmed the testing plan in chat before this run started')
    for command in ('claim', 'release', 'smoke', 'result', 'report', 'close', 'aliases', 'verify-sources'):
        sp = sub.add_parser(command); sp.add_argument('product'); sp.add_argument('--run', required=True)
        if command not in ('report', 'verify-sources'): sp.add_argument('--agent', choices=AGENTS, required=True)
        if command == 'result':
            sp.add_argument('--case', required=True); sp.add_argument('--status', choices=STATUSES, required=True)
            sp.add_argument('--note', required=True); sp.add_argument('--evidence', action='append', default=[])
    a = ap.parse_args(argv)
    if a.command in ('list', 'validate'):
        errors = []
        for p in sorted((ROOT / 'products').iterdir()):
            if not (p / 'product.json').exists(): continue
            c = read(p / 'product.json')
            errors.extend(f'{p.name}: {e}' for e in validate_config(c))
            if a.command == 'list': print(f'{c["slug"]}: {c["name"]} [{c.get("priority", "unset")}]')
        if errors: fail('\n'.join(errors))
        if a.command == 'validate': print('All product configurations valid; unset session URLs are expected.')
        return 0
    if a.command == 'runs':
        cmd_runs(product(a.product)); return 0
    if a.command == 'init':
        return cmd_init()
    if a.command == 'session':
        return cmd_session(product(a.product), a.agent, a.print_only)
    if a.command in ('doctor', 'status'):
        p = product(a.product); c = read(p / 'product.json')
        (cmd_doctor if a.command == 'doctor' else cmd_status)(p, c); return 0
    p = product(a.product); c = read(p / 'product.json')
    if a.command == 'configure':
        host = urlparse(a.url).hostname
        granted = datetime.now(timezone.utc)
        env = {'url': a.url, 'enabled': True,
               'allowed_hosts': sorted(set(([host.lower()] if host else []) + [h.lower() for h in a.allow_host])),
               'approved_actions': sorted(set(['read-only'] + a.allow_action)), 'build': a.build,
               'scope_notes': a.scope_notes, 'authorized_by': a.authorized_by, 'auth_method': a.auth_method,
               'granted_at': granted.isoformat(), 'expires_at': (granted + timedelta(days=SCOPE_TTL_DAYS)).isoformat(),
               'insecure': bool(a.allow_insecure), 'allow_private': bool(a.allow_private)}
        check_target(a.url, env)
        check_host_safety(host, env)
        c['environments'][a.env] = env
        errors = validate_config(c)
        if errors: fail('\n'.join(errors))
        save(p / 'product.json', c)
        print(f'Configured {c["name"]} {a.env}. Scope expires {env["expires_at"]}. New runs snapshot this scope.'); return 0
    if a.command == 'disable':
        prior = c['environments'].get(a.env, {})
        c['environments'][a.env] = {'url': '', 'enabled': False, 'allowed_hosts': [], 'approved_actions': ['read-only'],
                                    'build': 'unknown',
                                    'scope_notes': f'Disabled {now()}; prior authorization by {prior.get("authorized_by", "unrecorded")}'}
        errors = validate_config(c)
        if errors: fail('\n'.join(errors))
        save(p / 'product.json', c)
        print(f'Disabled {c["name"]} {a.env}. Existing runs keep their snapshot; new runs are blocked until reconfigured.'); return 0
    if a.command in ('preflight', 'new-run'):
        env = c['environments'][a.env]
        if not env['enabled']: fail('Session URL not configured. Use configure with the user-supplied target.')
        scope_active(env)
        check_target(env['url'], env)
        check_host_safety(urlparse(env['url']).hostname, env)
        if a.command == 'preflight':
            print('Read-only smoke ready. Product assessment requires confirmed requirements, fixtures, and role scope.')
            if env['build'] == 'unknown': print('Build unknown: release confidence is limited.')
            gaps = onboarding_gaps(p)
            if gaps: print('Onboarding incomplete (' + ', '.join(gaps) + '). Only baseline lab cases are justified until these are confirmed.')
            return 0
        if a.retest_of: run_path(p, a.retest_of)
        if a.review_of: run_path(p, a.review_of)
        prefix = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        index = 1
        while True:
            rid = f'{prefix}_{index:03d}_{a.agent}'
            r = p / 'runs' / rid
            try: r.mkdir(); break
            except FileExistsError: index += 1
        for folder in (f'results/{a.agent}', 'evidence', 'private'): (r / folder).mkdir(parents=True)
        save(r / 'manifest.json', {'schema_version': 1, 'product_name': c['name'], 'product': a.product, 'agent': a.agent, 'environment': a.env, 'scope': env, 'created_at': now(), 'status': 'open', 'fixture_namespace': f'{a.product}-{rid}', 'retest_of': a.retest_of, 'review_of': a.review_of, 'goal': a.goal, 'confirmed_by': a.confirmed_by, 'standard_version': '1.0'})
        save(r / 'cases.json', read(p / 'cases/catalog.json'))
        sources = [f for folder in (ROOT / 'standards', p / 'guides', p / 'docs') for f in folder.rglob('*') if f.is_file()]
        save(r / 'source-hashes.json', {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sources})
        write_run_docs(r, p, c, a, env)
        ensure_findings_index(p)
        (r / 'peer-review.md').write_text((ROOT / 'templates/peer-review.md').read_text())
        (r / 'cleanup.md').write_text('# Cleanup\nNo fixtures created by the runner. Document all subsequent mutations and cleanup here.\n')
        append_session_log(p, a.agent, a.confirmed_by, a.env, rid, a.goal)
        claim(r, a.agent); report(r); print(f'Created and claimed: {rid}'); return 0
    r = run_path(p, a.run)
    if a.command == 'claim': claim(r, a.agent)
    elif a.command == 'release':
        require_owner(r, a.agent)
        (r / '.claim/owner.json').unlink(); (r / '.claim').rmdir()
    elif a.command == 'smoke': return smoke(r, a.agent)
    elif a.command == 'result': record(r, a.agent, a.case, a.status, a.note, a.evidence)
    elif a.command == 'verify-sources': return cmd_verify_sources(r)
    elif a.command == 'report':
        if read(r / 'manifest.json')['status'] != 'open': fail('Closed reports are preserved')
        report(r)
    elif a.command == 'close':
        m = require_owner(r, a.agent); report(r)
        m.update(status='closed', closed_at=now()); save(r / 'manifest.json', m)
        (r / '.claim/owner.json').unlink(); (r / '.claim').rmdir()
    elif a.command == 'aliases':
        require_owner(r, a.agent)
        path = ROOT / 'local/identity.json'
        if not path.exists(): fail('Configure local/identity.json first; see local/README.md')
        identity = read(path); address = identity.get('gmail_address', '')
        if not re.fullmatch(r'[^+\s@]+@(?:gmail\.com|googlemail\.com)', address, re.I): fail('Provide a base Gmail address without a plus suffix')
        user, domain = address.split('@')
        personas = read(p / 'fixtures/personas.json')['personas']
        if not personas: fail('Confirm and populate product personas first')
        aliases = []
        for index, role in enumerate(personas, 1):
            tag = f'qa-{p.name[:12]}-{r.name}-{index}'
            local = f'{user}+{tag}'
            if len(local) > 64: fail('Alias too long; use a shorter dedicated inbox name')
            aliases.append({'persona': role, 'email': f'{local}@{domain}', 'created': False})
        (r / 'private').chmod(0o700)
        save(r / 'private/aliases.json', {'aliases': aliases, 'note': 'Proposed addresses only; no account creation or email was performed.'})
        (r / 'private/aliases.json').chmod(0o600)
        print('Proposed aliases saved in the ignored run private/aliases.json file; no accounts created.')
    return 0

if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        print(f'ERROR: {e}', file=sys.stderr); sys.exit(2)
