"""Writes the site's three entry pages from app.html: /, /windows/, /mac/ (same app, own title, link preview and start view).
Run: python3 -I site-src/build.py"""
import os
SRC = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.join(SRC, '..', 'site')
PAGES = {
    '':         dict(P='tv', PATH='/', OG='og.png?v=4', TITLE='Radu TV',
                     DESC='Televiziune românească și radio pe Android TV, Google TV, Windows și Mac. Instalare cu codul 3204554 în aplicația Downloader.'),
    'windows':  dict(P='windows', PATH='/windows/', OG='og-windows.png?v=2', TITLE='Radu TV pentru Windows',
                     DESC='Televiziune românească și radio pe calculator. Peste 140 de canale, ghid TV pe 3 zile, gratuit. Pentru Windows 10 și 11.'),
    'mac':      dict(P='mac', PATH='/mac/', OG='og-mac.png?v=2', TITLE='Radu TV pentru Mac',
                     DESC='Televiziune românească și radio pe Mac. Peste 140 de canale, ghid TV pe 3 zile, gratuit.'),
}
tpl = open(os.path.join(SRC, 'app.html'), encoding='utf-8').read()
for folder, v in PAGES.items():
    html = tpl
    for k, val in v.items(): html = html.replace('{{' + k + '}}', val)
    assert '{{' not in html
    out = os.path.join(SITE, folder, 'index.html'); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(html); print('wrote', os.path.relpath(out, SITE))
