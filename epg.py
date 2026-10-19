#!/usr/bin/env python3
"""Builds epg.json for Radu TV: the schedule of every mapped channel for today and tomorrow (Romanian calendar),
as [[start_epoch_minutes, title], ...] in UTC - the TV converts to wherever it is. Runs once a day in GitHub Actions.
Sources, in order per channel (channels.json: iptv-org id -> {xmltv, api, ptv}):
  xmltv: XMLTV files (FILE#channel_id): epgshare01.online RO1/FR1 (RO, FR), iptvx.one (MD); several days ahead, absolute times
  api:   the JSON API behind programtv.ro (mirror of cinemagia; cinemagia itself blocks datacenter IPs), one day per call
  ptv:   program-tv.ro channel pages (own data; 403 from GitHub, works from a home connection)
python3 epg.py --names DIR  also dumps each XMLTV file's channel list (for map.py)."""
import json, re, html, gzip, io, time, urllib.parse, urllib.request, sys, os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
RO = ZoneInfo('Europe/Bucharest')
XMLTV_URLS = {'RO1': 'https://epgshare01.online/epgshare01/epg_ripper_RO1.xml.gz',
              'FR1': 'https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz',
              'IPTVX': 'https://iptvx.one/epg/epg_noarch.xml.gz'}      # ~36 MB, 4300 channels incl. Moldova 1/2, Pro TV Chisinau, TV8, Jurnal TV
PTV_ROW = re.compile(r'<time class="progentry_time[^"]*" itemprop="startDate" content="[^"]*">\s*(\d{1,2}):(\d{2})</time>[\s\S]*?'
                     r'<h3 class="[^"]*progentry_progtitle[^"]*" itemprop="name"><a[^>]*>(?:<strong>)?([^<]+?)(?:</strong>)?</a>')

def get(url, accept='text/html', binary=False):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'ro'}), timeout=120).read()
    return r if binary else r.decode('utf-8', 'replace')

def clean(t): return re.sub(r'^(?:х/ф|т/с|д/ф|м/ф|д/с|м/с)\s*', '', re.sub(r'\s+', ' ', html.unescape(t or '')).strip())   # iptvx.one genre prefixes

# ---- xmltv -----------------------------------------------------------------------------------------------------
xml_cache = {}
def xmltv_file(name):
    """{channel_id: [[epoch_min, title]]} for one epgshare file, restricted to the window; downloaded once."""
    if name in xml_cache: return xml_cache[name]
    out = {}
    try:
        for ev, el in ET.iterparse(gzip.GzipFile(fileobj=io.BytesIO(get(XMLTV_URLS[name], '*/*', True)))):
            if el.tag != 'programme': continue
            try:
                t = int(datetime.strptime(el.get('start'), '%Y%m%d%H%M%S %z').timestamp() // 60)
                if WIN0 <= t < WIN1: out.setdefault(el.get('channel'), []).append([t, clean(el.findtext('title'))])
            except Exception: pass
            el.clear()
        print(f'xmltv {name}: {len(out)} canale in fereastra', file=sys.stderr)
    except Exception as e:
        print(f'xmltv {name}: {e}', file=sys.stderr)
    xml_cache[name] = out; return out

def from_xmltv(ref):
    name, cid = ref.split('#', 1)
    return xmltv_file(name).get(cid, [])

# ---- programtv.ro api / program-tv.ro (local Romanian clock -> absolute) ------------------------------------------
def ro_abs(day, rows):
    """rows = [(hh, mm, title)] in broadcast order for a Romanian day (may run past midnight) -> absolute minutes."""
    out, prev, off = [], -1, 0
    for h, m, title in rows:
        title = clean(title)
        if not title: continue
        t = int(h) * 60 + int(m)
        if t < prev - 60: off += 1
        prev = t
        start = datetime.combine(day + timedelta(days=off), datetime.min.time(), RO) + timedelta(minutes=t)
        out.append([int(start.timestamp() // 60), title])
    return out

def from_api(slug):
    out = []
    for day in (DAY0, DAY0 + timedelta(days=1)):
        rows = json.loads(get(f'https://programtv.ro/api/tv-program/{urllib.parse.quote(slug)}?date={day:%Y-%m-%d}&isToday=true', 'application/json'))
        items = []
        for r in rows:
            m = re.fullmatch(r'(\d{1,2}):(\d{2})', (r.get('ora') or '').strip())
            if m: items.append((m.group(1), m.group(2), r.get('numeEmisiune') or ''))
        out += ro_abs(day, items)
    return out

def from_ptv(code):
    page = get(f'https://program-tv.ro/program-tv/{code}')
    i = page.find('class="progarea"')                 # skip the "ACUM" box above the list
    return ro_abs(DAY0, PTV_ROW.findall(page[i:] if i > 0 else page))

# ---- main --------------------------------------------------------------------------------------------------------
def grab(cid, src):
    for name, fn in (('xmltv', from_xmltv), ('api', from_api), ('ptv', from_ptv)):
        if not src.get(name): continue
        for attempt in range(3):
            try:
                items = [p for p in fn(src[name]) if WIN0 <= p[0] < WIN1]
                if items:
                    items.sort(); dedup = []
                    for p in items:
                        if not dedup or p[0] != dedup[-1][0]: dedup.append(p)
                    return dedup
                break
            except Exception as e:
                time.sleep(3 * (attempt + 1)); print('retry', cid, name, e, file=sys.stderr)
    return []

def main():
    global DAY0, WIN0, WIN1
    now = datetime.now(RO); DAY0 = now.date()
    start = datetime.combine(DAY0, datetime.min.time(), RO)
    WIN0 = int(start.timestamp() // 60); WIN1 = int((start + timedelta(days=2)).timestamp() // 60)   # today + tomorrow (RO)
    if '--names' in sys.argv:
        d = sys.argv[sys.argv.index('--names') + 1]; os.makedirs(d, exist_ok=True)
        for f in XMLTV_URLS:
            names = {}; cnt = {}
            for ev, el in ET.iterparse(gzip.GzipFile(fileobj=io.BytesIO(get(XMLTV_URLS[f], '*/*', True)))):
                if el.tag == 'channel': names[el.get('id')] = clean(el.findtext('display-name'))
                elif el.tag == 'programme': cnt[el.get('channel')] = cnt.get(el.get('channel'), 0) + 1; el.clear()
            json.dump({k: [v, cnt.get(k, 0)] for k, v in names.items()}, open(os.path.join(d, f + '.names.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        return
    chans = json.load(open('channels.json', encoding='utf-8'))
    for src in chans.values():                         # fetch the xmltv files first, sequentially (they are big)
        if src.get('xmltv'): xmltv_file(src['xmltv'].split('#')[0])
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex: res = dict(zip(chans, ex.map(lambda kv: grab(*kv), chans.items())))
    ok = {k: v for k, v in res.items() if v}
    if len(ok) < max(10, len(chans) // 4):
        sys.exit(f'prea putine canale cu program ({len(ok)}/{len(chans)}); nu suprascriu epg.json')
    data = {'format': 2, 'day': f'{DAY0:%Y-%m-%d}', 'from': WIN0, 'to': WIN1, 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'channels': ok}
    json.dump(data, open('epg.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(ok)}/{len(chans)} canale cu program, {sum(len(v) for v in ok.values())} emisiuni; fara program: {sorted(set(chans) - set(ok))}')

if __name__ == '__main__':
    main()
