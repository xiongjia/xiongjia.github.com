---
title: Film & TV Archive (Douban Sync) — Design
created: 2026-09-27
updated: 2026-09-27
tags: [design, film-tv, douban, mkdocs, r2]
---

# Film & TV Archive (Douban Sync) — Design

Archive the Douban film & TV records (watched / watching, never the "wish" list) into
this site and present them as browsable pages plus statistics. The plan and its task
list live in [`plans/film-tv.md`](./plans/film-tv.md); this document holds the **decided
design** and the **measured spike findings**, so the plan only keeps goals, scope,
tasks, acceptance criteria and risks.

**Measured scale** (2026-09-27, full list walk — §1.2): **4292 watched**
(`type=movie` 3092 + `type=tv` 1200), **0 watching**. The plan's "≈8000" was an old
estimate that included the wish list; this archive excludes it.

## 1. Data sources & spike findings

### 1.1 Login & cookies (CDP)

- The Douban login page has a slider CAPTCHA, so **form login cannot be automated** — the
  only path is reusing a real browser session.
  `shared/douban_auth.py` + `scripts/film_tv_login.py` (`poe film-tv-login`) implement it
  and were verified end to end.
- Flow: probe `http://127.0.0.1:<port>/json/version` first; **if the peer is not a browser,
  abort** (never switch ports, never send CDP to an unrelated local process). With no
  attachable browser, launch local Edge/Chrome with
  `--remote-debugging-port=<port> --user-data-dir=.cache/film-tv/browser-profile/`
  (Chromium 136+ refuses CDP on the default profile; the isolated profile also keeps the
  developer's daily login untouched).
- Bring the Douban page to the front, let the developer log in by hand (QR works — measured
  `last_login_way=qr`), then poll `Storage.getCookies` on the **browser-level** endpoint
  (`Network.getAllCookies` does not exist there), keep `douban.com` cookies and write
  `.cache/douban-cookies.json` (0600, with `captured_at` / `user_id`).
- Raw CDP via `websocket-client`, **with `suppress_origin=True`** (an `Origin` header makes
  the browser answer 403). The dependency is a main dependency but imported **lazily**
  inside `shared/douban_auth.py`, so builds and CI never touch the browser stack.
- The browser's stderr is redirected to `.cache/film-tv/login.log`: macOS crashpad always
  writes an un-suppressible `Operation not permitted` warning.
- **Login gate (differs from the plan's assumption):** `https://www.douban.com/mine/` is the
  reliable probe — logged in it redirects 302 to `/people/<id>/`, expired/anonymous gets
  **403**; `https://www.douban.com/people/` answers **404** either way and cannot be used.
- Credential precedence: `DOUBAN_COOKIE` (explicit fallback; inherited by child processes)
  over `DOUBAN_COOKIES_FILE` (default `.cache/douban-cookies.json`). Logs mask `dbcl2` / `ck`.

**Session policy — the cookie is only sent for requests that need private account data:**

| Request                         | Session       |
| ------------------------------- | ------------- |
| Collection lists `collect`/`do` | **anonymous** |
| Subject `/subject/<id>/`        | logged in     |
| Album `photos?type=R`           | logged in     |
| Image CDN `img*.doubanio.com`   | anonymous     |

- Anonymous list pages are readable and **field-identical** to the logged-in variant, which
  only adds per-item 「修改 / 删除」 controls: the anonymous HTML is a **strict subset**
  (0 removed lines in a diff of the item list).
- Anonymous subject/album requests (even with a `bid` cookie and full browser headers) get
  302 to `sec.douban.com`; that challenge page is a JavaScript loader, so plain `requests`
  never passes it.
- Consequence: **the list walk — the high-frequency, repeated part — costs zero account
  calls.** Account calls are limited to subject pages (+ on-demand albums), which is at
  least one request per record because personal rating / tags / comment only exist there.
- If the collection ever becomes private (0 items anonymously, or a login redirect), the
  sync **falls back to the cookie automatically and warns**.
- **Measured limit of anonymous walks:** ~86 pages of anonymous paging get challenged by
  `sec.douban.com` (the first full pass is 143 pages), while the same walk with the account
  session finished all 145 pages in the spike. So day-to-day 1–3 page incremental walks are
  safe anonymously, and **the first full pass switches to the account session midway** (the
  script prints a notice; `--full` runs once). After a challenge, anonymous access from that
  IP stays restricted for a while.
- **2026-09-27 observation (the fallback is normal now, not rare):** the anonymous session was
  challenged on the **very first** list page, so a whole 117-page walk ran on the account
  session. The walk now (a) retries the anonymous session once per challenge and starts every
  tab cookie-free again, and (b) **counts** the pages it had to take through the account
  (`walk: … [account session: 117/117 pages]`) so that cost is visible instead of silently
  assumed to be zero. Once a challenge has been seen, **an empty list page can be Douban's
  soft-throttle answer** — see the walk guard in §4.

### 1.2 Collection lists (`collect` / `do`)

`https://movie.douban.com/people/<id>/collect` (watched) and `/do` (watching), with
`?start=N&sort=time&rating=all&filter=all&mode=list` — **`mode=list` gives 30 rows/page**,
`mode=grid` only 15 plus one poster thumbnail.

| Item        | Measured                 |
| ----------- | ------------------------ |
| Page size   | list 30 rows, grid 15    |
| End marker  | HTTP 200 + 0 rows        |
| Total       | page header shows 4292   |
| Paging      | `?start=0,30,60…`        |
| Cross-check | 4292 unique ids, 0 dupes |
| Cost        | ≈78 KB / ≈1 s per page   |
| Session     | anonymous (§1.1)         |

- The `<h1>` is `我看过的影视(4292)` and `<span class="subject-num">1-30 / 4292</span>`; the
  `type` tabs split it exactly (3092 + 1200), so the two-tab walk loses nothing.
- Past the last page Douban answers **HTTP 200 with an empty list**, not 404 — the end of the
  collection can only be detected by an empty page.
- `start=4290` returns the final 2 rows; a full walk is ≈144 pages ≈7 minutes at 2 s pacing.
- An anonymous session is enough; the logged-in variant only adds per-row edit controls.

Item markup (`mode=list`):

```text
<li id="list<subject_id>" class="item">            # the last row is class="item last"
  <div class="item-show[ deleted]">                # deleted = subject removed on Douban
    <div class="title"><a href="https://movie.douban.com/subject/<id>/">标题 / 原名</a>
      [<span class="playable">[可播放]</span>]</div>
    <div class="date">[<span class="rating<N>-t"></span>&nbsp;&nbsp;]2019-12-01</div>
  </div>
  <div id="grid<id>" data-cid="…" class="hide comment-item">
    <div class="grid-date"><span class="intro">上映日期 / 主演 / 地区 / 导演 / 片长 / 类型 / 编剧 / 语言</span><br/>
      [<span class="tags">标签: a b c</span>] </div>
    [<div class="comment">我的短评</div>]           # only in the 在看 list
  </div>
</li>
```

Fields the list page provides — and therefore the only fields allowed in the incremental
fingerprint:

| Field         | Source                            |
| ------------- | --------------------------------- |
| `id`          | `li id="list…"` / title link      |
| `title`       | `.title a` (`标题 / 原名`)        |
| `user_rating` | `.date .ratingN-t`                |
| `marked_at`   | `.date` text                      |
| `tags`        | `.tags` (space separated)         |
| `comment`     | `.comment`                        |
| `status`      | URL (`collect` / `do`)            |
| `type`        | URL tab `?type=movie` / `=tv`     |
| `deleted`     | `.item-show.deleted`              |
| `intro`       | `.intro` (unstructured one-liner) |

- The last row of every page is `class="item last"` — matching only `class="item"` silently
  drops one item per page (this bit the spike).
- An unrated item has **no** rating span at all, but still has a date.
- `tags` appears on roughly two thirds of the rows; a missing tag line does not mean "no
  tags".
- `comment` only exists on the 在看 list; **the 看过 list no longer exposes short comments**
  (`short-note` appears 0 times), which is the fingerprint deviation in §7.
- `type` comes from the tab, and both tabs partition the list exactly
  (3092 + 1200 = 4292), so walking two tabs costs the same as walking once and yields `type`
  for free.

The `/do` template matches `collect`; its rows have no rating span and may carry
`<div class="comment">`. This account has 0 watching rows, so that structure was verified
against a public account's page (readable anonymously).

### 1.3 Subject pages (field spec)

`https://movie.douban.com/subject/<id>/` — anonymous requests get 302 to `sec.douban.com`,
so a **cookie is required**.

| Field                     | Where                            | Hit  |
| ------------------------- | -------------------------------- | ---- |
| `douban_score`            | `#interest_sectl` · `v:average`  | 9/10 |
| `douban_score_count`      | `#interest_sectl` · `v:votes`    | 9/10 |
| `genres`                  | `#info` · `类型` / `v:genre`     | 9/10 |
| `regions` (raw)           | `#info` · `制片国家/地区`        | 9/10 |
| `languages`               | `#info` · `语言`                 | 9/10 |
| `runtime`                 | `#info` · `片长` / `v:runtime`   | 8/10 |
| `episodes`                | `#info` · `集数` (tv)            | 1/10 |
| `episode_runtime`         | `#info` · `单集片长` (tv)        | 1/10 |
| release dates             | `#info` · `首播` / `上映日期`    | 9/10 |
| `credits.directors`       | `#info` · `导演`                 | 9/10 |
| `credits.writers`         | `#info` · `编剧`                 | 9/10 |
| `credits.casts`           | `#info` · `主演`                 | 9/10 |
| my rating / date / status | `#interest_sect_level`           | 9/10 |
| my tags                   | `#interest_sect_level` · `标签:` | 5/10 |
| my comment                | free text after the tags         | 4/10 |
| cover fallback            | `#mainpic img`                   | —    |

(`Hit` = records among the 10 spike samples that carried the field; the misses are the deleted
subject plus tv entries without a runtime.)

Selector details worth keeping in one place:

- `#info` is a `<br/>`-separated row list with **two markup variants**
  (`<span><span class='pl'>导演</span>: <span class='attrs'>…</span></span>` and
  `<span class="pl">类型:</span> 剧情 / 犯罪`); multi-values are separated by `/`.
- `casts` is truncated to the **first 10** names at build time (§6); the page itself lists
  25+.
- My own tags arrive space-separated (`标签:Movie ENU Drama`); my short comment is the bare
  `<span>` after that tag span.
- The main poster URL can be upgraded from `s_ratio_poster` to `l` (1080 wide) by token
  swap.

Classification signals (the orthogonal `type` / `category` split is §6):

- `type` is authoritative from the list tab; the subject page cross-checks it
  (`集数` / `首播` rows plus `status_word = 这部电视剧`, 6/6 sampled).
- `category` comes from the `类型` (genre) row.
- Counterexample: a variety show is **not** necessarily `type=tv` — 《第74届NHK红白歌会》
  (genres 音乐 / 歌舞 / 真人秀) is `type=movie` with `status_word=这部电影`, so `category`
  must be derived from genres and never inferred from `type`.
- **Not available:** `seasons` and `episode_progress` (no `季数` row, no progress marker
  anywhere). They stay `null` rather than being invented; Douban models each season as its
  own subject anyway.

### 1.4 Photo album (cover candidates)

`https://movie.douban.com/subject/<id>/photos?type=R` (`R` = posters), **logged in** (§1.1).

- 30 posters per page, header `共161张`, `?start=30` to page; **default order = by likes**
  (a better candidate order than by time).
- Each item: `<li data-id="480747492"><div class="cover"><a href="…/photos/photo/480747492/"> <img src="https://img3.doubanio.com/view/photo/m/public/p480747492.jpg">` plus
  `<div class="name">正式海报 美国 135回应</div>`.
- Sizes (same `p<photo_id>`, different token): `m` = 540×800 (84 KB JPEG),
  `l` = 1080×1600 (249 KB). Covers are taken from `l` and capped to long edge ≤ 800 with
  WebP q80 → **≈72 KB per cover**.
- **Default = one cover, zero extra requests:** `#mainpic img` on the subject page is the
  current main poster; swapping its `s_ratio_poster` token for `l` yields the 1080×1513
  original (verified). The subject page is fetched anyway (§1.3), so the first pass never
  touches the album — saving 4292 account requests.
- **More candidates on demand:** `poe sync-film-tv --covers 8 --only <slug>` fetches the
  album for that one record; existing candidates are never deleted. Image downloads go to
  the CDN and do not count as account calls.
- **Budget:** first pass 1 cover × 72 KB ≈ **0.3 GB**; topping up to 3 covers ≈ **0.9 GB**.
  Only recent years are mirrored locally; the rest lives on R2 only.
- Existing files are skipped; only Douban's own image hosts (`img*.doubanio.com`) are
  allowed; file names use the slug/id and index only.

### 1.5 Failure modes

- Anonymous subject / album requests → 302 to `sec.douban.com` (JS challenge, `requests`
  cannot pass); collection lists are readable anonymously for public profiles.
- Read timeouts do happen (one aborted the spike's full walk) → the sync needs **retry with
  backoff (max 2)** and resumable state. `429`/`503` follow the same policy; a CAPTCHA or
  `403` aborts immediately (no hammering).
- A subject removed on Douban turns its list row into `<div class="item-show deleted">`
  (title may become the `未知电影` placeholder) with no date or rating, and the subject page
  is gone → the record is kept and tagged `meta.missing_since` (§2).
- `--limit` / `--pages` semantics are in §4. Account-call pacing: 2 s for subject pages,
  0.5 s for covers (the number of subject requests **is** the account exposure).

## 2. Data model (block ownership)

One record = everything known about one subject. Block ownership decides what a sync may
touch:

| Block             | Owner           | Sync rule                            |
| ----------------- | --------------- | ------------------------------------ |
| Douban fields     | script          | rewritten wholesale; hand edits lost |
| `slug` / `covers` | script (sticky) | appended only, never recomputed      |
| `user:`           | human           | never touched                        |
| `meta:`           | script          | bookkeeping, not published as-is     |

`generated_at` is a header comment of the year file, not a record field.

```yaml
# generated_at: 2026-09-27T14:30  # refreshed only when the body changes; comment-only
- id: "1292052"          # merge key — a field, never part of a file or directory name
  title: 肖申克的救赎
  original_title: The Shawshank Redemption
  year: 1994                    # release year (a field/stat, not the storage split)
  type: movie                   # movie | tv, from the list tab
  category: feature             # orthogonal to type (§6)
  status: collect               # collect | do
  user_rating: 5                # my Douban rating; unrated = null, never 0
  douban_score: 9.7             # public average (display only)
  douban_score_count: 2830000
  marked_at: "2008-06-01"       # Douban mark date → drives the year file
  douban_comment: 希望让人自由。 # my short comment (subject page interest block)
  tags: [Movie, ENU, Drama]     # my Douban tags (space separated)
  genres: [剧情, 犯罪]          # Douban wording, not normalized
  regions: [美国]               # normalized short name via taxonomy.yml
  languages: [英语]             # Douban wording
  runtime: 142                  # minutes; null for tv or missing
  credits:
    directors: [弗兰克·德拉邦特]
    casts: [蒂姆·罗宾斯, 摩根·弗里曼]   # first 10 only (§6)
    writers: [弗兰克·德拉邦特]
  # seasons / episodes / episode_progress: tv only; episodes from 集数, the other two unavailable
  slug: shawshank-redemption    # sticky; used only for share links (?id=<slug>)
  covers:                       # sticky, archive-root relative, keyed by Douban id
    - covers/1292052/01.webp
    - covers/1292052/02.webp
  douban_url: https://movie.douban.com/subject/1292052/
  user:                         # human block
    cover: covers/1292052/02.webp   # empty = first candidate
    hidden_comment: false       # true = keep in yml, drop from pages/JSON
    my_rating: 5                # optional correction of user_rating
    my_tags: [重看, 蓝光]
    watched_at: "2008-06-01"    # optional corrected watch date (drives the year file)
    review: |                   # my review, multi-line
      第一次看是在大学宿舍，之后又重看了两遍。
    hidden: false               # true = keep in yml, hide from pages and JSON
  meta:
    detail_synced_at: "2026-09-27"   # empty = detail still pending
    taxonomy_version: 1
    fingerprint: "a1b2c3d4"          # list-visible fields only
    machine_hash: "9c1e77ab"         # snapshot hash of the machine fields
    missing_since: null
```

- Merge key `id` (falling back to `title`). Records that disappear from Douban are **not
  deleted**: they get `meta.missing_since`, and only `--prune` (a full comparison) removes
  them. A `deleted` list row can be tagged during the walk.
- **Cover re-download bug (fixed 2026-09-27):** after the cover cache key switched from slug
  to Douban id, a cache miss made every sync re-download the main poster as a brand-new
  candidate (`02.webp` / `03.webp`). `ensure_covers` now means: **already referenced and the
  file exists → do nothing**; a referenced file that vanished is refilled **at its own key**;
  new candidates are only appended while below `wanted`.
- **Sticky fields:** `slug` is written once (a title change keeps the share link stable) and
  `covers` is append-only — never reordered or cleared, because that would break every cover
  reference and trigger re-downloads. Cover directories depend on the id, not the slug.
- **Skeleton first:** the list walk stores a record for **every row** (`slug: ""`, detail
  fields `null`, `meta.detail_synced_at: null`); the detail batches fill them in. `slug` and
  covers are allocated on the **first successful detail fetch**, so the slug can use the
  original/alias title instead of an ASCII-mangled Chinese one. A skeleton merge **only
  updates list-visible fields** and never clears existing detail fields.
- **Slug collisions** only affect share links: append `-<year>`, then `-2` / `-3`, and finally
  `-<hash6>`; degenerate slugs (all digits, no letters, too short) are skipped in favour of
  `douban-<id>`.
- Human values win: an empty `user.cover` means `covers[0]`; a set `user.watched_at`
  overrides `marked_at` for the year file (moving the record to another year file).
- **Rating semantics:** `effective_rating = user.my_rating ?? user_rating`, used uniformly by
  cards, `stats.yml` averages and `people.yml` `avg_rating`.
- **Missing-value semantics:** `user_rating` unrated = `null` (never 0), and averages only
  count records with an `effective_rating` while reporting "已评分 N/M";
  `douban_score` / `douban_score_count` / `runtime` / `episodes` / `seasons` /
  `episode_progress` missing = `null` (render blank, skip stats); a missing `marked_at` falls
  back to `user.watched_at`, and with neither the record lives in `movies-undated.yml` /
  `tv-undated.yml` and is listed as "needs a date" by `film-tv-check`.
- **Hand-edit detection:** `meta.machine_hash` hashes every top-level field except `user:` and
  `meta:` (including sticky `slug` / `covers`) in a fixed key order; the next sync or check
  compares it and warns that hand-edited machine fields will be overwritten.
- **`user.hidden` / `user.hidden_comment`** are fixed semantics: the data stays in the yml,
  but pages and generated JSON must exclude it (macros + derive guarantee it, `film-tv-check`
  verifies) — while `stats.yml` / `people.yml` still aggregate hidden records (the data view
  is complete).
- **Fingerprint fields (measured correction):** `title / user_rating / marked_at / status / type / tags / comment (在看 only)`. `douban_comment` and subject-page tags **cannot** be part
  of it: they only exist on the subject page, so including them would make a detail refill look
  like a Douban-side change and clash with "detail fields never reset `detail_synced_at`".
- `type` / `category` stay out of the fingerprint; they are detail-derived fields governed by
  `meta.taxonomy_version` plus a re-classification list.
- `regions` is normalized through `docs/notes/film-tv/data/taxonomy.yml`; `genres` keeps
  Douban's wording.
- `taxonomy.yml` carries both the region aliases and the `category` rules under a single
  `rules_version`. Each record stores the version it was judged with in
  `meta.taxonomy_version`; after a bump `film-tv-check` lists exactly the records whose
  `regions` / `category` would change.

### Field → owner → published

| Field                                              | Owner  | Published                  |
| -------------------------------------------------- | ------ | -------------------------- |
| Douban metadata                                    | script | yml + JSON                 |
| `slug` / `covers`                                  | script | yml + JSON (one cover)     |
| `douban_comment`                                   | script | yml + JSON, unless hidden  |
| `user.review`                                      | human  | yml + JSON                 |
| `user.cover`, `my_rating`, `my_tags`, `watched_at` | human  | yml + effective value      |
| `user.hidden`                                      | human  | yml only, record dropped   |
| `user.hidden_comment`                              | human  | yml only, comment dropped  |
| `meta.*`                                           | script | `pending` / `missing` only |
| `data/person-ids.yml`                              | script | board ids (`douban_id`)    |

Douban metadata = `id`, `title`, `year`, `type`, `category`, `status`, `user_rating`,
`douban_score(_count)`, `marked_at`, `tags`, `genres`, `regions`, `languages`, `runtime`,
`episodes`, `credits`, `douban_url`.

- `user.hidden: true` removes the record from the page JSON **and the shards**, but it is
  still counted by `stats.yml` / `people.yml` (a data-view statistic, not a published one).
- `user.hidden_comment: true` only drops the short comment; `user.review` is always shown.
- `meta.*` never reaches the page except the derived `pending` / `missing` flags.

## 3. Storage vs presentation

- **Storage** (serves diffs, incrementality and hand editing only):
  `docs/notes/film-tv/data/movies-<year>.yml` and `tv-<year>.yml`, plus `movies-undated.yml` /
  `tv-undated.yml`. The year is the **watch year** (`marked_at` / `user.watched_at`); inside a
  file records are date-descending with `id` as a stable tiebreaker.
- **Presentation** (never split by year): `index.md` (overview + statistics), `movies.md`,
  `tv.md`, `people.md`.
- **Front-end data contract** (generated by the backend, committed and shipped):
  - `assets/index.json`: `shard_size`, `shards`, `totals` and
    `months: {YYYY-MM → {shard, offset, count, by_type}}`; `by_type` lets the movies/tv pages
    count their own scope. (The **local** mirror prefix is not in this file: the macros emit it
    page-relative into the markup, and cover URLs carry the bucket base URL.)
  - `assets/shard-0001.json…`: 200 records per file, time-descending, each with `count`,
    `first_date` and `last_date` self-check fields; the first screen reads `shard-0001`.
  - `assets/stats.yml` (totals/distributions) and `assets/people.yml` (people aggregation,
    **bounded**: `works >= 2` and at most 2000 people — one-off bit-part names would balloon
    the file to several MB).
  - All four are produced by `poe film-tv-derive`: **deterministic, timestamp-free, and
    rewritten only when their content changed** (per-file comparison).
  - Cover URLs are **baked into the JSON** because a runtime `fetch` never passes through the
    bucket plugin's HTML rewriting; `derive` therefore resolves
    `extra.bucket.mappings[film-tv].base_url` (including `MKDOCS_BUCKET_BASE_URL[_FILM_TV]`
    overrides). **Switching bucket domains means re-running derive.**
  - **Local fallback:** when a cover is not on R2 yet (typical in local development) the front
    end falls back to the page-relative local mirror
    (`data-cover-local-base` = `extra.film_tv.local_prefix`); local preview shows posters and
    the page never shows a broken image or an error, though the console still logs the failed
    R2 request.
  - Hidden records are excluded from shards; records with a hidden comment simply carry no
    `comment` field. A missing shard or a parse failure raises a **visible banner** instead of
    silently showing fewer records.
- **Sorting and filtering:** watch date / release year / my rating / title; filters for
  `type`, `category`, region, release decade, minimum rating and **person**, plus a search over
  title / original title / director / cast / writer. **Tags are not a filter or a search facet**
  (the archived Douban tags are legacy and inaccurate; the data still shows up as 「我的标签」 in
  the detail dialog).
- **Person directory** (`data/person-ids.yml`): `personage id → display name`, appended by the
  sync from the `#info` person links. Extra person info (original name, avatar, birthday,
  filmography) can be fetched later straight from `https://www.douban.com/personage/<id>/`
  without re-matching by name; `derive` inverts it into `name → id` and writes `douban_id` /
  `douban_url` into `assets/people.yml`. (It is a directory rather than a field on every record
  because 12–25 people × 4292 records would add ~2 MB of redundancy while the directory costs
  about one line per person.)
- **Person name display** (`extra.film_tv.person_name_style`): the original name comes from the
  subject page's `#celebrities` block (`title="中文名 原文名"`, zero extra requests, covering the
  12 main people per page). `hint` (default) flips only **transliterated** names (those whose
  Chinese form contains `·`) to `原文（中文）`; `latin` always prefers the original; `zh` keeps
  Douban's Chinese. A CJK name (杨磊 / Lei Yang) stays Chinese under `hint`, because its "original"
  is just pinyin. An alias table normalizes short names from older records so one person never
  splits into two board rows.
- **Three entry points into a person:** the director/cast/writer names in the detail dialog are
  clickable (filtering the archive to that person, shown as a removable 「影人：…」 chip and kept
  in `?person=<name>` for sharing); the `people.md` board rows link to `../?person=<name>`; and
  the board lives in the nav under `Film & TV → People`.
- **Detail dialog** (no separate pages): cover, metadata, my Douban short comment and
  `user.review` — they are **not alternatives**, both are shown under different headings. A
  `?id=<slug>` deep link opens the dialog directly.
- **Two list views:**
  - **Month paging (default)** — one month of records per screen, with the month navigation in
    the toolbar **above** the list: `‹ 2026-08 | 2026 年 09 月 · 第 1 / 15 个月 | 2026-10 ›`
    (buttons name their destination month and use the compact `YYYY-MM` so the row **never
    wraps**) plus `最新` / `选月份` / `查看全部`. The month set is "months with records under the
    current filter", so paging can never land on an empty month; `?month=YYYY-MM` is shareable.
  - **All records** — a continuous list of 12 records per page with month headings inside the
    page (spilling months are marked 「（续）」) and a 「按月浏览」 button to switch back.
- **Month picker panel** (open by default, `选月份` collapses it; DOM order is
  `banner → nav → calendar → filters → list`, so navigation and the calendar sit above the
  list): **one year at a time**, rotated with `‹` / `›` instead of stacking decades, `2026 年` as
  the title, 12 cells in **6 columns** (4 on narrow screens) each showing month + count, empty
  months dashed/dimmed and still clickable (they jump to the previous month with records), and
  the year follows when a jump crosses years. Counts follow the active filter once every shard
  is loaded.
- The calendar is **navigation, not a filter**: clicking a month jumps to it, empty months jump
  backwards, and a truly empty filter result says "当前筛选没有结果" (distinct from "归档里还没有记录").
  Touching a filter or a sort loads every shard once (~3 MB, filtered in memory) while the
  default view stays lazy.
- **`"undated"` is a pseudo-month, never a date:** the year list behind the calendar rotation
  and the chart's 「按年」 selector is built by `core.calendarYears()`, which only accepts real
  `YYYY-MM` keys (`core.isMonthKey`). Slicing a month key blindly turned the pseudo-month into
  the year `"unda"` and, because the panel is open on page load, the very first render titled
  itself 「unda 年」 until a month was picked (the same slice ran in `film-tv-chart.js`).
- **An entry without a date is not shown as 「未知」; it gets a real date or is dropped:** the
  date is always *my* watch/mark time — the subject page's `#interest_sect_level` date (which is
  why a record's row in \*-undated.yml is a **pending** record, not a broken one), else the
  list row's date, else a hand-set `user.watched_at`. A subject that is **gone** is skipped: it is
  kept in the year yml as an archive entry (`meta.missing_since` + `meta.missing_reason`, nothing
  left to fetch) but `film-tv-derive` leaves a gone **and** dateless record out of the published
  JSON, so the pages have neither an 「未知」 bucket nor an empty 「未知电影」 row. Gone records
  that *do* carry a date stay published (a pruned record was really watched), and a date-less
  record whose subject is still alive is the only case that needs `user.watched_at` by hand —
  `film-tv-check` lists those (`undated` finding, split into pending / gone / needs-a-date).
- **"Gone" is three signals and one confirmation** (`_fetch_detail` / `_mark_gone`): Douban's
  `item-show deleted` row class, an HTTP `404`, or a `200` whose page parses empty (no title, no
  score, no interest block). An empty page is also what a *throttled* session gets, and the mark is
  permanent (a missing record is neither fetched nor published again), so it is re-fetched once
  before it counts — and a record that already **has a date** is never marked gone from an empty
  page: that case is a failure and is retried later. `meta.missing_reason` records why
  (`gone` = subject taken down, `pruned` = the row left my collection); only `pruned` is undone
  automatically when a walk sees the row again, and any successful detail fetch clears both fields
  (a restored subject is a live subject). Records that are gone are **not** pending anywhere:
  `backfill_progress` and `film-tv-check` report them separately (`gone N`), so "pending 0" stays a
  reachable target.
- **Pages and assets:** the section pages contain only a heading plus macro calls;
  `shared/macros/film_tv_macros.py` renders them (`film_tv_page` / `film_tv_stats` / `film_tv_chart` /
  `film_tv_people` / `film_tv_note`). Because mkdocs-macros accepts exactly one local
  `module_name`, `shared/macros/loader.py` is the single entry point that loads the health module and
  this one by path. The front end is `assets/javascripts/film-tv-core.js` (pure helpers,
  node-tested) plus `film-tv.js` (DOM/fetch/dialog) and `film-tv-chart.js`, styled by
  `assets/stylesheets/film-tv.css`; all three are registered for minification.
- **Statistics distributions are collapsible** (the `running.md` pattern): the four
  distributions (category / year / region / type) live in **one** `<details>` (collapsed by
  default, summary `📊 统计分布` with a count hint), while the four overview cards stay visible.
- **AI viewing summary:** `poe update-film-tv-summary` digests `stats.yml` / `people.yml` /
  shards, builds a Chinese prompt, calls the local `pi` CLI and rewrites **only** the
  `<!-- ai-summary:begin --> … <!-- ai-summary:end -->` block of `index.md`, appending
  "本地 AI（model）· date". A failed `pi` call leaves the page untouched; `--dry-run` prints the
  prompt.
- **Watch-volume chart** (index page, below the statistics): **one mermaid `xychart-beta`**, one
  bar per month = that month's total. Mermaid gives real axes, gridlines and self-scaling width
  (measured `width="100%"` in a 701 px container) with the theme's link colour, which reads in
  both palettes. Its limits were both measured: a second `bar` series is drawn **on top of** the
  first (no grouped/stacked bars), and `bar` + `line` assigns the bars a near-white palette
  colour — so the movie/tv split lives in the summary line, not in the bars. Controls: last 12
  months (default) / by year (year rotated with `‹` / `›`) / custom range, clamped to the data.
  The month maths (`monthAdd`, `monthSpan`, `lastMonths`, `chartBuckets`, `chartSummary`) are pure
  helpers in `film-tv-core.js` with node tests. The macro takes a `kind`, which the movies / tv
  pages use for their own volume chart (`film_tv_chart("movie")` renders movie bars only and its
  summary reports the movie share).
- **Dark mode (measured):** interactive elements (calendar year/month cells, pager buttons,
  stat bars) use `--md-typeset-a-color` / `--md-accent-fg-color` and **never
  `--md-primary-fg-color`** (the site's slate palette sets primary to black, which dropped the
  calendar year labels to 1.13 contrast). Secondary text on tinted surfaces uses full-strength
  foreground (4.06 → 6.76 in dark mode). Verification is a computed-style contrast audit in
  headless Chrome with `data-md-color-scheme=slate`, not eyeballing screenshots.
- **Build measurement** (60-record sample, 2026-09-27): `mkdocs build` 6.6 s; a page's HTML is
  47–53 KB and **does not grow with the record count** (the list is client-side); shards are
  ≈750 B/record → **≈3.2 MB at 4292 records**; `site/` totals 35 MB (including
  `mermaid.min.js`). The real 4292-record baseline is re-measured after the phase 4 backfill.
- Changing the file granularity later (per year → per decade) **does not affect the pages**.

## 4. Incremental sync

| Step            | What                              | Cost                               |
| --------------- | --------------------------------- | ---------------------------------- |
| ① Walk lists    | `collect` / `do`, per `type` tab  | anonymous, ≈144 pages full         |
| ② Short-circuit | stop at a page with no changes    | near zero daily                    |
| ③ Fetch details | new/changed records + main cover  | logged in, 1 request each          |
| ④ Merge + write | affected year files, `user:` kept | no network, no diff when unchanged |
| ⑤ Cleanup       | `--prune` marks vanished records  | occasional manual run              |

- **Session split (account protection, evidence in §1.1):** the list walk uses an **anonymous**
  session (zero account calls) while details/albums use the account session; the cookie is never
  attached to list requests. A private collection (0 rows / login redirect) falls back to the
  cookie with a warning.
- **Account budget:** the first pass costs 4292 requests (one subject page per record, main cover
  included); daily increments cost one per new record. Pacing: 2 s per subject page; stop after
  the current batch (`--limit N`, 300 recommended); cached details are never re-fetched; a `403`,
  `429` or CAPTCHA aborts immediately and keeps the progress.
- **Per-tab walks:** `collect?type=movie` and `collect?type=tv` (plus the same for `do`) cost the
  same number of pages as an unfiltered walk and yield `type` for free.
- **No baseline file:** the incremental index is rebuilt from the committed year yml
  (`id → fingerprint`).
- **Newest first:** the lists are already reverse-chronological, so the detail queue starts with
  the newest records; `--limit N` batches them (300 recommended, no hard cap).
- **Resumable:** progress and the detail cache live in the git-ignored
  `.cache/film-tv/state/` (`details/` parsed JSON, `covers.json`, `failures.json`,
  `walk.json`), so a re-run never repeats requests; `--data-quality` reports go to
  `.cache/film-tv/reports/<ts>.json`.
- **Walk progress (`walk.json`)** = `{cursor: {tab → next start}, total: {tab → page-header total}}`. A `--full` walk writes the cursor after every page, so an interrupted first pass
  **resumes** instead of re-requesting 100+ pages; the cursor is cleared when a tab reaches its
  natural end. An incremental run neither reads nor writes it (the newest rows always live on
  the first pages), and `--prune` never resumes (it compares the whole archive against the
  walk — skipping the head would mark it deleted). `total` is what makes the offline
  completeness check possible (`film-tv-check`).
- **An empty page is never "the list ends here" (required by the 2026-09-27 full pass):** an
  empty page mid-list was a soft throttle, and treating it as the end silently dropped the
  oldest ~900 movies — the archive still looked complete (3390 rows vs the 4292 the page
  headers advertised). The walk retries an empty page (`EMPTY_PAGE_RETRIES`) and, while the
  header still advertises more rows than were stored, **aborts with the progress kept** instead
  of finishing quietly.
- A watching-progress change only updates fields and **never resets `detail_synced_at`**, and is
  throttled separately so details are not re-fetched weekly.
- Write-back keeps the record order and the `user:` block; nothing is written when the content is
  unchanged, so a bot/PR diff only shows the records that were added.
- **Argument semantics:** `--limit N` = at most N detail fetches per run (0 = unlimited);
  `--pages M` = at most M list pages **per tab** (independent of `--limit`, unnecessary with the
  default short-circuit); `--covers N` = number of candidates (default 1 = the subject page's main
  poster; values > 1 fetch the album; candidates are only added, never deleted); `--only <slug>`
  processes a single record (ignores `--limit`); `--full` walks every list page without stopping
  early (`--prune` implies it).
- **List fetch resilience (required by the spike):** `ReadTimeout`, connection resets, `429` and
  `503` are retried with exponential backoff (max 2 attempts); a failure after that aborts while
  keeping progress.
- **Completeness is checked, not assumed:** `film-tv-check` compares the live records against
  `sum(walk.json totals)` and reports `walk-total` (error) when the archive is short, plus
  `local-orphan` for local cover files no record references (`poe sync-film-tv --dedupe-covers` repairs those: byte-identical duplicates of a referenced cover in the same
  subject dir are deleted).
- **Cover-map durability:** the `photo_id → covers/<id>/NN.webp` map is persisted **after every
  item**, not only at the 50-item flush — a killed batch used to lose the map for the last
  records, re-download the same poster as the next `NN` and orphan the previous file.
- **Write semantics:** the local yml is written directly (diffable, revertible, consistent with the
  repo's other scripts); `--dry-run` only prints what would be added / updated / migrated / marked
  missing.
- **Comment refresh:** the 看过 short comment only exists on the subject page, so the list
  short-circuit cannot detect "I only edited a comment" — use `--only <slug>` for one record or
  `--refresh-details [N]` to re-read the newest N details, ignoring the fingerprint.

## 5. Covers & the bucket

- Two candidate tiers, to minimise account calls:

  1. **One cover by default:** the subject page's `#mainpic` poster, upgraded to `l`
     (1080×1513) → `01.webp`. The subject page is fetched anyway, so this costs **no extra account
     request**.
  1. **More on demand:** `poe sync-film-tv --covers 8 --only <slug>` fetches the album
     (`photos?type=R`, by likes) → `02.webp…`, only for that record, never deleting existing
     candidates.

- A cover the developer uploads by hand is `user-01.webp` and **never enters `covers`** (that list
  only holds Douban candidates); it is referenced as
  `user.cover: covers/<douban_id>/user-01.webp`.

- Fetch constraints: only Douban's own image hosts (`img*.doubanio.com`); file names use
  slug/id + index, never a title (no path traversal); existing files are skipped; a single failure
  is recorded without failing the run; images come from `l` (1080×1600) and are capped to long edge
  ≤ 800 with WebP q80.

- **Path contract (fixed):** `covers` / `user.cover` always store an **archive-root relative key
  keyed by the Douban id** — `covers/<douban_id>/NN.webp`, **without** the
  `assets/bucket/film-tv/` prefix. The id is the merge key, so it is unique by construction and
  needs no collision escalation (`-<year>`, `-2`, `-hash6`) or degenerate-slug judgement;
  path readability does not matter because the yml and JSON always carry the id *and* the title.
  `slug` is retained only for share links (`?id=<slug>`) and never participates in a storage path.
  Consumers (macros, derived JSON, `film-tv-check`) prepend `extra.film_tv.local_prefix`
  (default `assets/bucket/film-tv/`); a full local path never belongs in the yml.

- Layout: local `docs/assets/bucket/film-tv/` (git-ignored) → R2 `data/film-tv/`;
  `.cache/` and `docs/assets/bucket/` are already covered by `.gitignore` (verified), so no new
  ignore rules are needed.

  ```text
  data/film-tv/
  └── covers/
      └── <douban_id>/          # e.g. 1292052
          ├── 01.webp           # subject-page main poster (always present)
          ├── 02.webp           # album candidate (on demand)
          └── user-01.webp      # hand-uploaded cover (optional)
  ```

- **Upload target (bug fixed 2026-09-27):** `film-tv-upload-covers` copies
  `docs/assets/bucket/film-tv/covers/` to `<remote_prefix>/covers/` — the key is
  `covers/<douban_id>/NN.webp`, so the `covers/` segment must survive the transfer. An earlier
  version copied the directory *contents* into `<remote_prefix>` itself, which put every object one
  level too high (`data/film-tv/<id>/01.webp`): the site's `cover_url`
  (`{base_url}/covers/<id>/NN.webp`) 404'd for every record. Objects left at the old location are
  unused — delete them by hand once the correct layout is uploaded (`film-tv-check --check-remote`
  lists them as orphans).

- **Local mirror policy:** the local copy is deliberately **not** a full mirror (1 cover/record
  ≈0.3 GB, 3 ≈0.9 GB); only recent years stay local. Two commands with **different semantics**:

  ```bash
  # (a) pull a subset — no delete semantics, rclone copy (the everyday choice)
  rclone copy <remote>:web-assets/data/film-tv/covers/<id>/ \
    docs/assets/bucket/film-tv/covers/<id>/ --checksum --progress
  rclone copy <remote>:web-assets/data/film-tv/ docs/assets/bucket/film-tv/ \
    --max-age 2y --checksum --progress

  # (b) a full mapping mirror — `bucket-sync pull` uses rclone sync, which DELETES
  #     local extras (including staged files not yet uploaded) → only for a full audit
  uv run poe bucket-sync pull --confirm        # dry-run by default: read what it would delete
  ```

- **Safety rule:** always dry-run a pull/upload that writes locally; if the output mentions
  deleting N > 0 local files, that is an **abort condition** (local work may be unuploaded) and
  needs a manual decision.

- **Cover validation tiers** (the local mirror may be absent): the local mode only validates the
  **key shape** (`covers/<id>/NN.webp`, id matches the record) and never reports "file missing";
  `poe film-tv-check --check-remote` lists the bucket and then reports missing files and orphans
  (skipping with a notice when rclone or credentials are unavailable).

- `mkdocs.yml` carries two blocks with deliberately different key styles:

  ```yaml
  extra:
    bucket:
      mappings:
        # before the generic assets/bucket/ mapping (more specific prefix first)
        - prefix: assets/bucket/film-tv/
          name: film-tv                 # hyphenated: bucket archive id (env override, --mapping)
          bucket: web-assets
          remote_prefix: data/film-tv
          base_url: "https://<r2>.r2.dev/data/film-tv"   # must mirror remote_prefix
    film_tv:                            # underscored: feature config block
      local_prefix: assets/bucket/film-tv/
      covers_default: 1
      cover_max_dimension: 800          # covers only (not optimize_images.max_dimension)
      cover_quality: 80
      person_name_style: hint           # hint | latin | zh
      data_dir: docs/notes/film-tv/data/
      json_dir: docs/notes/film-tv/assets/
  ```

- Supporting module work (implemented): `shared/bucket.py` now exposes `name` / `bucket` /
  `remote_prefix` from `load_mappings()`, adds `find_mapping()` / `pick_mapping()` (exact lookup by
  name, unknown name raises instead of silently falling back) and supports a **per-mapping
  `base_url` override** (`MKDOCS_BUCKET_BASE_URL_FILM_TV` beats the global
  `MKDOCS_BUCKET_BASE_URL`). `bucket_upload.py` / `bucket_sync.py` / `bucket_check.py` all accept
  `--mapping <name>`, and `bucket_sync.py` also has `--local-prefix` (narrows both sides so
  `rclone sync` cannot delete anything outside the requested subdirectory).

- **Flow (fixed): the sync only caches covers locally; uploading is the developer's step.**

  ```text
  poe sync-film-tv                 → fetch from Douban → local cache (no bucket, no R2 credentials)
  poe film-tv-upload-covers        → developer uploads (dry-run by default; rclone copy, never deletes)
  poe film-tv-check --check-remote → verify every referenced cover exists / list orphans
  ```

  `film-tv-upload-covers` uploads only files that are **referenced by the yml and present locally**
  (orphans and uncached references are ignored), supports `--limit N` batches and
  `--only <id|slug>`, and keeps credentials in the local rclone config.

- **R2 credentials and uploads are developer-only** (the AI never holds credentials or uploads):
  confirm there are no staged, unuploaded files in `docs/assets/bucket/film-tv/` → create a token
  scoped to `web-assets` (Object Read & Write) → fill `R2_*` in `.env.local` →
  `poe rclone-config-init` → verify the target with
  `poe bucket-upload <img> --mapping film-tv --confirm` → bulk upload →
  `poe bucket-check --check-remote` → `poe server-bucket` to confirm images render.

## 6. Classification rules (type / category / regions)

- `type`: `movie | tv`, authoritative from the list tab `?type=`; the subject page cross-checks it
  and `film-tv-check` reports disagreements.
- `category`: `feature | series | variety | anime | documentary | other`, **orthogonal to `type`**,
  derived from the subject page's `类型` (genres), taking the **first matching rule**:

| #   | Genre matches (any of)            | category      |
| --- | --------------------------------- | ------------- |
| 1   | 纪录片                            | `documentary` |
| 2   | 真人秀 / 脱口秀 / 综艺 / 舞台艺术 | `variety`     |
| 3   | 动画                              | `anime`       |
| 4   | `type == tv`                      | `series`      |
| 5   | `type == movie`                   | `feature`     |
| 6   | anything else                     | `other`       |

- The rules live in `taxonomy.yml` under `rules_version`; changing them bumps the version and
  `film-tv-check` lists the records to re-classify.
- **Confirmed by the developer:** any genre hit on 「动画」 means `anime` — animated series
  (tv + 动画), animated features and multi-episode OVA/compilations alike (e.g. One Piece,
  tv + 动画 → `anime`, not `series`). So `anime` outranks series/feature.
- `regions` maps the subject page's `制片国家/地区` (raw values such as 美国 / 中国大陆 / 日本 /
  韩国 / 中国香港) through the taxonomy aliases to short canonical names; an unmapped value is kept
  as-is and reported as a candidate alias. A co-production **counts once per region** (a statistic
  definition, so per-region counts may exceed the record count). An alias may map to a **list** of
  names (`港台: [香港, 台湾]`, `rules_version 2`), so a compound Douban label contributes one count
  to each region instead of being flattened onto a single one.
- `credits.casts`: the page lists ~19 names on average (up to 68; 12 samples) → only the **first
  10** are stored, which is also the actor scope of the people boards. Directors and writers are
  short lists and are stored in full.
- `year`: the earliest release year from `首播` / `上映日期` (tv uses the first-air year); parsing
  failures give `null`.

## 7. Deviations from the plan's original design

1. **The 看过 list no longer exposes short comments** → the fingerprint drops `douban_comment`
   and uses list-visible fields only (§2). Comments and tags can only be read from the subject
   page, so "I only edited a comment" is invisible to the short-circuit and needs
   `--only <slug>` or `--refresh-details [N]` (confirmed).
1. **4292 watched / 0 watching**, not ≈8000 (the old estimate included the wish list). Cover
   budget: 1 cover/record ≈ **0.3 GB**, 3 ≈ **0.9 GB** (measured 72 KB per cover at q80 / edge 800).
1. **Narrower account surface (ban-risk mitigation):** lists are walked anonymously (verified
   field-identical), covers default to the single subject-page poster (dropping 4292 album
   requests from the first pass), multi-candidate fetches became on-demand, and only subject pages
   / albums still need the login (anonymous gets the `sec.douban.com` JS challenge).
1. **Login gate is `/mine/`** (`/people/` always 404, anonymous `/mine/` 403).
1. **`deleted` rows** (subject removed on Douban) set `meta.missing_since` during the walk instead
   of waiting for `--prune`.
1. **The list walk runs twice, per `type=` tab** (same page count, yields `type`); `category` comes
   from genres because a variety show can be `type=movie`.
1. **`seasons` / `episode_progress` are unavailable** → permanently `null`, never invented.
1. **YAML write-back** uses PyYAML plus a custom dumper and a verbatim `user:` splice —
   `ruamel.yaml` is not needed. Verified: no write when unchanged, byte-identical user block, diffs
   limited to the machine lines that changed. PyYAML renders block sequences (`covers:`) indentless,
   which is legal and stable.
1. **Dependencies:** `websocket-client` is a main dependency but imported lazily in
   `shared/douban_auth.py`; login/browser code never enters CI.

## 8. References

- [Plan: Film & TV Archive](./plans/film-tv.md)
- [Bucket design](./bucket-design.md)
- [Health summary design](./health-summary-design.md) — the existing yml + macros + stats pattern
- [Commands](./commands.md)
- [Collection: Media](../docs/notes/collection/media.md)
