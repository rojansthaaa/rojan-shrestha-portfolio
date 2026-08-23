# Rojan Shrestha — Photography Portfolio

A static site. `index.html` fetches `content/site.json` at load time and
renders the nav, home photo, work list, about text, and contact info from
it. Photos live as real files under `images/`, referenced by path from
`content/site.json` — nothing is embedded as base64 anymore.

## Editing content

Once deployed (see below), go to `/admin` on the live site to edit:

- Artist name, role, email, phone, social links
- Home page hero photo
- About statement and facts
- Work categories (Editorial / Tearsheet labels and text)
- Pieces (projects) — title, and the list of photos in each one

Every save there commits a change to this git repo and the live site
rebuilds automatically within about a minute.

To add a whole new piece: open `/admin`, go to **Site Content → Pieces**,
click **Add**, give it a title and upload photos.

## First-time deployment (one-time setup)

1. **Push this repo to GitHub.** Create a new repo at github.com (private
   or public, your choice), then from this folder:
   ```
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
2. **Create a Netlify account** at netlify.com and choose "Add new site →
   Import an existing project," pointing it at the GitHub repo you just
   pushed. Leave the build settings blank — this is a plain static site,
   no build command needed. Deploy.
3. **Turn on Netlify Identity**: in the Netlify site dashboard, go to
   *Site configuration → Identity → Enable Identity*. Under registration,
   set it to **Invite only** (so strangers can't create editor accounts).
4. **Turn on Git Gateway**: still under Identity settings, scroll to
   *Services → Git Gateway → Enable Git Gateway*. This is what lets the
   `/admin` panel commit changes back to this repo on your behalf.
5. **Invite yourself as a user**: Identity tab → *Invite users* → enter
   your email. You'll get an email with a link to set a password.
6. Visit `https://<your-site>.netlify.app/admin`, log in, and you're
   editing live.
7. **Optional — custom domain**: *Domain settings* in Netlify lets you
   connect a domain you own, or buy one through them.

## Local development

```
python3 -m http.server 8000
```
then open `http://localhost:8000`. To test the `/admin` CMS panel locally
against this same repo (rather than a deployed one), run
`npx decap-server` in a second terminal — `admin/config.yml` already has
`local_backend: true` set for this.

## Project structure

```
index.html            the site (fetches content/site.json)
content/site.json      all editable text content, edited via /admin
images/                real photo files, organized per piece
admin/                 Decap CMS admin panel + config
```

`index_1.html` and `Works/` (in the parent folder, git-ignored) are the
old single-file version and the original full-resolution source photos —
kept locally for reference, not part of the deployed site.
