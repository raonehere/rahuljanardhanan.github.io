#!/usr/bin/env python3
"""Build static project and category pages from content/pages/*.md.

Run from the repo root: python3 tools/build_pages.py
Writes projects/<slug>/index.html. Images stay in media/.
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "content" / "pages"
OUT_DIR = ROOT / "projects"
SITE = "https://rahuljanardhanan.com"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MD_ITEM_RE = re.compile(r"^- \[([^\]]+)\]\(([^)]+\.md)\)$")
UNAVAIL_RE = re.compile(r"^\*\[Unavailable (video|file):\s*(.+?)\]\*$")
UNRENDERED_RE = re.compile(r"^\*\[Unrendered Notion\b.*\]\*$")
YT_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})"
)
BARE_URL_RE = re.compile(r"^https?://\S+$")


def parse_page(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"missing front matter: {path.name}")
    _, fm, body = text.split("---", 2)
    data = {}
    key = None
    for line in fm.splitlines():
        if line.startswith("  - "):
            data.setdefault(key, [])
            if not isinstance(data[key], list):
                data[key] = []
            data[key].append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        v = v.strip()
        if v in ("", "null"):
            data[key] = None
        elif v == "[]":
            data[key] = []
        else:
            data[key] = v.strip('"')
    data["body"] = body.strip("\n")
    data["file"] = path.name
    return data


def esc(value):
    return html.escape(value or "", quote=True)


def norm_id(value):
    return re.sub(r"[^0-9a-f]", "", (value or "").lower())


def bold(escaped):
    return BOLD_RE.sub(r"<strong>\1</strong>", escaped)


def media_src(raw):
    name = raw.strip()
    marker = "media/"
    idx = name.find(marker)
    if idx == -1:
        return None
    return "../../" + name[idx:]


def resolve_href(url, by_notion, by_slug):
    url = url.strip()
    if url.startswith("/") and not url.startswith("//"):
        nid = norm_id(url.split("?", 1)[0])
        page = by_notion.get(nid)
        if page:
            return f"../{page['slug']}/", ""
        return None, ""
    if url.endswith(".md"):
        slug = url.split("/")[-1][:-3]
        if slug in by_slug:
            return f"../{slug}/", ""
        return None, ""
    if url.startswith(("http://", "https://")):
        return url, ' target="_blank" rel="noopener noreferrer"'
    if url.startswith("mailto:"):
        return url, ""
    return url, ""


def fmt_inlines(raw, by_notion, by_slug):
    parts = []
    pos = 0
    for match in LINK_RE.finditer(raw):
        parts.append(bold(esc(raw[pos:match.start()])))
        href, attrs = resolve_href(match.group(2), by_notion, by_slug)
        label = bold(esc(match.group(1)))
        if href is None:
            parts.append(label)
            parts.append(f"<!-- unresolved notion link: {esc(match.group(2))} -->")
        else:
            parts.append(f'<a href="{esc(href)}"{attrs}>{label}</a>')
        pos = match.end()
    parts.append(bold(esc(raw[pos:])))
    return "".join(parts)


def youtube_id(url):
    match = YT_RE.search(url)
    return match.group(1) if match else None


def placeholder(kind, name):
    label = "Video coming soon" if kind == "video" else "File coming soon"
    comment = "video" if kind == "video" else "file"
    return (
        f'<div class="soon" role="img" aria-label="{label}">'
        f"<p>{label}</p>"
        f"<!-- replace with {comment}: {esc(name)} -->"
        f"</div>"
    )


def embed_youtube(url, title):
    vid = youtube_id(url)
    src = f"https://www.youtube-nocookie.com/embed/{vid}"
    return (
        f'<div class="embed"><iframe src="{esc(src)}" title="{esc(title)}"'
        f' loading="lazy" allow="accelerometer; autoplay; clipboard-write;'
        f' encrypted-media; gyroscope; picture-in-picture; web-share"'
        f" allowfullscreen></iframe></div>"
    )


def link_line(url):
    return (
        f'<p class="link-line"><a href="{esc(url)}" target="_blank"'
        f' rel="noopener noreferrer">{esc(url)}</a></p>'
    )


def image_tag(src, alt, lazy=True):
    loading = ' loading="lazy"' if lazy else ""
    return (
        f'<figure class="figure"><img src="{esc(src)}" alt="{esc(alt)}"{loading}></figure>'
    )


def first_visual(page):
    if page.get("cover"):
        return media_src(page["cover"])
    match = IMG_RE.search(page["body"])
    if match:
        return media_src(match.group(2))
    return None


def render_body(page, by_notion, by_slug, cards_html):
    lines = page["body"].splitlines()
    chunks = []
    i = 0
    skipped_title = False
    cards_done = False
    while i < len(lines):
        raw = lines[i].strip()
        if not raw:
            i += 1
            continue
        if raw.startswith("# "):
            if not skipped_title:
                skipped_title = True
            else:
                chunks.append(f"<h2>{fmt_inlines(raw[2:].strip(), by_notion, by_slug)}</h2>")
            i += 1
            continue
        if raw.startswith("## "):
            chunks.append(f"<h2>{fmt_inlines(raw[3:].strip(), by_notion, by_slug)}</h2>")
            i += 1
            continue
        if raw.startswith("### "):
            chunks.append(f"<h3>{fmt_inlines(raw[4:].strip(), by_notion, by_slug)}</h3>")
            i += 1
            continue
        unavail = UNAVAIL_RE.match(raw)
        if unavail:
            chunks.append(placeholder(unavail.group(1), unavail.group(2)))
            i += 1
            continue
        if UNRENDERED_RE.match(raw):
            chunks.append(f"<!-- {esc(raw)} -->")
            i += 1
            continue
        img = IMG_RE.fullmatch(raw)
        if img:
            src = media_src(img.group(2))
            alt = img.group(1).strip() or page["title"]
            if src:
                chunks.append(image_tag(src, alt))
            else:
                chunks.append(f"<!-- missing image: {esc(img.group(2))} -->")
            i += 1
            continue
        if raw.startswith("- "):
            items = []
            md_only = True
            while i < len(lines) and lines[i].strip().startswith("- "):
                item = lines[i].strip()
                md_match = MD_ITEM_RE.match(item)
                if md_match:
                    items.append(("md", md_match.group(1), md_match.group(2)))
                else:
                    md_only = False
                    items.append(("text", item[2:].strip(), None))
                i += 1
            if md_only and cards_html and not cards_done:
                chunks.append(cards_html)
                cards_done = True
            else:
                lis = []
                for kind, label, url in items:
                    if kind == "md":
                        href, attrs = resolve_href(url, by_notion, by_slug)
                        if href:
                            lis.append(f'<li><a href="{esc(href)}"{attrs}>{esc(label)}</a></li>')
                        else:
                            lis.append(f"<li>{esc(label)}</li>")
                    else:
                        lis.append(f"<li>{fmt_inlines(label, by_notion, by_slug)}</li>")
                chunks.append("<ul>" + "".join(lis) + "</ul>")
            continue
        if BARE_URL_RE.match(raw):
            if youtube_id(raw):
                chunks.append(embed_youtube(raw, page["title"]))
            else:
                chunks.append(link_line(raw))
            i += 1
            continue
        chunks.append(f"<p>{fmt_inlines(raw, by_notion, by_slug)}</p>")
        i += 1
    if cards_html and not cards_done:
        chunks.append(cards_html)
    return "\n".join(chunks)


def crumbs(page, by_slug):
    parts = [('Home', "../../")]
    parent = page.get("parent")
    if parent and parent != "index" and parent in by_slug:
        parts.append((by_slug[parent]["title"], f"../{parent}/"))
    parts.append((page["title"], None))
    bits = ['<nav class="crumbs" aria-label="Breadcrumb">']
    for idx, (label, href) in enumerate(parts):
        if idx:
            bits.append('<span class="sep" aria-hidden="true">/</span>')
        if href:
            bits.append(f'<a href="{esc(href)}">{esc(label)}</a>')
        else:
            bits.append(f"<span>{esc(label)}</span>")
    bits.append("</nav>")
    return "".join(bits)


def card(child, by_slug):
    page = by_slug[child]
    visual = first_visual(page)
    if visual:
        media = (
            f'<div class="media"><img src="{esc(visual)}" alt="" loading="lazy"></div>'
        )
    else:
        media = '<div class="media media-placeholder"><!-- replace with image --></div>'
    return (
        f'<a class="card card-link" href="../{esc(child)}/">'
        f"{media}<h2>{esc(page['title'])}</h2></a>"
    )


def child_slugs(page):
    slugs = []
    for line in page["body"].splitlines():
        match = MD_ITEM_RE.match(line.strip())
        if match:
            slugs.append(match.group(2).split("/")[-1][:-3])
    return slugs


def page_html(page, by_notion, by_slug):
    children = [slug for slug in child_slugs(page) if slug in by_slug]
    cards_html = ""
    if children:
        cards = "\n".join(card(slug, by_slug) for slug in children)
        cards_html = f'<div class="card-grid">{cards}</div>'
    cover = ""
    if page.get("cover"):
        src = media_src(page["cover"])
        if src:
            cover = image_tag(src, page["title"], lazy=False).replace(
                'class="figure"', 'class="figure cover"', 1
            )
    body = render_body(page, by_notion, by_slug, cards_html)
    title = page["title"]
    desc = esc(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} — Rahul Janardhanan</title>
  <meta name="description" content="{desc}">
  <meta name="theme-color" content="#000000">
  <link rel="canonical" href="{SITE}/projects/{esc(page['slug'])}/">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../../styles.css">
</head>
<body id="top">
  <a class="skip" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="shell header-inner">
      <a class="brand" href="../../">Rahul Janardhanan</a>
      <nav class="nav-links" aria-label="Sections">
        <a href="../../#recent">Recent</a>
        <a href="../../#personal">Personal</a>
        <a href="../../#client">Client</a>
        <a href="../../#connect">Connect</a>
      </nav>
    </div>
  </header>
  <main id="main">
    <article class="section article">
      <div class="shell">
        {crumbs(page, by_slug)}
        <h1>{esc(title)}</h1>
        {cover}
        <div class="prose">
{body}
        </div>
      </div>
    </article>
  </main>
  <footer class="site-footer">
    <div class="shell footer-inner">
      <div>
        <p class="footer-name">Rahul Janardhanan</p>
        <p class="footer-meta">Design · Animation · Video · Photo</p>
      </div>
      <a class="footer-top" href="#top">Back to top</a>
    </div>
  </footer>
</body>
</html>
"""


def visible_text(doc):
    return re.sub(r"<!--.*?-->", "", doc, flags=re.S)


def main():
    pages = [parse_page(path) for path in sorted(PAGES_DIR.glob("*.md"))]
    by_slug = {page["slug"]: page for page in pages}
    by_notion = {}
    for page in pages:
        nid = norm_id(page.get("notion_id"))
        if nid:
            by_notion[nid] = page
    if OUT_DIR.exists():
        for old in OUT_DIR.glob("*/index.html"):
            old.unlink()
    written = []
    problems = []
    for page in pages:
        if page["slug"] == "index":
            continue
        for match in IMG_RE.finditer(page["body"]):
            src = media_src(match.group(2))
            if not src or not (ROOT / src.replace("../../", "")).exists():
                problems.append(f"missing image {page['slug']}: {match.group(2)}")
        if page.get("cover"):
            src = media_src(page["cover"])
            if not src or not (ROOT / src.replace("../../", "")).exists():
                problems.append(f"missing cover {page['slug']}: {page['cover']}")
        doc = page_html(page, by_notion, by_slug)
        shown = visible_text(doc)
        for banned in ("Unrendered", "Unavailable video", "Unavailable file", "[Unrendered"):
            if banned in shown:
                problems.append(f"marker leaked on {page['slug']}: {banned}")
        dest = OUT_DIR / page["slug"] / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(doc, encoding="utf-8")
        written.append(page["slug"])
    print(f"wrote {len(written)} pages")
    if problems:
        print("PROBLEMS")
        for item in problems:
            print(" -", item)
        raise SystemExit(1)
    for slug in written:
        print(slug)


if __name__ == "__main__":
    main()
