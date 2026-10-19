#!/usr/bin/env python3
"""Downloads channel logos listed in channels/cache/logos-wanted.json into logos/ as small PNGs.
Logo hosts (imgur etc.) refuse requests coming from the TV, so logos are bundled at build time.
Usage: python3 -I channels/fetch-logos.py   (run after channels/build.js, then build again)"""
import io, json, os, subprocess, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'logos')
WANTED = os.path.join(ROOT, 'channels', 'cache', 'logos-wanted.json')
MAX_W, MAX_H = 220, 130
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'

def fetch(url):
    # many hosts only serve images with a same-site referer
    origin = urllib.parse.urlsplit(url); referer = f'{origin.scheme}://{origin.netloc}/'
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': referer, 'Accept': 'image/*,*/*;q=0.8'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(), r.headers.get('Content-Type', '')

def dark_tile_if_light(im):
    """A white/very light logo is invisible on the cream box: put it on a dark rounded tile inside the PNG."""
    px = im.getdata(); n = 0; lum = 0.0
    for r, g, b, a in px:
        if a > 128: n += 1; lum += (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    if n == 0 or lum / n < 0.62: return im
    from PIL import ImageDraw
    pad_x, pad_y = max(10, im.width // 10), max(8, im.height // 6)
    tile = Image.new('RGBA', (im.width + 2 * pad_x, im.height + 2 * pad_y), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, tile.width - 1, tile.height - 1], radius=max(8, tile.height // 8), fill=(41, 43, 38, 255))
    tile.paste(im, (pad_x, pad_y), im)
    return tile

def to_png(data, ctype, url):
    if ctype.startswith('image/svg') or url.lower().split('?')[0].endswith('.svg'):
        data = subprocess.run(['rsvg-convert', '-w', str(MAX_W * 2), '-h', str(MAX_H * 2), '-a'], input=data, capture_output=True, check=True).stdout
    im = Image.open(io.BytesIO(data)).convert('RGBA')
    if im.size == (161, 81): raise ValueError('imgur "image does not exist" placeholder')
    bbox = im.getbbox()                      # drop transparent margins so every logo fills its box the same way
    if bbox: im = im.crop(bbox)
    im = dark_tile_if_light(im)
    im.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True); return buf.getvalue()

def work(item):
    dest = os.path.join(OUT, item['file'])
    if os.path.exists(dest): return None
    for url in item['urls']:
        try:
            data, ctype = fetch(url)
            png = to_png(data, ctype, url)
            with open(dest, 'wb') as f: f.write(png)
            return (item['id'], 'ok')
        except Exception as e:
            last = f'{type(e).__name__}: {str(e)[:60]}'
    return (item['id'], 'FAIL ' + last)

def main():
    os.makedirs(OUT, exist_ok=True)
    wanted = json.load(open(WANTED))
    todo = [w for w in wanted if not os.path.exists(os.path.join(OUT, w['file']))]
    print(f'{len(wanted)} logos wanted, {len(todo)} to download')
    with ThreadPoolExecutor(max_workers=2) as ex:
        results = [r for r in ex.map(work, todo) if r]
    fails = [r for r in results if r[1] != 'ok']
    print(f'downloaded {len(results) - len(fails)}, failed {len(fails)}')
    for f in fails: print('  ', f[0], f[1])

if __name__ == '__main__':
    main()
