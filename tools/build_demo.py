#!/usr/bin/env python3
"""Build the isolated /demo/ landing preview from content/landing-demo.md.

The preview is a design draft. It has its own stylesheet (demo/demo.css),
its own copy (content/landing-demo.md), and its own output folder, so it
never touches the production homepage (index.html), styles.css, the
generated portfolio/blog pages, or the Notion sync.

Run from the repo root:

    python3 tools/build_demo.py
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY_MD = ROOT / "content" / "landing-demo.md"
PORTRAIT = ROOT / "demo" / "rahul-portrait.jpg"
OUT = ROOT / "demo" / "index.html"

ICON_MAIL = (
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/>'
    '<path d="m3 7 9 6 9-6"/></svg>'
)
ICON_INSTAGRAM = (
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/>'
    '<circle cx="12" cy="12" r="4"/>'
    '<circle cx="17.3" cy="6.7" r="0.6" fill="currentColor" stroke="none"/></svg>'
)
ICON_X = (
    '<svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
    '<path d="M18.24 2.25h3.31l-7.23 8.26 8.5 11.24h-6.65l-5.22-6.82-5.97 6.82'
    'H1.67l7.73-8.84L1.25 2.25h6.83l4.71 6.23 5.45-6.23Zm-1.16 17.52h1.83'
    'L7.08 4.13H5.12l11.96 15.64Z"/></svg>'
)

FIELD_RE = re.compile(r"^([a-z][a-z0-9_-]*)\s*:\s*(.+)$")


def esc(value):
    return html.escape(str(value), quote=True)


def read_copy():
    fields = {
        "title": "Rahul Janardhanan",
        "greeting": "hi, I'm",
        "description": "",
        "portrait": "rahul-portrait.jpg",
        "email": "",
        "instagram": "",
        "x": "",
    }
    if not COPY_MD.exists():
        return fields
    for line in COPY_MD.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = FIELD_RE.match(line.strip())
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def split_name(title):
    parts = title.split()
    if len(parts) < 2:
        return title, ""
    return parts[0], " ".join(parts[1:])


def social_html(fields):
    items = []
    if fields["email"]:
        items.append(
            f'      <li><a href="mailto:{esc(fields["email"])}" aria-label="Email">{ICON_MAIL}</a></li>'
        )
    if fields["instagram"]:
        items.append(
            f'      <li><a href="{esc(fields["instagram"])}" target="_blank" '
            f'rel="noopener noreferrer" aria-label="Instagram">{ICON_INSTAGRAM}</a></li>'
        )
    if fields["x"]:
        items.append(
            f'      <li><a href="{esc(fields["x"])}" target="_blank" '
            f'rel="noopener noreferrer" aria-label="X">{ICON_X}</a></li>'
        )
    return "\n".join(items)


def build(fields):
    first, rest = split_name(fields["title"])
    subject = f'<span class="hero-name">{esc(first)}</span>'
    if rest:
        subject = f"{subject} {esc(rest)}"
    cards = "\n".join(
        '      <div class="demo-card" aria-hidden="true"></div>' for _ in range(3)
    )
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Landing preview — {esc(fields["title"])}</title>
  <meta name="description" content="Preview of a new landing page design.">
  <meta name="robots" content="noindex, nofollow">
  <meta name="theme-color" content="#000000">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Sue+Ellen+Francisco&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="demo.css">
</head>
<body class="demo" id="top">
  <a class="skip" href="#main">Skip to content</a>

  <main id="main" class="demo-main">
    <div class="hero">
      <img class="hero-portrait" src="{esc(fields["portrait"])}" alt="Portrait of {esc(fields["title"])}" width="899" height="900">
      <h1 class="hero-title">
        <span class="hero-greeting">{esc(fields["greeting"])}</span>
        <span class="hero-subject">{subject}</span>
      </h1>
    </div>

    <p class="demo-intro">{esc(fields["description"])}</p>

    <section class="demo-articles" aria-label="Articles coming soon">
{cards}
    </section>

    <ul class="demo-social">
{social_html(fields)}
    </ul>
  </main>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    missing = [] if PORTRAIT.exists() else [str(PORTRAIT.relative_to(ROOT))]
    return missing


def main():
    missing = build(read_copy())
    print(f"wrote {OUT.relative_to(ROOT)}")
    for path in missing:
        print(f"missing portrait: {path}")


if __name__ == "__main__":
    main()
