# Rojan Shrestha — Photography Portfolio

A static site, deployed on Netlify. `index.html` fetches `content/site.json`
at load time and renders the nav, home photo, work list, about text, and
contact info from it. Photos live as real files under `images/`,
referenced by path from `content/site.json` — nothing is embedded as
base64.

Live at: https://fantastic-squirrel-79889b.netlify.app

## Editing content

There's no admin panel — edit `content/site.json` directly (artist info,
about text, contact details, social links, piece titles) and add/remove
files under `images/` for photos. Commit and push, and Netlify redeploys
automatically within about a minute:

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
```

`index_1.html` and `Works/` (in the parent folder, git-ignored) are the
old single-file version and the original full-resolution source photos —
kept locally for reference, not part of the deployed site.
