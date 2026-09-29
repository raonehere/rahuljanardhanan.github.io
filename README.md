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

Without a token, the sync reads the public page. New videos are compressed with ffmpeg (`scale` to at most 1280px wide, H.264 CRF 28, AAC 96k, faststart). Files already on disk are left alone until the Notion block changes.

GitHub Actions runs the same command every day at 06:00 UTC and whenever you start **Sync portfolio from Notion** from the Actions tab. If anything changed, it commits to `main`, and GitHub Pages republishes.

The workflow needs permission to push to `main`.

## Add NOTION_TOKEN (optional)

The public endpoints are enough for the published portfolio. The official API is used only when `NOTION_TOKEN` is set.

1. Open [Notion integrations](https://www.notion.so/my-integrations) and create an internal integration.
2. On the portfolio page, choose **Connections** and add that integration.
3. In this GitHub repo, open **Settings → Secrets and variables → Actions** and add a secret named `NOTION_TOKEN` with the integration token.
4. Run the **Sync portfolio from Notion** workflow, or export the secret locally and run `NOTION_TOKEN=secret python3 tools/notion_sync.py --apply`.

## Old project URLs

Pages that used to live at `/projects/<slug>/` now live at `/portfolio/projects/<slug>/`. The old addresses are small redirect pages, so existing links still open the project.
