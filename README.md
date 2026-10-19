# Radu TV – ghid TV
Fișierul `epg.json` conține programul zilei pentru canalele românești din aplicația Radu TV (LG webOS), extras zilnic de pe
cinemagia.ro de un job GitHub Actions (`.github/workflows/epg.yml`). Aplicația îl descarcă de pe raw.githubusercontent.com.
`channels.json`: id canal (iptv-org) -> pagina cinemagia. Orele sunt ora României; aplicația le convertește local.
