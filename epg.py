#!/usr/bin/env python3
"""Builds epg.json for Radu TV: today's schedule per channel, scraped from cinemagia.ro (times in Romanian time).
channels.json maps iptv-org channel id -> cinemagia page slug. Runs daily in GitHub Actions; the TV fetches epg.json."""
import json, re, time, urllib.request, html, sys
from concurrent.futures import ThreadPoolExecutor

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
ROW = re.compile(r'class="ora">\s*<div>(\d{1,2}):(\d{2})</div>[\s\S]*?class="title">\s*([^<]+?)\s*</div>')

def grab(item):
    cid, slug = item
    for attempt in range(3):
        try:
            req = urllib.request.Request(f'https://www.cinemagia.ro/program-tv/{slug}/', headers={'User-Agent': UA, 'Accept-Language': 'ro'})
            page = urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'replace')
            out, prev, off = [], -1, 0
            for h, m, title in ROW.findall(page):
                t = int(h) * 60 + int(m)
                if t < prev - 60: off += 1440            # rolled past midnight
                prev = t; out.append([t + off, html.unescape(re.sub(r'\s+', ' ', title)).strip()])
            return cid, out
        except Exception as e:
            time.sleep(3 * (attempt + 1)); err = e
    print('fail', cid, err, file=sys.stderr); return cid, []

def main():
    chans = json.load(open('channels.json', encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=4) as ex: res = dict(ex.map(grab, chans.items()))
    ok = {k: v for k, v in res.items() if v}
    if len(ok) < max(10, len(chans) // 4):
        sys.exit(f'prea putine canale cu program ({len(ok)}/{len(chans)}); nu suprascriu epg.json')
    data = {'day': time.strftime('%Y-%m-%d'), 'tz': 'Europe/Bucharest', 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'channels': ok}
    json.dump(data, open('epg.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(ok)}/{len(chans)} canale cu program, {sum(len(v) for v in ok.values())} emisiuni')

if __name__ == '__main__':
    main()
