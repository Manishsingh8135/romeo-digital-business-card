# Romeo’s Health Heaven · Digital business card

A light, tactile ivory card for Romeo’s Health Heaven. The card rests straight and still; deliberate actions flip it or reveal a sharing pass, contact slip, or small product collection.

## Stack

- **Frontend:** semantic HTML, custom CSS with 3D transforms, and vanilla JavaScript ES modules.
- **Browser features:** native Web Share, clipboard fallback, vCard download, screen wake lock while the QR is open where supported, and a service worker for offline access after a successful first visit.
- **Assets:** locally hosted DM Sans and Cormorant Garamond fonts, Lucide icons, existing brand artwork.
- **Build tools:** Python with Pillow for the social image/icons and Segno for QR codes. Node.js runs the local preview server, artifact checks, and JavaScript tests.
- **Hosting:** static files only. No React, Next.js, database, API server, paid API, or runtime package installation is required.

## Deploy on Vercel

Import this repository into Vercel as a new project. Keep the repository root as the root directory. The committed `vercel.json` sets:

| Setting | Value |
| --- | --- |
| Framework preset | Other |
| Build command | `node scripts/verify-dist.mjs` |
| Install command | Empty |
| Output directory | `dist` |
| Environment variables | None required |

The generated `dist/` directory is deliberately committed. Vercel verifies that it matches the source and then serves it; Python is needed only when regenerating the card. Vercel headers are generated alongside the HTML, including the structured-data CSP hash and contact-file MIME type.

**Before sharing publicly:** the configured address is currently `https://hello.romeoshealthheaven.com/`. Connect that exact domain to the Vercel project and wait for valid HTTPS, or change `cardUrl` in `site.config.json`, rebuild, and push. All share buttons, QR codes, canonical/OG URLs, and the contact file use this configured address, never the temporary preview URL. A Vercel preview can display the card before the custom domain works, but its share links still point to the configured domain.

`indexable` is currently `false`; the page requests `noindex, follow` while allowing social crawlers to fetch its metadata. Set it to `true` and rebuild when the public card should appear in search. That also generates a sitemap. No deployment or DNS change is included in this repository's initial upload.

Vercel documentation: [project configuration](https://vercel.com/docs/project-configuration/vercel-json).

## Other hosting

Any HTTPS static host can serve the contents of `dist/` at a domain root: Cloudflare Pages, Netlify, or the existing site's web hosting. `_headers` is included for hosts that support it; other hosts must apply the equivalent rules from `dist/headers.json`. GitHub Pages requires a custom domain at the root for this build; repository-subdirectory URLs are not supported by its root-relative assets.

## Preview locally

With Node.js 22 or newer:

```sh
npm run verify
npm run dev
```

Open `http://127.0.0.1:8767/`. No npm dependencies need to be installed. Local HTTP previews do not register the production service worker. Native share availability depends on the browser and device.

## Edit and rebuild

Use Python 3.12 or newer and a local virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/build.py
npm run verify
npm test
python -m unittest discover -s tests -p 'test_*.py'
```

On Windows, activate with `.venv\Scripts\activate` instead.

- `site.config.json`: public contact details, card URL, sharing metadata, indexing policy.
- `src/card.html`: card layout and copy.
- `src/styles.css`: responsive layout, depth, purposeful transitions, reduced-motion rules.
- `src/app.mjs`: card interactions and browser fallbacks.
- `scripts/build.py`: metadata, QR, vCard, preview image, icons, manifest, hosting headers, offline shell.
- `dist/`: generated deployment output. Rebuild rather than editing it directly.

Commit the source, regenerated `dist/`, and `vercel.json` together. A stale build fails Vercel's verification rather than silently publishing old contact details.

## Sharing and launch checks

See [the sharing checklist](docs/sharing-and-launch.md) for implemented features, local verification, and device/live-domain checks that remain before public distribution.

## Asset rights

Third-party font and icon licenses are retained under `assets/`. Montserrat is used only by the image generator; its license is beside that source font. Brand names, logos, and product artwork are not offered under an open-source license. No project-wide open-source license has been selected.
