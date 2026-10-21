# rahuljanardhanan.com

The site root is a short personal page. The portfolio lives at `/portfolio/`.

## Edit the landing page

Open `content/landing.md` and change the title, intro, email, or social links. Then rebuild:

```bash
python3 tools/build_pages.py
```

The intro line is based on the portfolio wording Design, Animation, Video, and Photo.

## Add or reorder photography

The photography page is built from `content/photography.json`. The order of the `photos` list is the order on the page. Each photo has an image path, alt text, caption, and optional link.

```bash
python3 tools/build_photography.py --list       # show the current order
python3 tools/build_photography.py --move 4 1   # move item 4 to the top
python3 tools/build_photography.py              # rebuild the page
```

## Edit the portfolio in Notion

The source page is [Rahul Janardhanan / Portfolio](https://raonehere.notion.site/Rahul-Janardhanan-Portfolio-6a818cbd5bdb4e199949b0603267a09d).

Change text, add a project, or replace an image or video there. The designed portfolio homepage (`portfolio/index.html`) is laid out by hand. Project and category pages are generated from `content/pages/`.

A Notion subpage titled **Landing** or **About** can override the landing intro the next time a sync runs. If that page does not exist, `content/landing.md` stays in charge.

## Blog and photography in Notion

Both are optional. If the matching page is missing, the local files stay in charge.

**Blog.** Add a page titled **Blog** under the portfolio page in Notion. Each child page becomes a post: the page title is the post title, the creation date is the post date, and the first paragraph becomes the list summary. The sync writes one Markdown file per post to `content/blog/` and rebuilds the blog.

**Photography.** Add a page titled **Photography** under the portfolio page and put the photos in it as image blocks, in the order you want. Drag the blocks to reorder. The image caption becomes the tile caption. To make a tile link somewhere, end the caption with a vertical bar and the link:

```text
Light Painting | portfolio/projects/light-painting-portraits/
```

The sync downloads the images to `media/photography/` and rewrites `content/photography.json`.

The sync is additive: deleting a post or photo in Notion does not delete the local copy. Remove the local file yourself if you want it gone.

## Sync Notion to the site

From a checkout:

```bash
python3 tools/notion_sync.py --dry-run   # show what would change
python3 tools/notion_sync.py --apply     # write pages, fetch new media, rebuild HTML
```

When `NOTION_TOKEN` is set, every request goes to the official API at `api.notion.com` (with the `Notion-Version` header). File links come back on those blocks. Public `notion.so` endpoints are used only when the token is unset. Those public calls are rate limited and have been returning HTTP 429.

HTTP 429 and 5xx responses are retried up to 6 times with exponential backoff and jitter. A `Retry-After` header is honored. There is a short pause between page fetches.

New videos are compressed with ffmpeg (`scale` to at most 1280px wide, H.264 CRF 28, AAC 96k, faststart). Files already on disk are left alone until the Notion block changes.

GitHub Actions runs the same command every day at 06:00 UTC and whenever you start **Sync portfolio from Notion** from the Actions tab. The workflow passes the Actions secret `NOTION_TOKEN` into the script. If anything changed, it commits to `main`, and GitHub Pages republishes.

The workflow needs permission to push to `main`. The daily run stays reliable only after the secret below is set. An empty secret falls back to the public endpoints.

## Add the NOTION_TOKEN secret

1. Open [Notion integrations](https://www.notion.so/my-integrations) and create an internal integration. Copy its token (it starts with `ntn_` or `secret_`).
2. Open the portfolio page **Rahul Janardhanan / Portfolio** (`6a818cbd-5bdb-4e19-9949-b0603267a09d`). Choose **Connections** (or the `…` menu → **Connect to**) and add that integration.
3. Sharing that one page is enough. Notion gives the integration the page and every child page nested under it. This portfolio has no databases. Project and category pages are children of the root, so they do not need their own connection. A page that is only linked, and lives somewhere else in the workspace, would need to be shared separately.
4. In this GitHub repo, open **Settings → Secrets and variables → Actions → New repository secret**. Name it exactly `NOTION_TOKEN` and paste the integration token.
5. Run **Sync portfolio from Notion** from the Actions tab, or locally: `NOTION_TOKEN=secret python3 tools/notion_sync.py --apply`.

## Old project URLs

Pages that used to live at `/projects/<slug>/` now live at `/portfolio/projects/<slug>/`. The old addresses are small redirect pages, so existing links still open the project.
