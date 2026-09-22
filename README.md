# Ajay Anand & Associates — website

## What this is

A static website for Ajay Anand & Associates, an accounting, audit, GST and taxation
firm in Bengaluru. There is no framework and no Node.js involved — a small
Python script (`build.py`) renders the templated HTML in `src/` into plain
HTML/CSS/JS in `dist/`, which is what gets deployed. Content (services, FAQs,
the statutory calendar, useful links, etc.) lives in JSON files under
`src/data/` so it can be edited without touching HTML.

## Requirements

- Python 3.10 or later (stdlib only — no `pip install` needed to build the site).
- A Chromium-based browser (Google Chrome) only if you need to regenerate the
  OpenGraph/icon images — see [Regenerating images](#regenerating-images).

## Build & preview

Run these from the project root.

| Command | What it does |
|---|---|
| `python build.py` | Builds `src/` → `dist/` once and exits. |
| `python build.py --serve` | Builds, then serves `dist/` at http://localhost:8000. |
| `python build.py --watch` | Builds, then rebuilds automatically whenever a file under `src/` changes. |
| `python build.py --serve --watch` | Both of the above together. |
| `python build.py --serve --watch --port 8080` | Same, on a different port. |

The build fails loudly (non-zero exit code, message naming the file and the
problem) on things like an unknown `{{ }}` variable, an unknown `{{> }}`
partial, or leftover template tags — treat a failed build as something to fix,
not ignore.

## Project structure

```
build.py                   the static site generator (stdlib Python only)
src/
  site.config.json         firm details, contact info, feature toggles (see table below)
  data/                    JSON content: services, faq, industries, calendar, documents, links
  pages/                   top-level pages (index.html, about.html, contact.html, 404.html, ...)
  posts/                   Insights articles (front matter + HTML body)
  templates/               service.html and post.html — one template, many generated pages
  partials/                reusable HTML fragments ({{> header }}, {{> footer }}, ...)
  assets/                  css, js, images (copied into dist/assets, css is concatenated)
  static/                  files copied as-is to the root of dist/ (robots.txt, manifest, icons, ...)
  og/                      source HTML for the OpenGraph/icon images (see tools/render-images.ps1)
tools/
  render-images.ps1        renders src/og/*.html to PNGs + favicon.ico via headless Chrome
  make_favicon.py          packs favicon-32.png into favicon.ico
  checklinks.py            checks dist/ for broken internal links, missing assets, dead anchors
.github/workflows/deploy.yml   GitHub Pages deployment workflow
dist/                      build output — not committed (see .gitignore)
```

## Dark mode

The site follows the visitor's system theme automatically and has a sun/moon button in the header to switch manually. The choice is remembered in the browser. Colours for both themes live in `src/assets/css/tokens.css`: the top `:root` block is the light palette and the two blocks below it hold the dark palette (one for the system setting, one for the manual toggle). Change a colour in all three places to keep the themes consistent. Printing always uses the light theme.

## Editing content

### `src/site.config.json`

| Field | Meaning |
|---|---|
| `name` | Firm's legal/display name, used throughout the site and in schema.org data. |
| `url` | Canonical production URL, e.g. `https://www.ajayanandassociates.com` — no trailing slash. Used for canonical links, sitemap, schema.org `@id`s. **Update this to the real domain before going live.** |
| `cname` | If set, `build.py` writes a `CNAME` file into `dist/` with this value, for a GitHub Pages custom domain. Leave empty if you're not using a custom domain on GitHub Pages. |
| `phone_display` | Phone number as shown to visitors, e.g. `+91 98765 43210`. |
| `phone_e164` | Same number in E.164 form for the `tel:` link, e.g. `+919876543210`. |
| `whatsapp` | WhatsApp number, digits only with country code, no `+` — e.g. `919876543210`. |
| `whatsapp_text` | Pre-filled message opened in WhatsApp when a visitor taps "WhatsApp Us". |
| `email` | Firm's email address, used for `mailto:` links and schema.org data. |
| `address` | `street`, `locality`, `region`, `postal`, `country` — shown on the Contact page and embedded in schema.org data. |
| `hours` | Human-readable business hours shown to visitors, e.g. `Monday - Saturday, 10:00 AM - 6:00 PM`. |
| `hours_schema` | Same hours in schema.org format, e.g. `["Mo-Sa 10:00-18:00"]`. |
| `maps_embed` | The `src` URL of a Google Maps embed iframe. In Google Maps: search the firm's location → **Share** → **Embed a map** → copy only the `src="..."` value from the `<iframe>` code and paste it here. Leave blank to show a text fallback instead of a map. |
| `booking_url` | External booking link (e.g. a Calendly URL). Leave blank to have "Book a Consultation" buttons go to the on-page enquiry form instead. |
| `hero_video` | Optional path/URL to an MP4 to show in the homepage hero instead of the animated filing-tracker illustration. Leave blank to keep the illustration. |
| `hero_video_poster` | Optional poster image shown for `hero_video` before it starts playing. Ignored when `hero_video` is blank. |
| `ga_id` | Google Analytics 4 Measurement ID (e.g. `G-XXXXXXXXXX`). Leave blank to omit analytics entirely. |
| `og_image` | Path to the social-share image, defaults to `/assets/img/og-image.png` (see [Regenerating images](#regenerating-images)). |
| `social` | `linkedin`, `facebook`, `instagram` URLs — any left blank are simply omitted. |
| `form.web3forms_key` | Access key for the enquiry form — see [Enquiry form setup](#enquiry-form-setup). |
| `testimonials.enabled` / `testimonials.items` | Set `enabled: true` and fill in `items` (`quote`, `name`, `role`) to show a testimonials section. Off by default — do not enable with placeholder quotes. |
| `team.enabled` / `team.members` | Set `enabled: true` and fill in `members` (`name`, `initials`, `role`, `bio`) to show a team section. Off by default. |

### `src/data/*.json`

| File | Shape |
|---|---|
| `services.json` | List of services shown on the Services pages. Each item: `slug, num, title, short, icon, summary, items[], note, deep_dive{...}\|null, who_for[], related[slugs], faq_tags[], calendar_tags[], show_documents, seo{title,description}`. One page is generated per entry at `/services/<slug>/`. |
| `faq.json` | List of `{q, a, group, tags[]}`. `group` is one of `General`, `GST`, `Income Tax & TDS`, `Working with us`. `tags` link FAQs to relevant service pages. |
| `industries.json` | List of `{slug, icon, title, text}` shown as industry cards. |
| `calendar.json` | Statutory due-date calendar: `{due, item, note, tags[], featured}`. `featured: true` rows appear in the compact "mini" calendar on the homepage. |
| `documents.json` | `{business: [string], individual: [string]}` — document checklists. |
| `links.json` | List of `{name, url, desc}` — external useful links (GST portal, Income Tax e-filing, MCA, etc.). |

Icons referenced by `icon` fields are inline SVGs at
`src/assets/img/icons/service-<icon>.svg` / `industry-<icon>.svg` (24x24,
`stroke="currentColor"`) — add new ones there, or fall back to `default.svg`.

### Adding an Insights post

Create `src/posts/<slug>.html` with front matter, e.g.:

```
---
title: How to Register for GST in Bengaluru | Ajay Anand & Associates
description: A 150-160 character summary for search engines and social shares.
date: 2026-09-12
summary: One or two lines shown on the Insights listing card.
read_time: 4 min read
draft: true
---
<p>Article body as HTML — styled with the .prose class by the post template.</p>
```

Set `draft: true` while writing; the build skips draft posts entirely. Remove
that line (or set it to `false`) to publish. Posts are sorted newest-first by
`date` and appear at `/insights/<slug>/`.

## Enquiry form setup

The contact form posts to [Web3Forms](https://web3forms.com), a free service
that emails you each submission — no backend to run or maintain.

1. Go to [web3forms.com](https://web3forms.com) and create a free access key
   using the firm's email address (`info@anandassociates.in` or whichever
   address should receive enquiries).
2. Copy the access key into `form.web3forms_key` in `src/site.config.json`.
3. Rebuild the site (`python build.py`).
4. Submit a test enquiry through the live form and confirm the email arrives.

Until a key is set, the build prints a warning and the form is replaced with a
notice asking visitors to WhatsApp or call instead — so the site is never
left with a form that silently fails.

Spam protection is a honeypot field (`botcheck`) hidden from real visitors by
CSS but visible to bots — Web3Forms silently discards submissions where it is
filled in. No CAPTCHA is required.

## Sharing a preview before go-live

Three ways to show the site to the client without touching the real domain:

1. **Send a folder or zip.** Run `python build.py --portable`. This writes `dist-portable/`, a copy with relative links that works when opened directly from a folder (double-click `index.html`) or from an unzipped attachment. Zip that folder and send it; no server or internet needed. The enquiry form stays disabled until a Web3Forms key is set, so nothing is submitted by mistake.
2. **Same Wi-Fi on a phone or tablet.** Run `python build.py --serve`, find this PC's address with `ipconfig` (IPv4 Address), and open `http://<that-address>:8000` on the device. If it does not load, allow the port once in an Administrator PowerShell: `New-NetFirewallRule -DisplayName "Website preview (port 8000)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow`.
3. **Temporary public URL.** Cloudflare Pages (direct upload of `dist/`) or Netlify Drop give a free `*.pages.dev` / `*.netlify.app` address in a minute. The site also works under a GitHub Pages project URL such as `https://<user>.github.io/<repo>/`: set `url` in `site.config.json` to that address and rebuild; the build prefixes every link with the sub-path automatically. Reset `url` to the real domain before the final deploy.

## Deploying

### A) GitHub Pages (included workflow)

1. Create a GitHub repository and push this project to it (`main` branch).
2. In the repo, go to **Settings → Pages** and set **Source** to
   **GitHub Actions**. The included workflow at
   `.github/workflows/deploy.yml` builds with `python build.py` and deploys
   `dist/` automatically on every push to `main`.
3. **Custom domain (optional):** set `cname` in `src/site.config.json` to your
   domain (e.g. `www.ajayanandassociates.com`) so the build writes a `CNAME` file
   into `dist/`. At your DNS provider, add:
   - `A` records for the apex domain pointing to `185.199.108.153`,
     `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   - a `CNAME` record for `www` pointing to `<your-github-username>.github.io`.
   Then in **Settings → Pages**, enter the custom domain and enable
   **Enforce HTTPS** once GitHub has issued a certificate.

### B) Cloudflare Pages

- **Connect the repo:** build command `python build.py`, output directory
  `dist`. Cloudflare Pages provides Python automatically for the build step.
- **Or direct upload:** run `python build.py` locally and upload the contents
  of `dist/` directly through the Cloudflare Pages dashboard.
- Security headers and asset caching for Cloudflare Pages come from
  `src/static/_headers`, which is copied straight into `dist/` by the build.

## Go-live checklist

- [ ] Replace every placeholder in `src/site.config.json`: `phone_display`,
      `phone_e164`, `whatsapp`, `email`, `address`, `maps_embed`.
- [ ] Set `url` (and `cname`, if using GitHub Pages with a custom domain) to
      the real production domain.
- [ ] Update the `Sitemap:` line in `src/static/robots.txt` if the domain
      differs from `https://www.ajayanandassociates.com/sitemap.xml`.
- [ ] Run `tools/render-images.ps1` to regenerate the OpenGraph image and
      icons if the firm name, tagline, or colours change.
- [ ] Have a qualified professional at the firm review every page under
      `src/pages/`, `src/posts/`, and `src/data/faq.json` /
      `src/data/calendar.json` for accuracy — especially statutory due dates
      and anything resembling advice.
- [ ] Set up the enquiry form (see above) and test it end-to-end.
- [ ] On an actual phone, test the enquiry form, the WhatsApp button, and the
      tap-to-call phone number.
- [ ] Submit `sitemap.xml` in [Google Search Console](https://search.google.com/search-console).
- [ ] Create/claim a Google Business Profile for the firm and link the website.

## Content & legal notes

- Do not add claims, credentials, years-in-practice figures, client counts,
  or specific fees that have not been explicitly verified with the firm.
- Never state or imply CA/ICAI/firm registration status without the firm
  confirming it in writing.
- Statutory due dates shown anywhere on the site are indicative and subject
  to change or extension by the authorities — the copy already carries this
  disclaimer; keep it if you edit calendar content.

## Regenerating images

`src/og/og-card.html` and `src/og/icon-card.html` are self-contained HTML
"cards" (no external fonts, no build step) used as the source for the
OpenGraph share image and the site icons. To regenerate the PNGs and
favicon after editing them:

```powershell
powershell -ExecutionPolicy Bypass -File tools/render-images.ps1
```

This requires Google Chrome installed locally (looked up automatically under
`C:/Program Files/Google/Chrome/Application/` or the `(x86)` equivalent) and
produces:

- `src/assets/img/og-image.png` (1200x630)
- `src/static/icon-512.png` (512x512)
- `src/static/apple-touch-icon.png` (180x180)
- `src/static/favicon-32.png` and `src/static/favicon.ico`

## Checking for broken links

After building, run:

```
python tools/checklinks.py
```

It walks every generated page under `dist/`, checks that every internal
`href`/`src` resolves to a real file, and flags in-page `#anchor` links whose
target `id` is missing. It exits with a non-zero status if anything is
broken — useful as a pre-deploy sanity check or a CI step.
