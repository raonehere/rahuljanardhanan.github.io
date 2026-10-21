#!/usr/bin/env python3
"""Pull Rahul's public Notion portfolio into content/pages and media/.

Uses the official Notion API when NOTION_TOKEN is set. Otherwise it reads the
public page through Notion's loadPageChunk and getSignedFileUrls endpoints.

Then it runs tools/build_pages.py.

  python3 tools/notion_sync.py --dry-run
  python3 tools/notion_sync.py
"""

import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "content" / "pages"
MEDIA = ROOT / "media"
STATE_PATH = ROOT / "content" / "notion-sync-state.json"
LANDING = ROOT / "content" / "landing.md"
BLOG_DIR = ROOT / "content" / "blog"
PHOTO_DATA = ROOT / "content" / "photography.json"
ROOT_PAGE = "6a818cbd-5bdb-4e19-9949-b0603267a09d"
NOTION_VERSION = "2022-06-28"
# One try plus retries. 429 and 5xx back off; other status codes fail immediately.
MAX_HTTP_ATTEMPTS = 6
PAGE_FETCH_DELAY = 0.4


def norm_id(value):
    return re.sub(r"[^0-9a-f]", "", (value or "").lower())


def dashed(value):
    raw = norm_id(value)
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def unwrap(record):
    value = record.get("value") or {}
    if isinstance(value, dict) and isinstance(value.get("value"), dict):
        return value["value"]
    return value if isinstance(value, dict) else {}


def notion_token():
    return os.environ.get("NOTION_TOKEN", "").strip()


def official_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
    }


def parse_retry_after(value, now=None):
    """Return a wait in seconds from a Retry-After header, or None."""
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return max(0.0, (when - current).total_seconds())


def backoff_seconds(attempt, retry_after=None):
    """Exponential backoff with jitter. Honor Retry-After when Notion sends one.

    attempt is 0 for the first retry. Caps a single wait at 60 seconds.
    """
    if retry_after is not None:
        base = min(60.0, max(0.0, float(retry_after)))
        return base + random.random() * 0.25
    base = min(60.0, 2 ** attempt)
    return base + random.random() * base * 0.3


def _retryable_status(code):
    return code == 429 or 500 <= code <= 599


def http_json(url, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    last_error = None
    for attempt in range(MAX_HTTP_ATTEMPTS):
        req = urllib.request.Request(url, data=data)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        if payload is not None and not req.has_header("Content-type"):
            req.add_header("Content-Type", "application/json")
        if not req.has_header("User-agent"):
            req.add_header("User-Agent", "Mozilla/5.0")
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            last_error = error
            try:
                error.read()
            except Exception:
                pass
            if not _retryable_status(error.code) or attempt == MAX_HTTP_ATTEMPTS - 1:
                raise
            retry_after = None
            if error.headers is not None:
                retry_after = parse_retry_after(error.headers.get("Retry-After"))
            wait = backoff_seconds(attempt, retry_after)
            print(
                f"HTTP {error.code} from {url.split('?')[0]} ; retry {attempt + 1} in {wait:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise last_error


def load_public_chunks(page_id):
    time.sleep(PAGE_FETCH_DELAY)
    blocks = {}
    for number in range(0, 6):
        data = http_json(
            "https://www.notion.so/api/v3/loadPageChunk",
            {
                "page": {"id": dashed(page_id)},
                "limit": 100,
                "cursor": {"stack": []},
                "chunkNumber": number,
                "verticalColumns": False,
            },
        )
        before = len(blocks)
        for record in data.get("recordMap", {}).get("block", {}).values():
            block = unwrap(record)
            if block.get("id") and block.get("type"):
                blocks[block["id"]] = block
        if len(blocks) == before:
            break
    return blocks


def fetch_public(root_id):
    blocks = {}
    queue = [dashed(root_id)]
    seen = set()
    while queue:
        page_id = queue.pop(0)
        if page_id in seen:
            continue
        page = blocks.get(page_id)
        if page and all((child in blocks) for child in (page.get("content") or [])):
            seen.add(page_id)
            continue
        seen.add(page_id)
        blocks.update(load_public_chunks(page_id))
        for block in list(blocks.values()):
            if block.get("type") == "page" and block.get("id") not in seen:
                queue.append(block["id"])
    return blocks


def rich_public(parts, pages):
    if not parts:
        return ""
    out = []
    mentions = []
    other = []
    for part in parts:
        text = part[0]
        annotations = part[1] if len(part) > 1 else []
        page_id = next((item[1] for item in annotations if item and item[0] == "p"), None)
        href = next((item[1] for item in annotations if item and item[0] == "a"), None)
        bold = any(item and item[0] == "b" for item in annotations)
        if page_id:
            page = pages.get(norm_id(page_id))
            label = page["title"] if page else text
            slug = page["slug"] if page else "missing"
            mentions.append(f"[{label}]({slug}.md)")
            if text.strip() not in ("‣", ""):
                other.append(text)
            continue
        if not text.strip() and not href:
            continue
        if bold and href:
            other.append(f"[**{text}**]({href})")
        elif href:
            other.append(f"[{text}]({href})")
        elif bold:
            other.append(f"**{text}**")
        else:
            other.append(text)
    if mentions and not "".join(other).strip():
        return "LIST:" + " ".join(mentions)
    return "".join(mentions + other)


def file_name_from(block):
    source = source_url(block)
    if source.startswith("attachment:"):
        return source.split(":")[-1] or "file"
    if source.startswith("http"):
        return source.split("?")[0].rstrip("/").split("/")[-1] or "file"
    title = (block.get("properties") or {}).get("title")
    if title and title[0] and title[0][0]:
        return title[0][0]
    return "file"


def source_url(block):
    for key in ("source", "link"):
        value = (block.get("properties") or {}).get(key) or []
        if value and value[0]:
            return value[0][0]
    display = (block.get("format") or {}).get("display_source")
    return display or ""


def plain_title(block):
    parts = (block.get("properties") or {}).get("title") or []
    return "".join(part[0] for part in parts if part).strip()


def slugify(title):
    slug = title.lower()
    slug = slug.replace("&", " and ")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "page"


def existing_pages():
    found = {}
    if not PAGES.exists():
        return found
    for path in PAGES.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        _, front, body = text.split("---", 2)
        notion_id = ""
        for line in front.splitlines():
            if line.startswith("notion_id:"):
                notion_id = norm_id(line.split(":", 1)[1])
        found[notion_id] = {"path": path, "front": front, "body": body.strip("\n"), "text": text}
    return found


def index_pages(blocks):
    pages = {}
    for block in blocks.values():
        if block.get("type") != "page":
            continue
        title = plain_title(block) or "Untitled"
        pages[norm_id(block["id"])] = {
            "id": block["id"],
            "title": title,
            "slug": slugify(title),
        }
    # Keep slugs that are already on disk.
    for notion_id, item in existing_pages().items():
        if notion_id in pages:
            match = re.search(r'^slug:\s*"?(.*?)"?\s*$', item["front"], re.M)
            if match:
                pages[notion_id]["slug"] = match.group(1).strip('"')
            match = re.search(r'^title:\s*"(.*)"\s*$', item["front"], re.M)
            if match:
                pages[notion_id]["title"] = match.group(1)
    return pages


def existing_media_lines(body):
    return [line for line in body.splitlines() if line.strip().startswith("![](")]


def render_page_body(page_id, blocks, pages):
    page = blocks.get(dashed(page_id)) or blocks.get(page_id)
    if not page:
        return ""
    lines = [f"# {pages[norm_id(page_id)]['title']}", ""]
    root = norm_id(page_id) == norm_id(ROOT_PAGE)
    images = existing_media_lines(
        existing_pages().get(norm_id(page_id), {}).get("body", "")
    )
    image_at = 0

    def walk(block_id):
        nonlocal image_at
        block = blocks.get(block_id) or {}
        kind = block.get("type")
        if kind == "column":
            walk_children(block.get("content") or [])
            return
        if kind == "column_list":
            for child in block.get("content") or []:
                walk(child)
            return
        if kind in ("header", "sub_header", "sub_sub_header"):
            if root:
                level = "##"
            else:
                level = {"header": "#", "sub_header": "##", "sub_sub_header": "###"}[kind]
            lines.append(f"{level} {plain_title(block)}")
            return
        if kind == "text":
            rendered = rich_public((block.get("properties") or {}).get("title"), pages)
            if rendered.startswith("LIST:"):
                lines.append("- " + rendered[5:])
            elif rendered.strip():
                lines.append(rendered.rstrip())
            return
        if kind == "image":
            if image_at < len(images):
                lines.append(images[image_at])
                image_at += 1
            else:
                name = file_name_from(block)
                slug = pages[norm_id(page_id)]["slug"]
                lines.append(f"![](../media/{slug}/{name})")
            return
        if kind in ("video", "file", "audio"):
            url = source_url(block)
            if url.startswith("http") and not re.search(r"\.(mp4|mov|m4v|webm|pdf)(\?|$)", url, re.I):
                lines.append(url)
                return
            name = file_name_from(block)
            label = "video" if kind != "file" else "file"
            lines.append(f"*[Unavailable {label}: {name}]*")
            return
        if kind == "embed":
            url = source_url(block)
            if url and "embed.notion.co" not in url:
                lines.append(url)
            elif url:
                # display_source is the notion iframe; prefer the real source property
                raw = ((block.get("properties") or {}).get("source") or [[""]])[0][0]
                if raw:
                    lines.append(raw)
            return
        if kind in ("tweet", "bookmark"):
            lines.append(f"*[Unrendered Notion {kind} block, id {norm_id(block_id)}]*")
            return
        if kind == "page":
            info = pages.get(norm_id(block_id))
            if info and norm_id(block_id) != norm_id(page_id):
                lines.append(f"- [{info['title']}]({info['slug']}.md)")
            return
        if kind == "divider":
            lines.append("")
            return
        for child in block.get("content") or []:
            if child != block_id:
                walk(child)

    def walk_children(ids):
        index = 0
        ids = list(ids)
        while index < len(ids):
            block = blocks.get(ids[index]) or {}
            if block.get("type") == "text":
                label = rich_public((block.get("properties") or {}).get("title"), pages)
                nxt = blocks.get(ids[index + 1]) if index + 1 < len(ids) else {}
                if (
                    label
                    and not label.startswith("LIST:")
                    and "http" not in label
                    and len(label) < 48
                    and (nxt or {}).get("type") == "page"
                ):
                    lines.append(f"### {label.strip()}")
                    index += 1
                    continue
            walk(ids[index])
            index += 1

    walk_children(page.get("content") or [])
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def normalize(text):
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def signed_url(block):
    """Resolve a file URL. Official API when NOTION_TOKEN is set; public only otherwise."""
    url = source_url(block)
    token = notion_token()
    if token:
        if url.startswith("http"):
            return url
        data = http_json(
            f"https://api.notion.com/v1/blocks/{block['id']}",
            headers=official_headers(token),
        )
        kind = data.get("type")
        payload = data.get(kind) or {}
        file_info = payload.get("file") or payload.get("external") or {}
        return file_info.get("url") or payload.get("url") or ""
    if not url:
        return ""
    if url.startswith("http"):
        return url
    data = http_json(
        "https://www.notion.so/api/v3/getSignedFileUrls",
        {
            "urls": [
                {
                    "url": url,
                    "permissionRecord": {"table": "block", "id": block["id"]},
                }
            ]
        },
    )
    signed = data.get("signedUrls") or []
    return signed[0] if signed else ""


def compress_video(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(source),
            "-vf", "scale='min(1280,iw)':-2",
            "-c:v", "libx264", "-crf", "28",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            str(dest),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"blocks": {}}


def sync_media(blocks, pages, state, apply):
    changed = []
    for block in blocks.values():
        if block.get("type") not in ("image", "video", "file", "audio"):
            continue
        parent = pages.get(norm_id(block.get("parent_id", "")))
        # parent_id may be missing; skip download in dry-run
        version = str(block.get("version", ""))
        previous = state["blocks"].get(block["id"], {})
        if previous.get("version") == version and previous.get("path"):
            if (ROOT / previous["path"]).exists():
                continue
        if not apply:
            continue
        # Downloads happen on a real run only, and only for new or updated blocks.
        changed.append(block["id"])
    return changed


def official_enabled():
    return bool(os.environ.get("NOTION_TOKEN"))


def fetch_official_tree(root_id, token):
    """Official API fallback shape is converted into the public block dict."""

    def get_children(block_id):
        time.sleep(PAGE_FETCH_DELAY)
        results = []
        cursor = None
        while True:
            url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
            if cursor:
                url += f"&start_cursor={cursor}"
            data = http_json(url, headers=official_headers(token))
            results.extend(data.get("results") or [])
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    blocks = {}

    def rich_to_public(rich):
        parts = []
        for item in rich or []:
            annotations = []
            if item.get("annotations", {}).get("bold"):
                annotations.append(["b"])
            if item.get("href"):
                annotations.append(["a", item["href"]])
            if item.get("type") == "mention" and item.get("mention", {}).get("type") == "page":
                annotations.append(["p", item["mention"]["page"]["id"], ""])
                parts.append(["‣", annotations])
            else:
                parts.append([item.get("plain_text", ""), annotations] if annotations else [item.get("plain_text", "")])
        return parts

    type_map = {
        "paragraph": "text",
        "heading_1": "header",
        "heading_2": "sub_header",
        "heading_3": "sub_sub_header",
        "child_page": "page",
        "column_list": "column_list",
        "column": "column",
        "divider": "divider",
        "image": "image",
        "video": "video",
        "file": "file",
        "audio": "audio",
        "bookmark": "bookmark",
        "embed": "embed",
        "link_preview": "bookmark",
    }

    def convert(item):
        kind = type_map.get(item.get("type"), item.get("type"))
        payload = item.get(item.get("type"), {}) if item.get("type") else {}
        title = rich_to_public(payload.get("rich_text") or [])
        if item.get("type") == "child_page":
            title = [[payload.get("title") or "Untitled"]]
        file_info = payload.get("file") or payload.get("external") or {}
        source = file_info.get("url") or payload.get("url") or ""
        name = payload.get("name") or (source.split("/")[-1].split("?")[0] if source else "")
        block = {
            "id": item["id"],
            "type": kind,
            "properties": {},
            "content": [],
            "version": item.get("last_edited_time"),
            "created_time": item.get("created_time"),
            "last_edited_time": item.get("last_edited_time"),
            "parent_id": (item.get("parent") or {}).get("block_id") or (item.get("parent") or {}).get("page_id"),
        }
        caption = rich_to_public(payload.get("caption") or [])
        if caption:
            block["properties"]["caption"] = caption
        if title:
            block["properties"]["title"] = title
        if source:
            block["properties"]["source"] = [[source]]
            if name:
                block["properties"]["title"] = [[name]]
        blocks[item["id"]] = block
        if item.get("has_children") or item.get("type") in ("child_page", "column_list", "column"):
            children = get_children(item["id"])
            block["content"] = [child["id"] for child in children]
            for child in children:
                convert(child)

    root = http_json(
        f"https://api.notion.com/v1/blocks/{dashed(root_id)}",
        headers=official_headers(token),
    )
    convert(root)
    # The block endpoint does not include the page title; read the page.
    page = http_json(
        f"https://api.notion.com/v1/pages/{dashed(root_id)}",
        headers=official_headers(token),
    )
    title = ""
    props = page.get("properties") or {}
    for prop in props.values():
        if prop.get("type") == "title":
            title = "".join(part.get("plain_text", "") for part in prop.get("title") or [])
    blocks[dashed(root_id)]["properties"]["title"] = [[title or "Portfolio"]]
    blocks[dashed(root_id)]["type"] = "page"
    if not blocks[dashed(root_id)].get("content"):
        children = get_children(dashed(root_id))
        blocks[dashed(root_id)]["content"] = [child["id"] for child in children]
        for child in children:
            convert(child)
    return blocks


def maybe_landing(blocks, pages, apply):
    for page in pages.values():
        if page["title"].strip().lower() in ("landing", "about"):
            body = render_page_body(page["id"], blocks, pages)
            first = ""
            for line in body.splitlines():
                if line and not line.startswith("#"):
                    first = line
                    break
            if apply and first and LANDING.exists():
                text = LANDING.read_text(encoding="utf-8")
                text = re.sub(r"^intro:.*$", f"intro: {first}", text, count=1, flags=re.M)
                LANDING.write_text(text, encoding="utf-8")
            return page["title"]
    return None


def page_depth(page_id, blocks):
    depth = 0
    seen = set()
    current = blocks.get(dashed(page_id)) or blocks.get(page_id) or {}
    while True:
        parent = norm_id(current.get("parent_id", ""))
        if not parent or parent in seen or parent == norm_id(page_id):
            return depth
        seen.add(parent)
        depth += 1
        current = blocks.get(dashed(parent)) or blocks.get(parent) or {}


def find_section(pages, blocks, names, kind):
    """Find the Notion page used as the blog or photography source.

    kind is "page" for a blog index (children are posts) or "image" for a
    gallery (children are photos). Pages that do not contain the right kind
    of block are ignored, so a portfolio category with the same title does
    not win.
    """
    matches = []
    for page in pages.values():
        if page["title"].strip().lower() not in names:
            continue
        if norm_id(page["id"]) == norm_id(ROOT_PAGE):
            continue
        block = blocks.get(dashed(page["id"])) or blocks.get(page["id"]) or {}
        children = [
            blocks.get(dashed(child)) or blocks.get(child) or {}
            for child in (block.get("content") or [])
        ]
        score = sum(1 for child in children if child.get("type") == kind)
        if score:
            matches.append((page_depth(page["id"], blocks), -score, page))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1]))
    return matches[0][2]


def child_pages(page_id, pages, blocks):
    block = blocks.get(dashed(page_id)) or blocks.get(page_id) or {}
    found = []
    for child in block.get("content") or []:
        info = pages.get(norm_id(child))
        if info:
            found.append(info)
    return found


def descendant_blocks(page_id, blocks):
    page = blocks.get(dashed(page_id)) or blocks.get(page_id) or {}
    queue = list(page.get("content") or [])
    seen = set()
    while queue:
        child = queue.pop(0)
        if child in seen:
            continue
        seen.add(child)
        block = blocks.get(dashed(child)) or blocks.get(child) or {}
        if block:
            yield block
        queue.extend(block.get("content") or [])


def rich_text(parts):
    if not parts:
        return ""
    out = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
        elif part:
            out.append(part[0] or "")
    return "".join(out).strip()


def block_date(block):
    for key in ("created_time", "last_edited_time"):
        value = block.get(key)
        if isinstance(value, (int, float)):
            seconds = value / 1000 if value > 100000000000 else value
            try:
                return datetime.fromtimestamp(seconds, timezone.utc).date()
            except (OverflowError, OSError, ValueError):
                pass
        elif isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except ValueError:
                pass
    return datetime.now(timezone.utc).date()


def safe_filename(name, block_id):
    name = (name or "image").strip()
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, "jpg"
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower() or "image"
    ext = re.sub(r"[^a-zA-Z0-9]", "", ext).lower() or "jpg"
    digest = hashlib.sha1(block_id.encode()).hexdigest()[:8]
    return f"{stem[:48]}-{digest}.{ext}"


def ensure_media(block, folder, state, apply):
    """Download a Notion file once and return its site-relative path."""
    filename = safe_filename(file_name_from(block), block["id"])
    rel = (Path("media") / folder / filename).as_posix()
    dest = ROOT / rel
    version = str(block.get("version") or "")
    previous = state.setdefault("blocks", {}).get(block["id"], {})
    if dest.exists() and (not version or previous.get("version") == version):
        return rel
    if not apply:
        return rel if dest.exists() else None
    url = signed_url(block)
    if not url:
        return rel if dest.exists() else None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
    except Exception as error:
        print(f"  could not download {filename}: {error}")
        return rel if dest.exists() else None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    state["blocks"][block["id"]] = {"version": version, "path": rel}
    return rel


def read_front_matter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    _, front, body = text.split("---", 2)
    fields = {}
    for line in front.splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields, body.strip("\n")


def existing_blog():
    by_id, by_title = {}, {}
    if not BLOG_DIR.exists():
        return by_id, by_title
    for path in sorted(BLOG_DIR.glob("*.md")):
        fields, _ = read_front_matter(path)
        notion_id = norm_id(fields.get("notion_id", ""))
        if notion_id:
            by_id[notion_id] = path
        title = fields.get("title", "").strip().lower()
        if title:
            by_title.setdefault(title, path)
    return by_id, by_title


def plain_text(text):
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`#>]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def summarize(markdown):
    for line in markdown.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-", "!", "*", "|", ">")):
            continue
        text = plain_text(line)
        if text:
            if len(text) > 160:
                text = text[:157].rsplit(" ", 1)[0] + "…"
            return text
    return ""


def strip_title(markdown):
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).strip()


def separate_paragraphs(markdown):
    """Notion emits one line per block with no blank line between them."""
    out = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        if out and out[-1].strip():
            previous = out[-1].strip()
            block_starts = ("#", "-", "!", "|", ">")
            if not stripped.startswith(block_starts) and not previous.startswith(block_starts):
                out.append("")
        out.append(line)
    return "\n".join(out)


def localize_images(markdown, page_id, slug, blocks, state, apply):
    names = {}
    for block in descendant_blocks(page_id, blocks):
        if block.get("type") != "image":
            continue
        original = file_name_from(block)
        rel = ensure_media(block, f"blog/{slug}", state, apply)
        if rel and original not in names:
            names[original] = rel

    def replace(match):
        local = names.get(match.group(1))
        return f"![]({local})" if local else match.group(0)

    return re.sub(r"!\[\]\(\.\./media/[^/]+/([^)]+)\)", replace, markdown)


def split_caption(text):
    text = (text or "").strip()
    if "|" not in text:
        return text, ""
    caption, link = text.rsplit("|", 1)
    return caption.strip(), link.strip()


def sync_blog(blocks, pages, state, apply):
    section = find_section(pages, blocks, ("blog", "posts", "writing"), "page")
    if not section:
        return None
    posts = child_pages(section["id"], pages, blocks)
    if not posts:
        return section["title"]
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    by_id, by_title = existing_blog()
    changed = 0
    for info in posts:
        block = blocks.get(dashed(info["id"])) or blocks.get(info["id"]) or {}
        notion_id = norm_id(info["id"])
        path = by_id.get(notion_id)
        if path is None:
            # Adopt a local post with the same title the first time it
            # appears in Notion, so migrated posts keep their URL.
            candidate = by_title.get(info["title"].strip().lower())
            if candidate:
                fields, _ = read_front_matter(candidate)
                if not fields.get("notion_id"):
                    path = candidate
        if path is None:
            slug = info["slug"]
            counter = 2
            while (BLOG_DIR / f"{slug}.md").exists():
                slug = f"{info['slug']}-{counter}"
                counter += 1
            path = BLOG_DIR / f"{slug}.md"
        else:
            slug = path.stem
        body = strip_title(render_page_body(info["id"], blocks, pages))
        body = separate_paragraphs(body)
        body = localize_images(body, info["id"], slug, blocks, state, apply)
        published = block_date(block)
        if not block.get("created_time") and path.exists():
            fields, _ = read_front_matter(path)
            try:
                published = datetime.fromisoformat(fields.get("date", "")).date()
            except ValueError:
                pass
        new_text = (
            "---\n"
            f"title: {info['title']}\n"
            f"date: {published.isoformat()}\n"
            f"summary: {summarize(body)}\n"
            f"notion_id: {dashed(notion_id)}\n"
            "---\n\n"
            f"{body.rstrip()}\n"
        )
        old_text = path.read_text(encoding="utf-8") if path.exists() else ""
        if normalize(old_text) != normalize(new_text):
            changed += 1
            if apply:
                path.write_text(new_text, encoding="utf-8")
    if apply:
        print(f"blog: {len(posts)} posts in Notion, {changed} updated")
    return section["title"]


def sync_photography(blocks, pages, state, apply):
    section = find_section(pages, blocks, ("photography", "photos"), "image")
    if not section:
        return None
    images = [
        block
        for block in descendant_blocks(section["id"], blocks)
        if block.get("type") == "image"
    ]
    if not images or not PHOTO_DATA.exists():
        return section["title"]
    data = json.loads(PHOTO_DATA.read_text(encoding="utf-8"))
    photos = []
    for block in images:
        rel = ensure_media(block, "photography", state, apply)
        if not rel:
            continue
        caption, link = split_caption(
            rich_text((block.get("properties") or {}).get("caption"))
        )
        item = {"image": rel, "alt": caption or "Photograph", "caption": caption}
        if link:
            item["link"] = link
        photos.append(item)
    if apply and photos:
        data["photos"] = photos
        PHOTO_DATA.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"photography: {len(photos)} photos in Notion")
    return section["title"]


def main():
    dry = "--dry-run" in sys.argv or "--apply" not in sys.argv and os.environ.get("NOTION_SYNC_APPLY") != "1"
    # A normal invocation writes. --dry-run only reports.
    if "--dry-run" in sys.argv:
        dry = True
    elif "--apply" in sys.argv or os.environ.get("NOTION_SYNC_APPLY") == "1":
        dry = False
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if token:
        print("source: official Notion API")
        blocks = fetch_official_tree(ROOT_PAGE, token)
    else:
        print("source: public notion.site endpoints")
        blocks = fetch_public(ROOT_PAGE)
    pages = index_pages(blocks)
    print(f"pages in notion: {len(pages)}")
    state = load_state()
    current = existing_pages()
    changed = []
    missing = []
    for notion_id, page in pages.items():
        if notion_id not in current:
            missing.append(page["slug"])
            continue
        rendered = normalize(render_page_body(page["id"], blocks, pages))
        previous = normalize(current[notion_id]["body"])

        def semantic(text):
            return [line.rstrip() for line in text.splitlines() if line.strip()]

        if semantic(rendered) != semantic(previous):
            changed.append(current[notion_id]["path"].name)
            if dry:
                import difflib
                diff = list(difflib.unified_diff(
                    semantic(previous), semantic(rendered), lineterm="", n=0
                ))
                print(f"# {page['slug']} semantic-diff-lines={len(diff)}")
                if len(changed) <= 12:
                    print("\n".join(diff[:24]))
    landing = maybe_landing(blocks, pages, apply=not dry)
    blog_section = sync_blog(blocks, pages, state, apply=not dry)
    photo_section = sync_photography(blocks, pages, state, apply=not dry)
    print(f"unchanged pages: {len(pages) - len(changed) - len(missing)}")
    print(f"changed pages: {len(changed)}")
    print(f"new pages: {len(missing)}")
    if landing:
        print(f"landing subpage: {landing}")
    else:
        print("landing subpage: none (content/landing.md stays the source)")
    if blog_section:
        print(f"blog subpage: {blog_section}")
    else:
        print("blog subpage: none (content/blog stays the source)")
    if photo_section:
        print(f"photography subpage: {photo_section}")
    else:
        print("photography subpage: none (content/photography.json stays the source)")
    if dry:
        print("dry-run: no files written")
        return
    for notion_id, page in pages.items():
        if notion_id not in current:
            continue
        rendered = render_page_body(page["id"], blocks, pages).rstrip() + "\n"
        item = current[notion_id]
        new_text = "---" + item["front"] + "---\n\n" + rendered
        if normalize(new_text) != normalize(item["text"]):
            item["path"].write_text(new_text, encoding="utf-8")
    sync_media(blocks, pages, state, apply=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    for builder in ("build_pages.py", "build_blog.py", "build_photography.py"):
        subprocess.run([sys.executable, str(ROOT / "tools" / builder)], check=True)


if __name__ == "__main__":
    main()
