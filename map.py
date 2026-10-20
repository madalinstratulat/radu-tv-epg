#!/usr/bin/env python3
"""Rebuilds epg.channels.json: iptv-org channel id -> guide sources, matched by name against the app's channel list
(../LgIptv/app/channels.js) and the XMLTV channel lists saved by epg.py --names. Keeps the existing api/ptv slugs.
Usage: python3 map.py <dir with RO1.names.json FR1.names.json BE2.names.json>"""
import json, re, sys, unicodedata, os

def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\((?:hd|hd / 4k)\)', '', s); s = re.sub(r'\b(hd|tv|channel)\b', '', s)
    return re.sub(r'[^a-z0-9]', '', s)

FILES = {'ro': ['RO1'], 'md': ['RO1', 'IPTVX'], 'fr': ['FR1'], 'be': ['FR1']}
MANUAL = {'PROTVChisinau.md': 'IPTVX#pro-tv-md', 'TV8.md': 'IPTVX#tv8-md', 'Moldova1.md': 'IPTVX#moldova-1', 'Moldova2.md': 'IPTVX#moldova-2',
          'ExclusivTV.md': 'IPTVX#tnt-bravo-moldova', 'NorocTV.md': 'IPTVX#noroc-tv-md'}
NOT = {'MagicTV.ro', 'PROTVChisinau.md'}   # Magic.be is a different station; PRO TV Chisinau has its own schedule
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'LgIptv', 'app', 'channels.js'), encoding='utf-8').read()
app = json.loads(src[src.index('{'):src.rindex('}') + 1])
old = json.load(open('epg.channels.json', encoding='utf-8'))
names = {f: json.load(open(os.path.join(sys.argv[1], f + '.names.json'), encoding='utf-8')) for f in ['RO1', 'FR1', 'IPTVX']}
out = {}
for g in app['groups']:
    if g['id'] not in FILES: continue
    for c in g['channels']:
        if c.get('cat') == 'radio': continue
        e = {k: v for k, v in old.get(c['id'], {}).items() if k in ('api', 'ptv')}
        if c['id'] in MANUAL: e['xmltv'] = MANUAL[c['id']]
        elif c['id'] not in NOT:
            for f in FILES[g['id']]:
                cands = [cid for cid, (n, cnt) in names[f].items() if cnt > 0 and norm(n) == norm(c['name'])]
                if cands: e['xmltv'] = f + '#' + sorted(cands, key=lambda x: ('.HD.' in x, x.count('.'), x))[0]; break
        if e: out[c['id']] = e
json.dump(out, open('epg.channels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out), 'canale;', sum('xmltv' in e for e in out.values()), 'xmltv,', sum('api' in e for e in out.values()), 'api')
