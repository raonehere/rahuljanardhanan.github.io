# EKA Forest: website v1
Static site (HTML + CSS + ~20 lines of JS). No build step. Fonts self-hosted.

Run locally: `python3 -m http.server 8080` in this folder, then open http://localhost:8080
Deploy: upload the folder to any static host (Netlify drop, Vercel, GitHub Pages, Cloudflare Pages).

- index.html: all content. Comments mark Figma nodes, NEW sections and ASSUMPTION/PLACEHOLDER items
- assets/styles.css: tokens (Figma + brand), desktop layout at Figma coordinates, tablet ≤1280, mobile ≤760
- assets/main.js: footer year, FAQ one-open-per-column, click-to-load Google Map
- CONTENT-NOTES.md: researched vs assumed content, placeholders to replace
- screenshots/: headless Chrome captures (1440 desktop, 390 mobile @2x, button hover)
