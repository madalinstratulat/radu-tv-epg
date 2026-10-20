# Radu TV – ghid TV
Fișierul `epg.json` conține programul zilei pentru canalele românești din aplicația Radu TV (LG webOS), extras zilnic de pe
cinemagia.ro de un job GitHub Actions (`.github/workflows/epg.yml`). Aplicația îl descarcă de pe raw.githubusercontent.com.
`epg.channels.json`: id canal (iptv-org) -> sursele de ghid. `channels.json` este LISTA de canale pentru aplicatie (channels/build.js).


## Format 2 (19 oct 2026)
`epg.json` = `{format: 2, day, from, to, generated, channels: {id: [[start_epoch_minutes_utc, title], ...]}}`, azi + maine (calendar romanesc). TV-ul converteste la fusul orar detectat. Surse per canal, in ordine: `xmltv` (epgshare01.online, RO1/FR1), `api` (programtv.ro), `ptv` (program-tv.ro). `epg.channels.json` (maparea pentru ghid; `channels.json` e lista de canale) se regenereaza cu `python3 epg.py --names DIR && python3 map.py DIR`.

## Media
`themes/fireplace.webp`: fireplace loop for the radio "Șemineu" scene, made from Mixkit clip 2707 (Mixkit Free License: free for use in projects, no attribution required, not to be redistributed as stock footage). 960x540, 15 fps, crossfaded so it loops seamlessly.
