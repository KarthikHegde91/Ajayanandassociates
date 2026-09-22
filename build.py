#!/usr/bin/env python3
"""
Static site builder for Anand & Associates (stdlib only).

  python build.py            build ./src -> ./dist
  python build.py --serve    build, then serve dist/ on http://localhost:8000
  python build.py --watch    rebuild whenever anything under src/ changes
  python build.py --serve --watch --port 8080
  python build.py --portable  also writes ./dist-portable with relative links (opens from a folder / zip)

Template syntax (partials, pages, templates):
  {{> partial-name }}        include src/partials/partial-name.html (recursive)
  {{ site.phone_display }}   dotted lookup over  site | page | service | post | globals
Unknown partials/variables fail the build with the file name and key.
"""
import datetime
import html
import json
import re
import shutil
import sys
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"

INCLUDE_RE = re.compile(r"\{\{>\s*([\w\-]+)\s*\}\}")
VAR_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
CSS_ORDER = ["fonts.css", "tokens.css", "base.css", "components.css", "pages.css"]


class BuildError(Exception):
    pass


# ----------------------------------------------------------------- helpers --
def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            p.write_text(text, encoding="utf-8", newline="\n")
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.3)


def load_json(name: str):
    p = SRC / "data" / f"{name}.json"
    if not p.exists():
        return [] if name != "documents" else {"business": [], "individual": []}
    try:
        return json.loads(read(p))
    except json.JSONDecodeError as e:
        raise BuildError(f"data/{name}.json: {e}") from e


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def deep_esc(v):
    """HTML-escape every string leaf (used for the site config exposed to templates)."""
    if isinstance(v, dict):
        return {k: deep_esc(x) for k, x in v.items()}
    if isinstance(v, list):
        return [deep_esc(x) for x in v]
    if isinstance(v, str):
        return esc(v)
    return v


def icon_svg(name: str, fallback: str = "default") -> str:
    """Inline an SVG from src/assets/img/icons/<name>.svg (falls back gracefully)."""
    for candidate in (name, fallback):
        p = SRC / "assets" / "img" / "icons" / f"{candidate}.svg"
        if p.exists():
            return read(p).strip()
    return ('<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h6"/></svg>')


def parse_front_matter(text: str, name: str):
    m = FM_RE.match(text)
    if not m:
        raise BuildError(f"{name}: missing front matter block (--- ... ---)")
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise BuildError(f"{name}: bad front matter line: {line!r}")
        k, v = line.split(":", 1)
        v = v.strip()
        if v.lower() in ("true", "false"):
            v = v.lower() == "true"
        fm[k.strip()] = v
    return fm, text[m.end():]


def lookup(ctx, key: str):
    cur = ctx
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(key)
    return cur


def render(text: str, ctx: dict, partials: dict, src_name: str, depth: int = 0) -> str:
    if depth > 6:
        raise BuildError(f"{src_name}: partial include depth exceeded")

    def inc(m):
        name = m.group(1)
        if name not in partials:
            raise BuildError(f'{src_name}: unknown partial "{name}"')
        return render(partials[name], ctx, partials, f"partials/{name}.html", depth + 1)

    text = INCLUDE_RE.sub(inc, text)

    def sub(m):
        try:
            v = lookup(ctx, m.group(1))
        except KeyError:
            raise BuildError(f'{src_name}: unknown variable "{m.group(1)}"') from None
        return "" if v is None else str(v)

    return VAR_RE.sub(sub, text)


def out_path(url_path: str) -> Path:
    if url_path.endswith(".html"):
        return DIST / url_path.lstrip("/")
    if url_path.strip("/"):
        return DIST / url_path.strip("/") / "index.html"
    return DIST / "index.html"


def json_ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"


# ------------------------------------------------------------ html builders --
ARROW = ('<svg class="icon-arrow" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" '
         'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
         '<path d="M4 10h12M11 5l5 5-5 5"/></svg>')


def service_card(s: dict, bullets: int = 4, compact: bool = False) -> str:
    href = f"/services/{s['slug']}/"
    items = "".join(f"<li>{esc(i)}</li>" for i in s.get("items", [])[:bullets]) if bullets else ""
    lst = f'<ul class="card__list">{items}</ul>' if items and not compact else ""
    return (
        f'<article class="card card--service">'
        f'<div class="card__top"><span class="card__num">{esc(s.get("num", ""))}</span>'
        f'<span class="card__icon">{icon_svg("service-" + s.get("icon", s["slug"]))}</span></div>'
        f'<h3 class="card__title"><a href="{href}">{esc(s["title"])}</a></h3>'
        f'<p class="card__text">{esc(s.get("summary", ""))}</p>{lst}'
        f'<a class="card__link" href="{href}">View details {ARROW}</a></article>'
    )


def industry_card(i: dict) -> str:
    return (
        f'<article class="card card--industry">'
        f'<span class="card__icon">{icon_svg("industry-" + i.get("icon", i.get("slug", "default")))}</span>'
        f'<h3 class="card__title">{esc(i["title"])}</h3><p class="card__text">{esc(i["text"])}</p></article>'
    )


def faq_items(faqs: list) -> str:
    return "".join(
        f'<details class="accordion__item"><summary class="accordion__q">{esc(f["q"])}</summary>'
        f'<div class="accordion__a"><p>{esc(f["a"])}</p></div></details>'
        for f in faqs
    )


def faq_groups(faqs: list) -> str:
    groups = []
    for f in faqs:
        g = f.get("group", "General")
        if g not in groups:
            groups.append(g)
    out = []
    for g in groups:
        items = faq_items([f for f in faqs if f.get("group", "General") == g])
        out.append(f'<h2 class="accordion__group">{esc(g)}</h2><div class="accordion" data-accordion>{items}</div>')
    return "".join(out)


def faq_schema(faqs: list) -> str:
    if not faqs:
        return ""
    return json_ld({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": f["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs],
    })


def faq_by_tags(faqs: list, tags: list, limit: int = 4) -> list:
    return [f for f in faqs if set(f.get("tags", [])) & set(tags)][:limit]


def calendar_rows(rows: list) -> str:
    return "".join(
        f'<tr class="calendar__row"><td class="calendar__date">{esc(r["due"])}</td>'
        f'<td class="calendar__item">{esc(r["item"])}</td><td class="calendar__note">{esc(r.get("note", ""))}</td></tr>'
        for r in rows
    )


def checklist(items: list, cols: int = 2) -> str:
    return (f'<ul class="checklist checklist--{cols}">'
            + "".join(f'<li class="checklist__item">{esc(i)}</li>' for i in items) + "</ul>")


def links_grid(links: list) -> str:
    return '<div class="links-grid">' + "".join(
        f'<a class="link-card" href="{esc(l["url"])}" target="_blank" rel="noopener noreferrer">'
        f'<span class="link-card__title">{esc(l["name"])}</span><span class="link-card__text">{esc(l.get("desc", ""))}</span>'
        f'<span class="link-card__arrow">{ARROW}</span></a>' for l in links) + "</div>"


def breadcrumb(site_url: str, crumbs: list) -> tuple:
    """crumbs = [(name, path), ...] excluding Home. Returns (html, json-ld)."""
    trail = [("Home", "/")] + crumbs
    lis = []
    for i, (name, path) in enumerate(trail):
        last = i == len(trail) - 1
        lis.append(f'<li><span aria-current="page">{esc(name)}</span></li>' if last
                   else f'<li><a href="{esc(path)}">{esc(name)}</a></li>')
    h = '<nav class="breadcrumb" aria-label="Breadcrumb"><ol>' + "".join(lis) + "</ol></nav>"
    ld = json_ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": site_url + p} for i, (n, p) in enumerate(trail)]})
    return h, ld



# ------------------------------------------------------- link rewriting --
ATTR_RE = re.compile(r'\b(href|src|action|content|data-src)="/(?!/)([^"]*)"')


def _split_target(rest: str):
    """'about/#x?y' -> ('about/', '#x?y')"""
    m = re.match(r"([^?#]*)(.*)", rest)
    return m.group(1), m.group(2)


def apply_base_path(base: str) -> None:
    """Prefix every root-absolute URL with base (e.g. '/repo') for GitHub project pages."""
    if not base:
        return
    for p in list(DIST.rglob("*.html")):
        s = read(p)
        s2 = ATTR_RE.sub(lambda m: f'{m.group(1)}="{base}/{m.group(2)}"', s)
        if s2 != s:
            write(p, s2)
    css = DIST / "assets" / "css" / "main.css"
    if css.exists():
        write(css, read(css).replace('url("/assets/', f'url("{base}/assets/').replace("url('/assets/", f"url('{base}/assets/"))


def make_portable(out: Path) -> int:
    """Copy dist -> out with relative links so the site opens from a folder (file://), a zip, or any sub-path."""
    if out.exists():
        shutil.rmtree(out, onerror=lambda f, path, exc: None)
    shutil.copytree(DIST, out, dirs_exist_ok=True)
    n = 0
    for p in out.rglob("*.html"):
        depth = len(p.relative_to(out).parts) - 1
        prefix = "../" * depth

        def fix(m):
            path, tail = _split_target(m.group(2))
            if path == "" or path.endswith("/"):
                path += "index.html"
            return f'{m.group(1)}="{prefix}{path}{tail}"'

        s = read(p)
        s2 = ATTR_RE.sub(fix, s)
        if s2 != s:
            write(p, s2)
        n += 1
    css = out / "assets" / "css" / "main.css"
    if css.exists():
        write(css, read(css).replace('url("/assets/', 'url("../').replace("url('/assets/", "url('../"))
    return n


# ------------------------------------------------------------------- build --
def build() -> int:
    if not (SRC / "site.config.json").exists():
        raise BuildError("src/site.config.json not found")
    cfg = json.loads(read(SRC / "site.config.json"))
    site_url = cfg.get("url", "").rstrip("/")
    today = datetime.date.today().isoformat()

    services = load_json("services")
    faqs = load_json("faq")
    industries = load_json("industries")
    calendar = load_json("calendar")
    documents = load_json("documents")
    links = load_json("links")
    partials = {p.stem: read(p) for p in (SRC / "partials").glob("*.html")}

    # --- dist skeleton -------------------------------------------------------
    if DIST.exists():
        # Tolerate files locked by a dev server / editor: remove what we can, overwrite the rest.
        shutil.rmtree(DIST, onerror=lambda f, path, exc: None)
    DIST.mkdir(exist_ok=True)
    assets = SRC / "assets"
    if assets.exists():
        shutil.copytree(assets, DIST / "assets", ignore=shutil.ignore_patterns("*.css"), dirs_exist_ok=True)
    css = "\n\n".join(f"/* ==== {n} ==== */\n" + read(assets / "css" / n)
                      for n in CSS_ORDER if (assets / "css" / n).exists())
    write(DIST / "assets" / "css" / "main.css", css)
    static = SRC / "static"
    if static.exists():
        shutil.copytree(static, DIST, dirs_exist_ok=True)
    if cfg.get("cname"):
        write(DIST / "CNAME", cfg["cname"] + "\n")

    # --- derived values ------------------------------------------------------
    wa_number = re.sub(r"\D", "", cfg.get("whatsapp", ""))
    whatsapp_url = f"https://wa.me/{wa_number}?text={urllib.parse.quote(cfg.get('whatsapp_text', ''))}"
    booking_url = cfg.get("booking_url") or ""
    booking_href = booking_url or "/contact/"
    booking_attrs = ' target="_blank" rel="noopener"' if booking_url.startswith("http") else ""
    hero_video = cfg.get("hero_video") or ""
    hero_video_poster_attr = f' poster="{esc(cfg.get("hero_video_poster", ""))}"' if cfg.get("hero_video_poster") else ""
    hero_video_html = "" if not hero_video else (
        f'<video class="hero__video" autoplay muted loop playsinline preload="metadata"{hero_video_poster_attr}>'
        f'<source src="{esc(hero_video)}" type="video/mp4"></video>')
    ga_id = cfg.get("ga_id") or ""
    ga_snippet = "" if not ga_id else (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={esc(ga_id)}"></script>'
        f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
        f"gtag('js',new Date());gtag('config','{esc(ga_id)}');</script>")

    form_cfg = cfg.get("form", {}) or {}
    key = form_cfg.get("web3forms_key") or ""
    form_action = "https://api.web3forms.com/submit"
    form_hidden = (
        f'<input type="hidden" name="access_key" value="{esc(key)}">'
        f'<input type="hidden" name="subject" value="New website enquiry - {esc(cfg.get("name", ""))}">'
        f'<input type="hidden" name="from_name" value="{esc(cfg.get("name", ""))} Website">'
        f'<input type="hidden" name="redirect" value="{esc(site_url)}/thank-you/">'
        '<input type="checkbox" name="botcheck" class="form__hp" tabindex="-1" autocomplete="off" aria-hidden="true">'
    )
    form_disabled_attr = "" if key else " data-form-disabled"
    form_notice_html = "" if key else (
        '<p class="callout callout--warn form__notice">The enquiry form is not connected yet. '
        f'Please <a href="{esc(whatsapp_url)}" target="_blank" rel="noopener">WhatsApp us</a> or call instead.</p>')
    if not key:
        print("warning: form.web3forms_key is empty - enquiry form is disabled until it is set", file=sys.stderr)
    for field in ("phone_display", "phone_e164", "whatsapp", "email", "url"):
        val = str(cfg.get(field, ""))
        if "XXXX" in val.upper() or "example" in val.lower() or not val:
            print(f"warning: site.config.json '{field}' still looks like a placeholder ({val!r})", file=sys.stderr)
    service_options_html = "".join(f'<option value="{esc(s["title"])}">{esc(s["title"])}</option>' for s in services) \
        + '<option value="Other">Other / Not sure</option>'

    addr = cfg.get("address", {}) or {}
    org_ld = json_ld({
        "@context": "https://schema.org", "@type": "AccountingService", "@id": site_url + "/#organization",
        "name": cfg.get("name"), "url": site_url + "/", "logo": site_url + "/assets/img/logo.png",
        "image": site_url + cfg.get("og_image", "/assets/img/og-image.png"),
        "description": cfg.get("description", ""),
        "telephone": cfg.get("phone_e164", ""), "email": cfg.get("email", ""),
        "address": {"@type": "PostalAddress", "streetAddress": addr.get("street", ""),
                    "addressLocality": addr.get("locality", "Bengaluru"), "addressRegion": addr.get("region", "Karnataka"),
                    "postalCode": addr.get("postal", ""), "addressCountry": addr.get("country", "IN")},
        "areaServed": [{"@type": "City", "name": "Bengaluru"}, {"@type": "State", "name": "Karnataka"},
                       {"@type": "Country", "name": "India"}],
        "openingHours": cfg.get("hours_schema", []), "priceRange": "$$",
        "sameAs": [u for u in (cfg.get("social", {}) or {}).values() if u],
    })

    def testimonials_section():
        t = cfg.get("testimonials", {}) or {}
        if not t.get("enabled") or not t.get("items"):
            return ""
        cards = "".join(
            f'<figure class="testimonial"><blockquote class="testimonial__quote">{esc(i["quote"])}</blockquote>'
            f'<figcaption class="testimonial__by"><strong>{esc(i.get("name", ""))}</strong>'
            f'<span>{esc(i.get("role", ""))}</span></figcaption></figure>' for i in t["items"])
        return (f'<section class="section testimonials" data-reveal><div class="container">'
                f'<div class="section-head section-head--center"><p class="eyebrow">Client feedback</p>'
                f'<h2 class="section-head__title">{esc(t.get("title", "What our clients say"))}</h2></div>'
                f'<div class="grid grid--3">{cards}</div></div></section>')

    def team_section():
        t = cfg.get("team", {}) or {}
        if not t.get("enabled") or not t.get("members"):
            return ""
        cards = "".join(
            f'<article class="team-card"><div class="team-card__avatar">{esc(m.get("initials") or m.get("name", "?")[:1])}</div>'
            f'<h3 class="team-card__name">{esc(m["name"])}</h3><p class="team-card__role">{esc(m.get("role", ""))}</p>'
            f'<p class="team-card__bio">{esc(m.get("bio", ""))}</p></article>' for m in t["members"])
        return (f'<section class="section team" data-reveal><div class="container">'
                f'<div class="section-head section-head--center"><p class="eyebrow">Our team</p>'
                f'<h2 class="section-head__title">{esc(t.get("title", "People behind the numbers"))}</h2></div>'
                f'<div class="grid grid--3">{cards}</div></div></section>')

    # --- posts (front matter first so the listing is available globally) ----
    posts = []
    for p in sorted((SRC / "posts").glob("*.html")):
        fm, body = parse_front_matter(read(p), f"posts/{p.name}")
        if fm.get("draft"):
            continue
        fm.setdefault("path", f"/insights/{p.stem}/")
        fm.setdefault("breadcrumb", fm.get("title", p.stem))
        fm.setdefault("date", today)
        fm.setdefault("summary", fm.get("description", ""))
        fm.setdefault("read_time", "")
        fm.setdefault("heading", fm.get("title", p.stem).split("|")[0].strip())
        posts.append((fm, body, p.name))
    posts.sort(key=lambda t: t[0]["date"], reverse=True)

    def post_card(fm):
        date = datetime.date.fromisoformat(fm["date"]).strftime("%d %b %Y")
        rt = f' &middot; {esc(fm["read_time"])}' if fm.get("read_time") else ""
        return (f'<article class="card card--post"><p class="card__meta"><time datetime="{esc(fm["date"])}">{date}</time>{rt}</p>'
                f'<h3 class="card__title"><a href="{esc(fm["path"])}">{esc(fm.get("title_short") or fm["heading"])}</a></h3>'
                f'<p class="card__text">{esc(fm["summary"])}</p><a class="card__link" href="{esc(fm["path"])}">Read guide {ARROW}</a></article>')

    featured_cal = [r for r in calendar if r.get("featured")] or calendar[:4]

    g = {
        "year": str(cfg.get("year") or datetime.date.today().year),
        "today": today,
        "whatsapp_url": esc(whatsapp_url),
        "booking_href": esc(booking_href),
        "booking_attrs": booking_attrs,
        "hero_video_html": hero_video_html,
        "tel_href": "tel:" + re.sub(r"[^\d+]", "", cfg.get("phone_e164", "")),
        "mailto_href": "mailto:" + esc(cfg.get("email", "")),
        "ga_snippet": ga_snippet,
        "org_json_ld": org_ld,
        "form_action": form_action,
        "form_hidden": form_hidden,
        "form_notice_html": form_notice_html,
        "form_disabled_attr": form_disabled_attr,
        "service_options_html": service_options_html,
        "services_nav_html": "".join(f'<li><a class="nav__sublink" href="/services/{s["slug"]}/">{esc(s["title"])}</a></li>' for s in services),
        "services_footer_html": "".join(f'<li><a href="/services/{s["slug"]}/">{esc(s["title"])}</a></li>' for s in services),
        "services_cards_html": "".join(service_card(s) for s in services),
        "services_cards_top_html": "".join(service_card(s, bullets=0) for s in services),
        "industries_cards_html": "".join(industry_card(i) for i in industries),
        "faq_all_html": f'<div class="accordion" data-accordion>{faq_items(faqs)}</div>',
        "faq_groups_html": faq_groups(faqs),
        "faq_top_html": f'<div class="accordion" data-accordion>{faq_items(faqs[:4])}</div>',
        "faq_json_ld": faq_schema(faqs),
        "calendar_rows_html": calendar_rows(calendar),
        "calendar_mini_html": calendar_rows(featured_cal),
        "documents_business_html": checklist(documents.get("business", [])),
        "documents_individual_html": checklist(documents.get("individual", [])),
        "links_html": links_grid(links),
        "posts_list_html": "".join(post_card(fm) for fm, _, _ in posts),
        "posts_latest_html": "".join(post_card(fm) for fm, _, _ in posts[:3]),
        "testimonials_section_html": testimonials_section(),
        "team_section_html": team_section(),
        "address_display": esc(", ".join(x for x in (addr.get("street"), addr.get("locality"), (addr.get("region", "") + " " + addr.get("postal", "")).strip()) if x)),
        "hero_services_html": "".join(f'<li class="hero-list__item"><a class="hero-list__link" href="/services/{s["slug"]}/"><span class="hero-list__num">{esc(s.get("num", ""))}</span><span class="hero-list__title">{esc(s["title"])}</span>{ARROW}</a></li>' for s in services[:5]),
        "industries_chips_html": "".join(f'<li class="chip">{esc(i["title"])}</li>' for i in industries),
        "maps_embed_html": (
            f'<div class="map-embed"><iframe src="{esc(cfg["maps_embed"])}" loading="lazy" '
            f'referrerpolicy="no-referrer-when-downgrade" allowfullscreen '
            f'title="Map showing the location of {esc(cfg.get("name", ""))}"></iframe></div>'
            if cfg.get("maps_embed") else
            f'<div class="map-embed map-embed--fallback"><p><strong>{esc(cfg.get("name", ""))}</strong><br>'
            f'{esc(addr.get("locality", "Bengaluru"))}, {esc(addr.get("region", "Karnataka"))}, India</p></div>'),
    }
    site_ctx = deep_esc(cfg)
    written = []   # (url_path, robots, source name)

    def page_ctx(fm: dict, extra: dict = None, crumbs: list = None):
        path = fm["path"]
        canonical = site_url + path
        if crumbs is None:
            crumbs = [(fm.get("breadcrumb", fm.get("title", "")), path)] if path != "/" else []
        bc_html, bc_ld = breadcrumb(site_url, crumbs) if crumbs else ("", "")
        page = dict(fm)
        for k in ("title", "description", "breadcrumb", "summary", "title_short"):
            if isinstance(page.get(k), str):
                page[k] = esc(page[k])
        page.update({
            "canonical": esc(canonical),
            "robots": fm.get("robots") or "index,follow",
            "og_type": fm.get("og_type") or "website",
            "og_image": esc(site_url + (fm.get("image") or cfg.get("og_image", "/assets/img/og-image.png"))),
            "body_class": fm.get("body_class", ""),
            "breadcrumb_html": bc_html,
            "breadcrumb_json_ld": bc_ld,
            "extra_json_ld": fm.get("extra_json_ld", ""),
        })
        ctx = {"site": site_ctx, "page": page, **g}
        if extra:
            ctx.update(extra)
        return ctx

    def emit(html_text: str, url_path: str, robots: str, name: str):
        write(out_path(url_path), html_text)
        written.append((url_path, robots, name))

    # --- plain pages ---------------------------------------------------------
    for p in sorted((SRC / "pages").glob("*.html")):
        fm, body = parse_front_matter(read(p), f"pages/{p.name}")
        if fm.get("draft"):
            continue
        fm.setdefault("path", "/" if p.stem == "index" else (f"/{p.stem}.html" if p.stem == "404" else f"/{p.stem}/"))
        if p.stem == "404":
            fm.setdefault("robots", "noindex,nofollow")
        fm.setdefault("breadcrumb", fm.get("title", p.stem).split("|")[0].strip())
        ctx = page_ctx(fm)
        emit(render(body, ctx, partials, f"pages/{p.name}"), fm["path"], ctx["page"]["robots"], p.name)

    # --- service pages -------------------------------------------------------
    tpl = SRC / "templates" / "service.html"
    if tpl.exists() and services:
        tpl_text = read(tpl)
        by_slug = {s["slug"]: s for s in services}
        for s in services:
            path = f"/services/{s['slug']}/"
            seo = s.get("seo", {}) or {}
            fm = {"title": seo.get("title") or f"{s['title']} in Bengaluru | {cfg.get('name')}",
                  "description": seo.get("description") or s.get("summary", ""),
                  "path": path, "breadcrumb": s["title"]}
            dd = s.get("deep_dive") or {}
            deep_dive_html = "" if not dd else (
                f'<section class="section section--alt deep-dive" data-reveal><div class="container">'
                f'<div class="section-head"><p class="eyebrow">{esc(dd.get("eyebrow", ""))}</p>'
                f'<h2 class="section-head__title">{esc(dd.get("title", ""))}</h2>'
                f'<p class="section-head__lead">{esc(dd.get("intro", ""))}</p></div>'
                f'<p class="deep-dive__lead-in">{esc(dd.get("lead_in", ""))}</p>{checklist(dd.get("items", []), 3)}'
                f'<p class="deep-dive__outro">{esc(dd.get("outro", ""))}</p></div></section>')
            note_html = f'<div class="callout callout--note">{esc(s["note"])}</div>' if s.get("note") else ""
            who_for_html = "".join(f'<li class="chip">{esc(w)}</li>' for w in s.get("who_for", []))
            related = [by_slug[r] for r in s.get("related", []) if r in by_slug]
            related_cards_html = "".join(service_card(r, bullets=0) for r in related)
            sub_faqs = faq_by_tags(faqs, s.get("faq_tags", []), 4)
            cal = [r for r in calendar if set(r.get("tags", [])) & set(s.get("calendar_tags", []))]
            docs_key = s.get("show_documents")
            documents_html = checklist(documents.get(docs_key, [])) if docs_key else ""
            service_ld = json_ld({"@context": "https://schema.org", "@type": "Service", "name": s["title"],
                                  "serviceType": s["title"], "description": s.get("summary", ""),
                                  "provider": {"@id": site_url + "/#organization"},
                                  "areaServed": {"@type": "City", "name": "Bengaluru"}, "url": site_url + path})
            ctx = page_ctx(fm, crumbs=[("Services", "/services/"), (s["title"], path)], extra={
                "service": deep_esc(s),
                "service_icon_html": icon_svg("service-" + s.get("icon", s["slug"])),
                "service_checklist_html": checklist(s.get("items", []), 3),
                "service_items_count": str(len(s.get("items", []))),
                "deep_dive_html": deep_dive_html,
                "service_note_html": note_html,
                "who_for_html": who_for_html,
                "related_cards_html": related_cards_html,
                "faq_subset_html": f'<div class="accordion" data-accordion>{faq_items(sub_faqs)}</div>' if sub_faqs else "",
                "faq_subset_json_ld": faq_schema(sub_faqs),
                "calendar_subset_html": calendar_rows(cal),
                "calendar_subset_count": str(len(cal)),
                "documents_html": documents_html,
                "service_json_ld": service_ld,
            })
            emit(render(tpl_text, ctx, partials, f"templates/service.html [{s['slug']}]"), path, "index,follow", f"service:{s['slug']}")

    # --- posts ---------------------------------------------------------------
    ptpl = SRC / "templates" / "post.html"
    if ptpl.exists() and posts:
        ptpl_text = read(ptpl)
        for fm, body, name in posts:
            fm.setdefault("og_type", "article")
            fm["date_display"] = datetime.date.fromisoformat(fm["date"]).strftime("%d %B %Y")
            ctx = page_ctx(fm, crumbs=[("Insights", "/insights/"), (fm["breadcrumb"], fm["path"])])
            ctx["post"] = dict(fm)
            ctx["post"]["body"] = render(body, ctx, partials, f"posts/{name}")
            emit(render(ptpl_text, ctx, partials, f"templates/post.html [{name}]"), fm["path"], ctx["page"]["robots"], f"post:{name}")

    # --- sitemap + checks ----------------------------------------------------
    urls = [u for u, r, _ in written if "noindex" not in r and not u.endswith(".html") and not u.strip("/").startswith("_")]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        pr = "1.0" if u == "/" else ("0.8" if u.count("/") <= 2 else "0.7")
        sm.append(f"  <url><loc>{esc(site_url + u)}</loc><lastmod>{today}</lastmod><priority>{pr}</priority></url>")
    sm.append("</urlset>")
    write(DIST / "sitemap.xml", "\n".join(sm) + "\n")

    leftovers = [str(p.relative_to(DIST)) for p in DIST.rglob("*.html") if "{{" in read(p)]
    if leftovers:
        raise BuildError("unrendered template tags remain in: " + ", ".join(leftovers))
    base = urllib.parse.urlparse(cfg.get("url", "")).path.rstrip("/")
    if base:
        apply_base_path(base)
        print(f"note: site.url has a sub-path; all links prefixed with '{base}'", file=sys.stderr)
    print(f"Built {len(written)} pages -> {DIST}")
    return len(written)


# ------------------------------------------------------------------- serve --
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIST), **kw)

    def send_error(self, code, message=None, explain=None):
        page = DIST / "404.html"
        if code == 404 and page.exists():
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s %s\n" % (self.command, self.path))


def src_signature() -> float:
    return max((p.stat().st_mtime for p in SRC.rglob("*") if p.is_file()), default=0)


def main(argv):
    port = 8000
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    try:
        build()
        if "--portable" in argv:
            out = ROOT / "dist-portable"
            n = make_portable(out)
            print(f"Portable copy with relative links ({n} pages) -> {out}  (open index.html directly, or zip the folder)")
    except BuildError as e:
        print(f"build failed: {e}", file=sys.stderr)
        return 1
    if "--serve" not in argv and "--watch" not in argv:
        return 0
    httpd = None
    if "--serve" in argv:
        import threading
        httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        print(f"Serving dist/ at http://localhost:{port}  (Ctrl+C to stop)")
    if "--watch" in argv:
        print("Watching src/ for changes ...")
    last = src_signature()
    try:
        while True:
            time.sleep(1)
            if "--watch" in argv:
                sig = src_signature()
                if sig != last:
                    last = sig
                    try:
                        build()
                    except BuildError as e:
                        print(f"build failed: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        if httpd:
            httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
