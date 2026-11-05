#!/usr/bin/env python3
"""Build the blog from content/blog/*.md.

Each post is a Markdown file with front matter:

    ---
    title: A post title
    date: 2026-10-19
    summary: One sentence for the list page.
    lead: placeholder        # or media/blog/<slug>/photo.jpg
    notion_id: optional
    ---

Run after editing or after a Notion sync:

    python3 tools/build_blog.py
"""

import html
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "blog"
OUT = ROOT / "blog"
SITE = "https://rahuljanardhanan.com"
INTRO = "Notes on design, animation, photography, and building small apps."


def esc(value):
    return html.escape(str(value), quote=True)


def parse_front(text):
    fields = {}
    body = text
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        for line in front.splitlines():
            if ":" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields, body.strip("\n")


def inline(text):
    """Escape and convert the small Markdown subset Notion produces."""
    text = esc(text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}"'
        + (' target="_blank" rel="noopener noreferrer"' if m.group(2).startswith("http") else "")
        + f">{m.group(1)}</a>",
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def image_tag(src, alt, prefix):
    url = src if src.startswith(("http://", "https://", "/")) else prefix + src
    return (
        f'<figure class="figure"><img src="{esc(url)}" alt="{esc(alt)}" '
        f'loading="lazy"></figure>'
    )


def render_markdown(md, prefix):
    lines = md.splitlines()
    out = []
    para = []

    def flush():
        if para:
            text = inline(" ".join(part.strip() for part in para))
            if re.fullmatch(r'<a [^>]+>.*</a>', text):
                out.append(f'<p class="link-line">{text}</p>')
            else:
                out.append(f"<p>{text}</p>")
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            i += 1
            continue
        if stripped.startswith("## "):
            flush()
            out.append(f"<h2>{inline(stripped[3:])}</h2>")
            i += 1
            continue
        if stripped.startswith("### "):
            flush()
            out.append(f"<h3>{inline(stripped[4:])}</h3>")
            i += 1
            continue
        if stripped.startswith("# "):
            flush()
            out.append(f"<h2>{inline(stripped[2:])}</h2>")
            i += 1
            continue
        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image:
            flush()
            out.append(image_tag(image.group(2), image.group(1), prefix))
            i += 1
            continue
        if stripped.startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue
        if stripped.startswith("> "):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote.append(lines[i].strip()[2:])
                i += 1
            out.append(f"<blockquote><p>{inline(' '.join(quote))}</p></blockquote>")
            continue
        if re.fullmatch(r"https?://\S+", stripped):
            flush()
            url = esc(stripped)
            out.append(
                f'<p class="link-line"><a href="{url}" target="_blank" '
                f'rel="noopener noreferrer">{url}</a></p>'
            )
            i += 1
            continue
        para.append(line)
        i += 1
    flush()
    return "\n\n".join(out)


def date_label(value):
    return value.strftime("%-d %B %Y")


def load_posts():
    posts = []
    if not CONTENT.exists():
        return posts
    for path in sorted(CONTENT.glob("*.md")):
        fields, body = parse_front(path.read_text(encoding="utf-8"))
        try:
            published = date.fromisoformat(fields.get("date", ""))
        except ValueError:
            continue
        summary = fields.get("summary", "").strip()
        if not summary:
            for line in body.splitlines():
                if line.strip() and not line.startswith(("#", "-", "!", ">")):
                    summary = re.sub(r"[*_`\[\]]", "", line.strip())
                    break
        posts.append(
            {
                "slug": path.stem,
                "title": fields.get("title", path.stem),
                "date": published,
                "summary": summary,
                "lead": fields.get("lead", ""),
                "body": body,
            }
        )
    posts.sort(key=lambda item: (item["date"], item["title"]), reverse=True)
    return posts


def head(title, description, canonical):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#000000">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../../styles.css">
</head>"""


def nav():
    return """  <header class="site-header">
    <div class="shell header-inner">
      <a class="brand" href="../../">Rahul Janardhanan</a>
      <nav class="header-nav" aria-label="Main">
        <a href="../../portfolio/">Portfolio</a>
        <a href="../../photography/">Photography</a>
        <a href="../" aria-current="page">Blog</a>
      </nav>
    </div>
  </header>"""


def footer():
    return """  <footer class="site-footer">
    <div class="shell footer-inner">
      <div>
        <p class="footer-name">Rahul Janardhanan</p>
        <p class="footer-meta">Design · Animation · Video · Photo</p>
      </div>
      <a class="footer-top" href="#top">Back to top</a>
    </div>
  </footer>"""


def post_page(post):
    lead = ""
    if post["lead"] == "placeholder":
        lead = '        <figure class="post-lead" aria-hidden="true"><span>Photo placeholder</span></figure>\n\n'
    elif post["lead"]:
        lead = (
            '        <figure class="post-lead"><img src="../../'
            + esc(post["lead"])
            + '" alt="" loading="lazy"></figure>\n\n'
        )
    prose = render_markdown(post["body"], "../../")
    doc = f"""{head(post["title"] + " — Rahul Janardhanan", post["summary"], f"{SITE}/blog/{post['slug']}/")}
<body id="top">
  <a class="skip" href="#main">Skip to content</a>

{nav()}

  <main id="main">
    <article class="section article">
      <div class="shell">
        <nav class="crumbs" aria-label="Breadcrumb">
          <a href="../">Blog</a>
          <span aria-hidden="true">/</span>
          <span>{esc(post["title"])}</span>
        </nav>

        <h1>{esc(post["title"])}</h1>
        <p class="post-date"><time datetime="{post["date"].isoformat()}">{date_label(post["date"])}</time></p>

{lead}        <div class="prose">
{prose}
        </div>
      </div>
    </article>
  </main>

{footer()}
</body>
</html>
"""
    target = OUT / post["slug"] / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")


def index_page(posts):
    items = []
    for post in posts:
        thumb = '<span class="post-thumb" aria-hidden="true"><span>Photo</span></span>'
        if post["lead"] and post["lead"] != "placeholder":
            thumb = (
                '<span class="post-thumb" aria-hidden="true">'
                f'<img src="../{esc(post["lead"])}" alt="" loading="lazy"></span>'
            )
        items.append(
            f"""          <li class="post-item">
            <a class="post-link" href="{post["slug"]}/">
              {thumb}
              <span class="post-date"><time datetime="{post["date"].isoformat()}">{date_label(post["date"])}</time></span>
              <span class="post-title">{esc(post["title"])}</span>
              <span class="post-summary">{esc(post["summary"])}</span>
            </a>
          </li>"""
        )
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Blog — Rahul Janardhanan</title>
  <meta name="description" content="{esc(INTRO)}">
  <meta name="theme-color" content="#000000">
  <link rel="canonical" href="{SITE}/blog/">
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
        <a href="../photography/">Photography</a>
        <a href="./" aria-current="page">Blog</a>
      </nav>
    </div>
  </header>

  <main id="main">
    <section class="blog-hero">
      <div class="shell">
        <h1>Blog</h1>
        <p>{esc(INTRO)}</p>
      </div>
    </section>

    <section class="section" aria-labelledby="posts-heading">
      <div class="shell">
        <h2 class="visually-hidden" id="posts-heading">Posts</h2>
        <ul class="post-list">
{chr(10).join(items)}
        </ul>
      </div>
    </section>
  </main>

{footer()}
</body>
</html>
"""
    (OUT / "index.html").write_text(doc, encoding="utf-8")


def main():
    posts = load_posts()
    OUT.mkdir(parents=True, exist_ok=True)
    for post in posts:
        post_page(post)
    index_page(posts)
    print(f"wrote {len(posts)} posts and blog/index.html")


if __name__ == "__main__":
    main()
