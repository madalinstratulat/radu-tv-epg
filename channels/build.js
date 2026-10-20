#!/usr/bin/env node
// Builds channels.json (fetched by the Radu TV app at start) from the iptv-org API using the rules in channels.config.json.
// Usage: node channels/build.js [--refresh]   (runs daily in GitHub Actions, see .github/workflows/channels.yml)
'use strict';
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const RADIO_MIRRORS = ['at1', 'nl1', 'de1', 'fi1'].map(m => 'https://' + m + '.api.radio-browser.info/json/stations/search?');
const RADIO_UA = 'RaduTV/1.0 (personal webOS IPTV app)';

const ROOT = path.join(__dirname, '..');
const CACHE = path.join(__dirname, 'cache');
const API = 'https://iptv-org.github.io/api/';
const MAX_AGE_MS = 24 * 3600 * 1000;
const refresh = process.argv.includes('--refresh');

function download(url) {
  return new Promise((resolve, reject) => {
    (url.startsWith('http:') ? http : https).get(url, { headers: { 'User-Agent': RADIO_UA } }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) return resolve(download(res.headers.location));
      if (res.statusCode !== 200) return reject(new Error(url + ' -> HTTP ' + res.statusCode));
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    }).on('error', reject);
  });
}

async function load(name) {
  fs.mkdirSync(CACHE, { recursive: true });
  const file = path.join(CACHE, name + '.json');
  const fresh = fs.existsSync(file) && Date.now() - fs.statSync(file).mtimeMs < MAX_AGE_MS;
  if (!fresh || refresh) {
    process.stdout.write('downloading ' + name + '.json... ');
    fs.writeFileSync(file, await download(API + name + '.json'));
    console.log('ok');
  }
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function twitchUsers(logins) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ query: 'query($l:[String!]){users(logins:$l){login displayName profileImageURL(width:300)}}', variables: { l: logins } });
    const req = https.request('https://gql.twitch.tv/gql', { method: 'POST', headers: { 'Client-ID': 'kimne78kx3ncx6brgo4mv6wki5h1ko', 'Content-Type': 'text/plain' } }, res => {
      const chunks = []; res.on('data', c => chunks.push(c));
      res.on('end', () => { const out = {}; try { (JSON.parse(Buffer.concat(chunks).toString('utf8')).data.users || []).forEach(u => { if (u) out[u.login] = u; }); } catch (e) {} resolve(out); });
    });
    req.on('error', () => resolve({})); req.end(body);
  });
}

function qualityOf(s) { const m = /^(\d+)/.exec(s.quality || ''); return m ? parseInt(m[1], 10) : 0; }

// iptv-org points AntenaPlay channels at the lowest variant; the master playlist next to it is adaptive.
function fixUrl(url) { return url.replace(/(antenaplay\.ro\/[^\s]*)_600k\.m3u8$/, '$1.m3u8'); }

async function main() {
  const config = JSON.parse(fs.readFileSync(path.join(ROOT, 'channels.config.json'), 'utf8'));
  const [channels, feeds, streams, logos] = await Promise.all(['channels', 'feeds', 'streams', 'logos'].map(load));

  const chById = new Map(channels.map(c => [c.id, c]));
  const feedsBy = new Map();
  feeds.forEach(f => { if (!feedsBy.has(f.channel)) feedsBy.set(f.channel, []); feedsBy.get(f.channel).push(f); });
  const streamsBy = new Map();
  streams.forEach(s => { if (!streamsBy.has(s.channel)) streamsBy.set(s.channel, []); streamsBy.get(s.channel).push(s); });
  // All usable logo candidates per channel, best first: channel-wide before feed-specific, raster before SVG.
  const logoBy = new Map();
  logos.forEach(l => {
    if (!l.in_use || !l.url) return;
    if (!logoBy.has(l.channel)) logoBy.set(l.channel, []);
    logoBy.get(l.channel).push(l);
  });
  logoBy.forEach(list => list.sort((a, b) => (a.feed === null ? 0 : 1) - (b.feed === null ? 0 : 1) || (a.format === 'SVG' ? 1 : 0) - (b.format === 'SVG' ? 1 : 0)));
  const LOGO_DIR = path.join(ROOT, 'logos');
  const wanted = [];
  function safeName(id) { return id.replace(/[^A-Za-z0-9._-]/g, '_'); }
  function localLogo(id) {
    const file = safeName(id) + '.png';
    const cands = (logoBy.get(id) || []).map(l => l.url);
    if (cands.length) wanted.push({ id, file, urls: cands });
    return fs.existsSync(path.join(LOGO_DIR, file)) ? 'logos/' + file : '';
  }

  function languagesOf(id, feed) {
    const fl = feedsBy.get(id) || [];
    const f = (feed && fl.find(x => x.id === feed)) || fl.find(x => x.is_main) || fl[0];
    return f ? f.languages : [];
  }
  // ISO 639-3 (iptv-org) -> 2-letter codes used by the subtitle service
  const LANG2 = { ron: 'ro', eng: 'en', fra: 'fr', rus: 'ru', nld: 'nl', deu: 'de', spa: 'es', ita: 'it', por: 'pt', tur: 'tr', ukr: 'uk', hun: 'hu', pol: 'pl', ell: 'el', bul: 'bg', srp: 'sr', ara: 'ar', jpn: 'ja', zho: 'zh', kor: 'ko' };
  function lang2(id, feed) { const l = languagesOf(id, feed)[0]; return LANG2[l] || ''; }

  function pickStreams(id, feed, allowGeo) {
    let list = streamsBy.get(id) || [];
    if (feed) { const sub = list.filter(s => s.feed === feed); if (sub.length) list = sub; }
    list = list.filter(s => allowGeo || !s.labels.includes('Geo-blocked'));
    return list.slice().sort((a, b) => {
      const needsA = a.user_agent || a.referrer ? 1 : 0, needsB = b.user_agent || b.referrer ? 1 : 0;
      if (needsA !== needsB) return needsA - needsB;
      return qualityOf(b) - qualityOf(a);
    });
  }

  function entry(id, feed, nameOverride, allowGeo) {
    const c = chById.get(id);
    if (!c || c.closed || c.is_nsfw) return null;
    const list = pickStreams(id, feed, allowGeo);
    if (!list.length) return null;
    return {
      id: feed ? id + '@' + feed : id,
      name: nameOverride || c.name,
      logo: localLogo(id),
      url: fixUrl(list[0].url),
      alt: list[1] ? fixUrl(list[1].url) : '',
      cat: c.categories[0] || '',
      q: list[0].quality || '',
      lang: lang2(id, feed)
    };
  }

  // radio-browser lookups are cached so rebuilds do not hammer the API
  const radioCacheFile = path.join(CACHE, 'radio.json');
  const radioCache = fs.existsSync(radioCacheFile) ? JSON.parse(fs.readFileSync(radioCacheFile, 'utf8')) : {};
  async function radioStation(st) {
    const key = st.cc + '|' + st.name;
    if (!radioCache[key] || refresh) {
      const q = new URLSearchParams({ name: st.name, countrycode: st.cc, order: 'votes', reverse: 'true', limit: '1', hidebroken: 'true' });
      let list = null, lastErr = null;
      for (const base of RADIO_MIRRORS) {
        try { list = JSON.parse(await download(base + q.toString())); break; } catch (e) { lastErr = e; }
      }
      if (!list) throw lastErr;
      radioCache[key] = list[0] || null;
    }
    return radioCache[key];
  }
  const LANG_BY_CC = { RO: 'ro', MD: 'ro', BE: 'fr', FR: 'fr', RU: 'ru' };

  const out = { format: 1, generated: new Date().toISOString(), defaultFavorites: config.defaultFavorites || [], groups: [] };
  for (const g of config.groups) {
    let items = [];
    if (g.twitch) {
      // Twitch: display name + profile picture from Twitch's web API; the stream address is resolved on the TV at play time
      const users = await twitchUsers(g.twitch);
      for (const login of g.twitch) {
        const u = users[login.toLowerCase()];
        if (!u) { console.warn('  skip (twitch user not found): ' + login); continue; }
        const id = 'twitch:' + u.login, file = safeName(id) + '.png';
        if (u.profileImageURL) wanted.push({ id, file, urls: [u.profileImageURL] });
        items.push({ id, name: u.displayName || u.login, logo: fs.existsSync(path.join(LOGO_DIR, file)) ? 'logos/' + file : '', url: '', alt: '', cat: 'twitch', q: '', lang: 'ro', twitch: u.login });
      }
    } else if (g.stations) {
      for (const st of g.stations) {
        const r = await radioStation(st);
        if (!r) { console.warn('  skip (radio not found): ' + st.cc + ' ' + st.name); continue; }
        const id = 'radio:' + r.stationuuid;
        const file = safeName(id) + '.png';
        wanted.push({ id, file, urls: r.favicon ? [r.favicon] : [] });   // no favicon: find-logos.py tries the station's site
        items.push({ id, name: st.display || st.name, logo: fs.existsSync(path.join(LOGO_DIR, file)) ? 'logos/' + file : '',
          url: r.url_resolved || r.url, alt: '', cat: 'radio', q: [r.codec, r.bitrate ? r.bitrate + 'k' : ''].filter(Boolean).join(' '), lang: LANG_BY_CC[st.cc] || '' });
      }
      fs.writeFileSync(radioCacheFile, JSON.stringify(radioCache));
    } else if (g.channels) {
      for (const it of g.channels) {
        const spec = typeof it === 'string' ? { channel: it } : it;
        const e = entry(spec.channel, spec.feed, spec.name, !!g.allowGeoBlocked);
        if (e) items.push(e); else console.warn('  skip (no stream): ' + JSON.stringify(spec));
      }
    } else {
      const ex = g.excludeName ? new RegExp(g.excludeName, 'i') : null;
      for (const c of channels) {
        if (c.country !== g.country) continue;
        if (g.exclude && g.exclude.includes(c.id)) continue;
        if (ex && ex.test(c.name)) continue;
        if (g.languages && !languagesOf(c.id).some(l => g.languages.includes(l))) continue;
        if (g.categories && !c.categories.some(cat => g.categories.includes(cat))) continue;
        const e = entry(c.id, null, null, !!g.allowGeoBlocked);
        if (e) items.push(e);
      }
      items.sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }));
      if (g.first) {
        // Well-known channels first, in the configured order; the rest stay alphabetical.
        const rank = new Map(g.first.map((id, i) => [id, i]));
        items.sort((a, b) => (rank.has(a.id) ? rank.get(a.id) : 1e9) - (rank.has(b.id) ? rank.get(b.id) : 1e9));
      }
    }
    out.groups.push({ id: g.id, name: g.name, channels: items });
    console.log(g.name + ': ' + items.length + ' canale');
  }

  fs.writeFileSync(path.join(ROOT, 'channels.json'), JSON.stringify(out));
  fs.writeFileSync(path.join(CACHE, 'logos-wanted.json'), JSON.stringify(wanted));
  const missing = wanted.filter(w => !fs.existsSync(path.join(LOGO_DIR, w.file))).length;
  console.log('wrote channels.json' + (missing ? ' (' + missing + ' logos missing: run channels/fetch-logos.py, then build again)' : ''));
}

main().catch(e => { console.error(e); process.exit(1); });
