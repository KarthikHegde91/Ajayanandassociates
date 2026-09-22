# Ajay Anand & Associates website — architecture & contract

Static site. `python build.py` renders `src/` -> `dist/`. No Node, no frameworks, no external CDNs (fonts are self-hosted in src/assets/fonts).
`python build.py --serve` serves dist/ at http://localhost:8000 (add `--watch` to rebuild on change).

## Template syntax (partials, pages, templates)
- `{{> partial-name }}` includes `src/partials/partial-name.html` (recursive).
- `{{ dotted.key }}` substitutes a value from the merged context: `site.*` (site.config.json, HTML-escaped),
  `page.*` (front matter + derived), `service.*` (service pages), `post.*` (insight posts), and the globals below.
- No loops / conditionals. Lists are pre-rendered by build.py as HTML-string globals.
- Unknown partial or variable => build fails naming the file and key. Leftover `{{` in dist => build fails.
- **Escaping rule:** front-matter values (title, description, breadcrumb, summary) are PLAIN TEXT — write `&`, build escapes.
  In HTML bodies write `&amp;` yourself. JSON data values are plain text; build escapes them.

## Page front matter (src/pages/*.html, src/posts/*.html)
```
---
title: Page Title | Ajay Anand & Associates      (plain text; becomes <title> and og:title)
description: 150-160 char meta description  (plain text)
path: /about/                               (clean URL; index -> "/", 404 -> "/404.html"; defaults from filename)
breadcrumb: About Us                        (label in breadcrumb; defaults to title before "|")
robots: noindex,nofollow                    (optional; default index,follow)
body_class: page-about                      (optional)
date: 2026-09-12   summary: ...   read_time: 4 min read   draft: true     (posts only)
---
```

## Page skeleton (every page/template MUST follow)
```html
<!DOCTYPE html>
<html lang="en-IN">
{{> head }}
<body class="{{ page.body_class }}">
<a class="skip-link" href="#main">Skip to content</a>
{{> header }}
<main id="main">
  ...sections...
</main>
{{> cta-band }}
{{> footer }}
{{> wa-float }}
{{> mobile-bar }}
<script src="/assets/js/main.js" defer></script>
</body>
</html>
```
Section pattern:
```html
<section class="section [section--alt|section--navy]" data-reveal>
  <div class="container">
    <div class="section-head [section-head--center]">
      <p class="eyebrow">Eyebrow</p>
      <h2 class="section-head__title">Title</h2>
      <p class="section-head__lead">Lead paragraph.</p>
    </div>
    ...
  </div>
</section>
```
Page hero (non-home):
```html
<section class="hero hero--page"><div class="container">
  {{> breadcrumb }}
  <p class="hero__eyebrow">About us</p>
  <h1 class="hero__title">Your Trusted Partner for Accounting, Tax &amp; Compliance</h1>
  <p class="hero__lead">...</p>
  <div class="hero__actions"><a class="btn btn--accent" href="{{ booking_href }}"{{ booking_attrs }}>Book a Consultation</a>
  <a class="btn btn--whatsapp" href="{{ whatsapp_url }}" target="_blank" rel="noopener">WhatsApp Us</a></div>
</div></section>
```

## Globals available on every page (HTML strings unless noted)
| name | content |
|---|---|
| `year`, `today` | "2026", ISO date |
| `whatsapp_url` | https://wa.me/91…?text=… (escaped) |
| `booking_href`, `booking_attrs` | `/contact/#enquiry` or external booking URL; attrs = ` target="_blank" rel="noopener"` when external |
| `tel_href`, `mailto_href` | `tel:+91…`, `mailto:…` |
| `ga_snippet`, `org_json_ld` | used by head/schema-org only |
| `form_action`, `form_hidden`, `form_notice_html`, `service_options_html` | for the contact form partial |
| `services_nav_html` | `<li><a class="nav__sublink" href=…>Title</a></li>` x8 |
| `services_footer_html` | `<li><a href=…>Title</a></li>` x8 |
| `services_cards_html` | 8 x `.card.card--service` (num, icon, title link, summary, 4 bullets, link) |
| `services_cards_top_html` | 8 x `.card.card--service` without bullet list (compact) |
| `industries_cards_html` | 10 x `.card.card--industry` |
| `faq_all_html` | `<div class="accordion" data-accordion>` with all FAQs as `<details class="accordion__item"><summary class="accordion__q">…</summary><div class="accordion__a">` |
| `faq_groups_html` | same, grouped with `<h2 class="accordion__group">` headings |
| `faq_top_html` | first 4 FAQs |
| `faq_json_ld` | FAQPage schema for all FAQs — place `{{ faq_json_ld }}` inside `<main>` of faq.html only |
| `calendar_rows_html` | `<tr class="calendar__row"><td class="calendar__date"><td class="calendar__item"><td class="calendar__note">` rows — wrap in `<table class="calendar"><thead>…</thead><tbody>…</tbody></table>` |
| `calendar_mini_html` | rows flagged `featured` (4) |
| `documents_business_html`, `documents_individual_html` | `<ul class="checklist checklist--2">` |
| `links_html` | `<div class="links-grid">` of `.link-card` |
| `posts_list_html`, `posts_latest_html` | `.card.card--post` cards (all / latest 3) |
| `testimonials_section_html`, `team_section_html` | full `<section>` or empty string (disabled by default) |
| `maps_embed_html` | `.map-embed` iframe or `.map-embed--fallback` card |

## Service template vars (src/templates/service.html only)
`service.slug num title short summary note icon`, `service_icon_html`, `service_checklist_html` (`.checklist--3` of all items),
`service_items_count`, `deep_dive_html` (full `<section class="section section--alt deep-dive">` or ""), `service_note_html` (`.callout--note` or ""),
`who_for_html` (`<li class="chip">` items — wrap in `<ul class="chips">`), `related_cards_html` (3 compact service cards),
`faq_subset_html` ("" when none), `faq_subset_json_ld`, `calendar_subset_html` (rows or ""), `calendar_subset_count`,
`documents_html` (checklist or ""), `service_json_ld`. Breadcrumb: Home › Services › Title (automatic).

## Post template vars (src/templates/post.html)
`post.title description path date date_display summary read_time body` — `post.body` is the rendered article HTML (style with `.prose`).

## Partials and owners
| partial | owner | notes |
|---|---|---|
| head, schema-org, breadcrumb | foundation (done) | do not edit |
| header, footer, cta-band, wa-float, mobile-bar, contact-form, process, why-us | A | header nav: About · Services ▾ · Who We Serve ▾ (For Businesses, For Individuals & Professionals, Industries) · Resources ▾ (Resources, Insights, FAQ) · Contact · [Book a Consultation] |
| approach, audience-split, trust-strip | B | |
| calendar, documents, useful-links | D | calendar partial = full `<table class="calendar">` + disclaimer footnote using `calendar_rows_html` |

Templates `service.html`, `post.html` — A. Stub partials exist for all of the above so any workstream can build at any time.

## Data shapes (src/data/*.json)
- `services.json` (skeleton exists; C fills): `{slug,num,title,short,icon,summary,items[],note,deep_dive{eyebrow,title,intro,lead_in,items[],outro}|null,who_for[],related[slugs],faq_tags[],calendar_tags[],show_documents:"business"|"individual"|null,seo{title,description}}`
- `faq.json`: `[{q,a,group:"General"|"GST"|"Income Tax & TDS"|"Working with us",tags:[…]}]` — tags: `general accounting gst income-tax audit tds payroll registrations notices fees remote`
- `industries.json`: `[{slug,icon,title,text}]`
- `calendar.json`: `[{due,item,note,tags:["gst"|"tds"|"payroll"|"income-tax"],featured:bool}]`
- `documents.json`: `{business:[string],individual:[string]}`
- `links.json`: `[{name,url,desc}]`
- Icons: `src/assets/img/icons/service-<icon>.svg`, `industry-<icon>.svg`, `default.svg` (24x24 viewBox, `fill="none" stroke="currentColor" stroke-width="1.8"`, `aria-hidden="true"`). Inlined by build.py.

## Design tokens & class inventory (A implements; everyone uses ONLY these)
Tokens: `--c-primary-900 #0B1F4B · --c-primary #12306F · --c-primary-600 #1B44A3 · --c-primary-400 #2F62D6 (logo deep indigo) · --c-primary-100 #E4EBF5 · --c-primary-050 #F2F6FB · --c-accent #5D5294 (logo purple) · --c-accent-600 #B42525 · --c-accent-100 #FBE8E8 · --c-ink #14181F · --c-text #2A313B · --c-muted #5B6470 · --c-line #E3E7EC · --c-surface #F6F8FA · --c-bg #FFFFFF · --c-success #1E8E5A · --c-error #C0392B · --c-whatsapp #25D366`
`--font-head "Plus Jakarta Sans" · --font-body "Inter"` (self-hosted variable woff2, see fonts.css) · fluid type `--fs-xs sm base md lg xl 2xl 3xl` · `--sp-1..9` · `--section-y` · `--r-sm md lg pill` · `--sh-sm md lg` · `--container 72rem · --container-narrow 44rem · --gutter` · `--ease --dur`. Breakpoints 480/768/1024/1280 mobile-first. Light theme only. Gold only on navy or as accents; body text never gold.

Layout: `.container`, `.container--narrow`, `.section`, `.section--alt` (surface bg), `.section--navy` (navy bg, light text), `.section--tight`, `.grid .grid--2 .grid--3 .grid--4 .grid--5`, `.split` (text + media two columns, `.split__text .split__media`), `.stack`, `.sr-only`, `.skip-link`, `.prose`.
Components: `.site-header` · `.nav` · `.hero` (`--home --page`, `__eyebrow __title __lead __actions __chips __art`) · `.section-head` (`--center`, `.eyebrow`, `__title __lead`) · `.card` (`--service --industry --post`, `__top __num __icon __title __text __list __link __meta`) · `.tile` (`__icon __title __text`) · `.process` (`__step __num __title __text`) · `.checklist` (`--2 --3`, `__item`) · `.accordion` (`__group __item __q __a`) · `.cta-band` (`__title __text __actions`) · `.form` (`__row __field __label __input __select __textarea __error __hp __status __notice`) · `.contact-card` (`__row __icon __label __value`) · `.site-footer` · `.breadcrumb` · `.wa-float` · `.mobile-bar` · `.btn` (`--primary --accent --secondary --secondary-light --ghost --whatsapp --lg --block`) · `.badge` · `.chip` / `.chips` · `.trust-strip` (`__item`) · `.calendar` (table, `.calendar__note-foot`) · `.callout` (`--note --warn`) · `.map-embed` (`--fallback`) · `.links-grid` / `.link-card` (`__title __text __arrow`) · `.audience` (`__panel`) · `.testimonial` · `.team-card` · `.deep-dive`.
JS hooks (data attributes only): `data-nav-toggle`, `data-nav-menu` (on `.nav__item--has-menu`), `data-accordion`, `data-reveal`, `data-form`.

## Copy rules
- Use the approved copy in `docs/website-copy.txt` verbatim (light editorial tightening OK; no new claims).
- Never invent credentials, years in practice, client counts, testimonials, CA/ICAI/firm registration claims, or specific fees.
- Statutory due dates always carry: "Dates are indicative and subject to change or extension by the authorities. Please verify current due dates."
- Contact details come only from `{{ site.* }}` — never hard-code a phone/email/address.
- Every `<img>`/inline SVG needs `alt` or `aria-hidden="true"`. Headings in order, one H1 per page.
