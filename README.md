# Radu TV – ghid TV
Fișierul `epg.json` conține programul zilei pentru canalele românești din aplicația Radu TV (LG webOS), extras zilnic de pe
cinemagia.ro de un job GitHub Actions (`.github/workflows/epg.yml`). Aplicația îl descarcă de pe raw.githubusercontent.com.
`channels.json`: id canal (iptv-org) -> pagina cinemagia. Orele sunt ora României; aplicația le convertește local.


## Format 2 (19 oct 2026)
`epg.json` = `{format: 2, day, from, to, generated, channels: {id: [[start_epoch_minutes_utc, title], ...]}}`, azi + maine (calendar romanesc). TV-ul converteste la fusul orar detectat. Surse per canal, in ordine: `xmltv` (epgshare01.online, RO1/FR1), `api` (programtv.ro), `ptv` (program-tv.ro). `channels.json` se regenereaza cu `python3 epg.py --names DIR && python3 map.py DIR`.
