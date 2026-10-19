#!/usr/bin/env python3
"""Re-probes the channels that were excluded from channels.config.json because their streams were dead, against the
current iptv-org stream list. Known stations (La Une, RTL TVI, Comedy Central...) come back as soon as a working
address appears. Usage: python3 -I channels/recheck-excluded.py [--restore] [group-id ...]
  --restore  removes the revived ids from "exclude"; then run channels/build.js again"""
import json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
cs = import_module('check-streams')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, 'channels.config.json')

def main():
    only = {a for a in sys.argv[1:] if not a.startswith('--')}
    cfg = json.load(open(CONFIG, encoding='utf-8'))
    streams = json.load(urllib.request.urlopen('https://iptv-org.github.io/api/streams.json', timeout=60))
    by = {}
    for s in streams:
        if s.get('channel') and s.get('url'): by.setdefault(s['channel'], []).append(s['url'])
    revived = {}
    for g in cfg['groups']:
        ids = g.get('exclude', [])
        if not ids or (only and g['id'] not in only): continue
        def test(cid):
            res = [(u, cs.probe(u)) for u in by.get(cid, [])]
            ok = [u for u, (st, _) in res if st == 'OK']
            return cid, ok, res
        with ThreadPoolExecutor(max_workers=10) as ex: results = list(ex.map(test, ids))
        alive = [(cid, ok) for cid, ok, _ in results if ok]
        print(f"== {g['name']}: {len(alive)} din {len(ids)} excluse au din nou flux")
        for cid, ok, res in results:
            print(f"   {'OK  ' if ok else 'dead'} {cid:<30} " + (ok[0][:80] if ok else (f'{len(res)} adrese, niciuna nu merge' if res else 'nicio adresa in iptv-org')))
        revived[g['id']] = [cid for cid, _ in alive]
    if '--restore' in sys.argv:
        n = 0
        for g in cfg['groups']:
            back = set(revived.get(g['id'], []))
            if back: g['exclude'] = [c for c in g['exclude'] if c not in back]; n += len(back)
        json.dump(cfg, open(CONFIG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'config: {n} canale scoase din exclude; ruleaza node channels/build.js')

if __name__ == '__main__':
    main()
