#!/usr/bin/env python3
"""Probes every stream in channels.json with curl (same behaviour as a browser: redirects, TLS, timeouts)
and classifies each channel:
  OK      HLS playlist or raw MPEG-TS answered
  DEAD    DNS/connection failure, timeout, or 400/404/410: the address is gone
  GEO?    403: may be geo-blocked only where this script runs (RO vs BE), keep and test on the TV
  TEMP    5xx/429 or odd 200: server trouble, keep
Usage: python3 -I channels/check-streams.py [--write-exclude] [--conservative] [group-id ...]
  --conservative   for GitHub Actions (US datacenter): only DNS failures and HTTP 404/410 count as DEAD; timeouts and
                   refused connections may be a geo firewall, so they are kept
  --write-exclude  adds DEAD ids to channels.config.json (country groups: "exclude"; curated groups: removed from "channels")
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, 'channels.config.json')
UA = 'Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36 WebAppManager'
DEAD_CURL = {6, 7, 35, 52, 56}   # dns, refused, tls, empty reply, recv failure
DEAD_HTTP = {400, 404, 410}

CONSERVATIVE = '--conservative' in sys.argv

def probe(url):
    r = subprocess.run(['curl', '-s', '-L', '-A', UA, '--max-time', '12', '--range', '0-4095',
                        '-o', '/dev/stdout', '-w', '\n@@%{http_code} %{content_type}', url], capture_output=True)
    out = r.stdout
    body, _, meta = out.rpartition(b'@@')
    parts = meta.decode('utf-8', 'replace').split(' ', 1)
    code = int(parts[0] or 0); ctype = parts[1] if len(parts) > 1 else ''
    if b'#EXTM3U' in body[:4096]: return 'OK', 'hls'
    if code == 200 and (ctype.startswith('video/') or body[:1] == b'G'): return 'OK', 'ts'
    if r.returncode == 28 and body: return 'OK', 'ts'          # kept streaming until the timeout: live TS
    if CONSERVATIVE:
        if r.returncode == 6: return 'DEAD', 'curl 6 (dns)'
        if code in (404, 410): return 'DEAD', f'HTTP {code}'
        if r.returncode or code in DEAD_HTTP: return 'TEMP', f'curl {r.returncode} HTTP {code}'
    if r.returncode in DEAD_CURL or r.returncode == 28 and not body: return 'DEAD', f'curl {r.returncode}'
    if code in DEAD_HTTP: return 'DEAD', f'HTTP {code}'
    if code == 403: return 'GEO?', 'HTTP 403'
    return 'TEMP', f'HTTP {code} {ctype}'.strip()

def check(ch):
    if ch.get('twitch'): return ch, 'OK', 'twitch (resolved on the TV)'
    st, why = probe(ch['url'])
    if st != 'OK' and ch['alt']:
        st2, why2 = probe(ch['alt'])
        if st2 == 'OK': return ch, 'OK', 'alt ' + why2
        why += ' | alt: ' + why2
        if st2 != 'DEAD': st = st2 if st == 'DEAD' else st
    return ch, st, why

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    write = '--write-exclude' in sys.argv
    data = json.load(open(os.path.join(ROOT, 'channels.json'), encoding='utf-8'))
    only = set(args)
    dead_by_group = {}
    for g in data['groups']:
        if only and g['id'] not in only: continue
        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(check, g['channels']))
        bad = [(c, st, why) for c, st, why in results if st != 'OK']
        print(f"== {g['name']}: {len(g['channels']) - len(bad)}/{len(g['channels'])} OK")
        for c, st, why in sorted(bad, key=lambda x: x[1]):
            print(f"   {st:<5} {c['id']:<34} {c['name']:<30} {why}")
        dead_by_group[g['id']] = [c['id'].split('@')[0] for c, st, _ in bad if st == 'DEAD']
    if write:
        cfg = json.load(open(CONFIG, encoding='utf-8'))
        for g in cfg['groups']:
            dead = set(dead_by_group.get(g['id'], []))
            if not dead: continue
            if 'channels' in g:
                g['channels'] = [it for it in g['channels'] if (it if isinstance(it, str) else it['channel']) not in dead]
            else:
                g['exclude'] = sorted(set(g.get('exclude', [])) | dead)
        json.dump(cfg, open(CONFIG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print('config updated: excluded', sum(len(v) for v in dead_by_group.values()), 'dead channels')

if __name__ == '__main__':
    main()
