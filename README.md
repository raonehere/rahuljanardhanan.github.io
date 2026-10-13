# rahuljanardhanan.com

The site root is a short personal page. The portfolio lives at `/portfolio/`.

## Edit the landing page

Open `content/landing.md` and change the title, intro, email, or social links. Then rebuild:

```bash
python3 tools/build_pages.py
```

The intro line is based on the portfolio wording Design, Animation, Video, and Photo.

## Edit the portfolio in Notion

The source page is [Rahul Janardhanan / Portfolio](https://raonehere.notion.site/Rahul-Janardhanan-Portfolio-6a818cbd5bdb4e199949b0603267a09d).

Change text, add a project, or replace an image or video there. The designed portfolio homepage (`portfolio/index.html`) is laid out by hand. Project and category pages are generated from `content/pages/`.

A Notion subpage titled **Landing** or **About** can override the landing intro the next time a sync runs. If that page does not exist, `content/landing.md` stays in charge.

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
