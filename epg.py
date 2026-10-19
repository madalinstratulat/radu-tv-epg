#!/usr/bin/env python3
"""Builds epg.json for Radu TV: today's schedule per channel (times in Romanian time, minutes since midnight;
entries after midnight are 1440+). Two sources, both reachable from GitHub Actions (cinemagia.ro blocks datacenter IPs):
  api: the JSON API behind programtv.ro (a mirror of cinemagia's data; the day runs 07:00 -> 06:00 next day)
  ptv: program-tv.ro channel pages (its own data; used when the api has nothing for the channel today)
channels.json maps iptv-org channel id -> {api: slug, ptv: CODE}. Runs daily in GitHub Actions; the TV fetches epg.json."""
import json, re, html, time, urllib.parse, urllib.request, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
PTV_ROW = re.compile(r'<time class="progentry_time[^"]*" itemprop="startDate" content="[^"]*">\s*(\d{1,2}):(\d{2})</time>[\s\S]*?'
                     r'<h3 class="[^"]*progentry_progtitle[^"]*" itemprop="name"><a[^>]*>(?:<strong>)?([^<]+?)(?:</strong>)?</a>')

def ro_today():
    try:
        from zoneinfo import ZoneInfo; return datetime.now(ZoneInfo('Europe/Bucharest')).strftime('%Y-%m-%d')
    except Exception: return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%Y-%m-%d')

def get(url, accept='text/html'):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'ro'}), timeout=25).read().decode('utf-8', 'replace')

def pack(rows):
    """[(hh, mm, title)] in broadcast order -> [[minutes, title]] with midnight rollover."""
    out, prev, off = [], -1, 0
    for h, m, title in rows:
        title = re.sub(r'\s+', ' ', html.unescape(title)).strip()
        if not title: continue
        t = int(h) * 60 + int(m)
        if t < prev - 60: off += 1440
        prev = t; out.append([t + off, title])
    return out

def from_api(slug):
    rows = json.loads(get(f'https://programtv.ro/api/tv-program/{urllib.parse.quote(slug)}?date={DAY}&isToday=true', 'application/json'))
    items = []
    for r in rows:
        m = re.fullmatch(r'(\d{1,2}):(\d{2})', (r.get('ora') or '').strip())
        if m: items.append((m.group(1), m.group(2), r.get('numeEmisiune') or ''))
    return pack(items)

def from_ptv(code):
    page = get(f'https://program-tv.ro/program-tv/{code}')
    i = page.find('class="progarea"')                 # skip the "ACUM" box above the list
    return pack(PTV_ROW.findall(page[i:] if i > 0 else page))

def grab(item):
    cid, src = item
    for name, fn in (('api', from_api), ('ptv', from_ptv)):
        if not src.get(name): continue
        for attempt in range(3):
            try:
                out = fn(src[name])
                if out: return cid, out
                break
            except Exception as e:
                time.sleep(3 * (attempt + 1)); print('retry', cid, name, e, file=sys.stderr)
    return cid, []

def main():
    global DAY; DAY = ro_today()
    chans = json.load(open('channels.json', encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=4) as ex: res = dict(ex.map(grab, chans.items()))
    ok = {k: v for k, v in res.items() if v}
    if len(ok) < max(10, len(chans) // 4):
        sys.exit(f'prea putine canale cu program ({len(ok)}/{len(chans)}); nu suprascriu epg.json')
    data = {'day': DAY, 'tz': 'Europe/Bucharest', 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'channels': ok}
    json.dump(data, open('epg.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(ok)}/{len(chans)} canale cu program, {sum(len(v) for v in ok.values())} emisiuni; fara program: {sorted(set(chans) - set(ok))}')

if __name__ == '__main__':
    main()
