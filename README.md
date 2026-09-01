# Rojan Shrestha — Photography Portfolio

A static site. `index.html` fetches `content/site.json` at load time and
renders the nav, home photo, work list, about text, and contact info from
it. Photos live as real files under `images/`, referenced by path from
`content/site.json` — nothing is embedded as base64. Two pieces also carry
interactive 3D scans (`.glb` files under `models/`), rendered with
Google's `<model-viewer>`.

**Live at: https://rojanshrestha.com** — served by GitHub Pages (Settings
→ Pages), which auto-rebuilds on every push to `main`. The `CNAME` file
at the repo root is what GitHub uses to route the custom domain; leave it
in place. The repo is public, which GitHub Pages requires for free
hosting.

The site is also mirrored at
https://rojan-shrestha-portfolio.pages.dev (Cloudflare Pages) as a second
host — that one does *not* auto-deploy on push; it's updated manually via
`npx wrangler pages deploy .` after a change, kept mainly as a fallback
since Netlify (the original host) hit a free-tier usage cap early on.

## Editing content

There's no admin panel — edit `content/site.json` directly (artist info,
about text, contact details, social links, piece titles) and add/remove
files under `images/` or `models/`. Commit and push, and the live site at
rojanshrestha.com rebuilds automatically within about a minute:

```
git add -A
git commit -m "describe the change"
git push
```

To add a whole new piece, add an entry to the `pieces` array in
`content/site.json` with a `title` and an `images` array of paths, and
put the actual photo files at those paths under `images/`.

## Local development

```
python3 -m http.server 8000
```
then open `http://localhost:8000`.

## Project structure

```
index.html            the site (fetches content/site.json)
content/site.json      all editable text content
images/                real photo files, organized per piece
models/                3D scans (.glb), for pieces that have one
CNAME                  custom domain for GitHub Pages — do not remove
```

`index_1.html` and `Works/` (in the parent folder, git-ignored) are the
old single-file version and the original full-resolution source photos —
kept locally for reference, not part of the deployed site.

## DNS

`rojanshrestha.com` points at GitHub Pages via four A records on `@`
(185.199.108–111.153) — see GitHub's docs if these ever need to be
re-added at the registrar. `www.rojanshrestha.com` is not currently
configured; add a CNAME for `www` → `rojansthaaa.github.io` at the
registrar if that variant should also resolve.
