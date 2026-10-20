#!/usr/bin/env python3
"""Build photography/index.html from content/photography.json.

The order of the "photos" list is the order on the page. To reorder:

    python3 tools/build_photography.py --list
    python3 tools/build_photography.py --move 4 1   # move item 4 to the top

A normal run rebuilds the page:

    python3 tools/build_photography.py
"""

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "content" / "photography.json"
OUT = ROOT / "photography" / "index.html"
SITE = "https://rahuljanardhanan.com"


def esc(value):
    return html.escape(str(value), quote=True)


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def save(data):
    DATA.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def photo_html(photo):
    image = esc(photo["image"])
    alt = esc(photo.get("alt", ""))
    caption = esc(photo.get("caption", ""))
    link = photo.get("link", "").strip()
    size = ""
    if photo.get("width") and photo.get("height"):
        size = f' width="{int(photo["width"])}" height="{int(photo["height"])}"'
    inner = (
        f'<img src="../{image}" alt="{alt}"{size} loading="lazy">\n'
        f"            <span>{caption}</span>"
    )
    if link:
        return (
            f'          <a class="photo-tile" href="../{esc(link)}">\n'
            f"            {inner}\n"
            f"          </a>"
        )
    return (
        f'          <div class="photo-tile">\n'
        f"            {inner}\n"
        f"          </div>"
    )


def post_html(post):
    if not post:
        return ""
    return f"""        <ul class="post-list">
          <li class="post-item">
            <a class="post-link" href="../{esc(post["href"])}">
              <span class="post-thumb" aria-hidden="true"><span>Photo</span></span>
              <span class="post-date"><time datetime="{esc(post["date"])}">{esc(post["date_label"])}</time></span>
              <span class="post-title">{esc(post["title"])}</span>
              <span class="post-summary">{esc(post["summary"])}</span>
            </a>
          </li>
        </ul>
"""


def build(data):
    photos = "\n".join(photo_html(photo) for photo in data["photos"])
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(data["title"])} — Rahul Janardhanan</title>
  <meta name="description" content="{esc(data["intro"])}">
  <meta name="theme-color" content="#000000">
  <link rel="canonical" href="{SITE}/photography/">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
</head>
<body id="top">
  <a class="skip" href="#main">Skip to content</a>

  <header class="site-header">
    <div class="shell header-inner">
      <a class="brand" href="../">Rahul Janardhanan</a>
      <nav class="header-nav" aria-label="Main">
        <a href="../portfolio/">Portfolio</a>
        <a href="./" aria-current="page">Photography</a>
        <a href="../blog/">Blog</a>
      </nav>
    </div>
  </header>

  <main id="main">
    <section class="blog-hero">
      <div class="shell">
        <h1>{esc(data["title"])}</h1>
        <p>{esc(data["intro"])}</p>
      </div>
    </section>

    <section class="section" aria-labelledby="work-heading">
      <div class="shell">
        <div class="section-head">
          <h2 id="work-heading">Selected work</h2>
        </div>

        <div class="photo-grid">
{photos}
        </div>
      </div>
    </section>

    <section class="section" aria-labelledby="read-heading">
      <div class="shell">
        <div class="section-head">
          <h2 id="read-heading">From the blog</h2>
        </div>
{post_html(data.get("post"))}        <p class="card-links"><a href="../portfolio/projects/portrait-photography/">All photography projects</a></p>
      </div>
    </section>
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(data['photos'])} photos")


def main():
    data = load()
    args = sys.argv[1:]

    if args and args[0] == "--list":
        for index, photo in enumerate(data["photos"], start=1):
            print(f"{index:2d}. {photo.get('caption', '')} — {photo['image']}")
        return

    if args and args[0] == "--move":
        if len(args) != 3:
            raise SystemExit("usage: --move FROM TO (1-based positions)")
        start, end = int(args[1]), int(args[2])
        count = len(data["photos"])
        if not (1 <= start <= count and 1 <= end <= count):
            raise SystemExit(f"positions must be between 1 and {count}")
        item = data["photos"].pop(start - 1)
        data["photos"].insert(end - 1, item)
        save(data)
        print(f"moved item {start} to position {end}")

    build(data)


if __name__ == "__main__":
    main()
