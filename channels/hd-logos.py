#!/usr/bin/env python3
"""High-resolution logos for the radio screen (the regular ones are max 220x130). Looks up each station's page on
Wikipedia (infobox image), downloads the original, renders SVGs, trims and saves logos/hd/<file>.png (max 600x400).
Wikimedia rate-limits hard: slow pace with backoff. Usage: python3 -I channels/hd-logos.py"""
import io, json, os, subprocess, time, urllib.parse, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'RaduTV/1.0 (personal TV app; logo lookup; github.com/madalinstratulat) python-urllib'}
PAGES = {   # station name in channels.json -> (wikipedia language, page title)
  'Radio ZU': ('ro', 'Radio ZU'), 'Kiss FM': ('ro', 'Kiss FM (România)'), 'Europa FM': ('ro', 'Europa FM'), 'Digi FM': ('ro', 'Digi FM'),
  'Pro FM': ('ro', 'Pro FM'), 'Magic FM': ('ro', 'Magic FM (România)'), 'Rock FM': ('ro', 'Rock FM (România)'), 'Virgin Radio': ('ro', 'Virgin Radio România'),
  'Radio Guerrilla': ('ro', 'Radio Guerrilla'), 'Radio Romania Actualitati': ('ro', 'Radio România Actualități'),
  'Radio Romania Muzical': ('ro', 'Radio România Muzical'), 'Radio Contact': ('fr', 'Radio Contact'), 'Bel RTL': ('fr', 'Bel RTL'),
  'NRJ Belgique': ('fr', 'NRJ Belgique'), 'Nostalgie Belgique': ('fr', 'Nostalgie (Belgique)'), 'Fun Radio Belgique': ('fr', 'Fun Radio (Belgique)'),
  'RTBF La Première': ('fr', 'La Première (RTBF)'), 'RTBF VivaCité': ('fr', 'VivaCité'), 'RTBF Classic 21': ('fr', 'Classic 21'),
}
SKIP_WORDS = ('coverage', 'acoperire', 'map', 'harta', 'studio', 'building')   # infobox images that are not logos

def get(url, tries=6):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            time.sleep(30 * (i + 1))
    raise RuntimeError('rate limited')

def main():
    d = json.load(open(os.path.join(ROOT, 'channels.json'), encoding='utf-8'))
    radios = {c['name']: c for g in d['groups'] for c in g['channels'] if c.get('cat') == 'radio'}
    for name, (lang, title) in PAGES.items():
        c = radios.get(name)
        if not c or not c.get('logo'): print('skip', name); continue
        out = os.path.join(ROOT, 'logos', 'hd', os.path.basename(c['logo']))
        if os.path.exists(out): continue
        try:
            q = urllib.parse.urlencode({'action': 'query', 'prop': 'pageimages', 'piprop': 'original', 'titles': title, 'redirects': 1, 'format': 'json'})
            pg = list(json.loads(get(f'https://{lang}.wikipedia.org/w/api.php?' + q))['query']['pages'].values())[0]
            src = (pg.get('original') or {}).get('source')
            if not src or any(w in src.lower() for w in SKIP_WORDS): print('no logo', name, src or ''); time.sleep(5); continue
            data = get(src)
            if src.lower().split('?')[0].endswith('.svg'):
                data = subprocess.run(['rsvg-convert', '-w', '1200', '-a'], input=data, capture_output=True, check=True).stdout
            im = Image.open(io.BytesIO(data)).convert('RGBA')
            bbox = im.getbbox(); im = im.crop(bbox) if bbox else im
            im.thumbnail((600, 400), Image.LANCZOS); im.save(out, 'PNG', optimize=True)
            print('ok', name, im.size, src.split('/')[-1].split('?')[0])
        except Exception as e: print('fail', name, e)
        time.sleep(8)

if __name__ == '__main__':
    main()
