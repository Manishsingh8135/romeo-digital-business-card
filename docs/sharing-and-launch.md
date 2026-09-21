# Sharing and launch checklist

## Implemented

- Initial-response Open Graph metadata, X large-image card tags, canonical URL, description, locale, and image alt text.
- A matching 1200 × 630 JPEG social image with a content-derived filename to help refresh cached previews.
- Organization, founder, and webpage structured data using public business details; no invented reviews, certifications, social handles, or apartment address.
- Native share menu on a direct user action. Unsupported or failed sharing offers WhatsApp/email composers and copying. Cancelling is quiet; no unsupported delivery claims.
- Copy confirmation only after clipboard success; an editable-selection fallback remains available when clipboard access is denied.
- QR codes generated from the same configured URL as metadata, share actions, and vCard. Downloadable QR and card images.
- A UTF-8 vCard 3.0 with CRLF line endings, byte-safe folding, a stable UID, and business contact details. The person must confirm import in their contacts app.
- Phone, email, website, and shop links; no assumption that the business phone is registered with WhatsApp.
- Favicon, Apple touch icon, home-screen manifest, maskable icons, and a QR shortcut. Installation availability is controlled by the browser.
- Offline shell after first successful production visit. Network responses are preferred while online; an offline message explains that shop/messaging need a connection. A copied contact does not automatically sync when the website changes.
- Best-effort screen wake lock while the QR is visible, released when it closes or the page becomes hidden.
- Stationary front-facing default, no pointer-following tilt or ambient motion, reduced-motion support, keyboard controls, focus return, hidden-panel inert states, and no-JavaScript contact links.
- Self-hosted runtime assets, no analytics cookies, and generated security/MIME headers.

## Verification so far

Automated tests cover sharing, cancellation, denied copying, offline-worker behavior, metadata and image dimensions, local asset references, vCard syntax/escaping, and URL consistency. The artifact verifier catches stale source/output before deployment.

Browser checks covered desktop, 390px and 320px layouts, front/reverse, contact slip, sharing pass, focus handling, and successful clipboard copying. Assets loaded without console errors in the inspected session. Actual contacts-app import has not been verified. A browser download check was stopped when download permission was declined; it was not retried through another route.

## Before public distribution

1. Confirm the final subdomain and public business details. Update `site.config.json` if needed, rebuild, and push.
2. Deploy the repository and connect the intended domain. Confirm HTTPS, public crawler access without authentication, and the configured canonical URL.
3. Check the HTML and social image return 200 with correct MIME types for ordinary requests and social crawlers. Ensure the live page contains metadata before JavaScript executes.
4. Paste the public URL into iMessage, WhatsApp, Facebook/LinkedIn, and X to inspect actual previews. Platforms can cache old data or crop images differently; local metadata tests are not proof of platform rendering.
5. Scan the QR on a real iPhone and Android phone. Open/import the vCard and check name, company, phone, email, and URLs. Check native share cancellation and clipboard fallback in mobile/in-app browsers.
6. Test home-screen launch, QR shortcut, and offline reopening after a successful online visit. Confirm reconnecting refreshes changed data.
7. Set `indexable` to `true` if search visibility is wanted, then rebuild and deploy. Retest public metadata after changes.

## Optional later

A physical NFC card/tag can carry the same HTTPS URL; the site does not need a Web NFC permission prompt. Purchase/program/test the actual tag separately. Device-to-device contact transfer and wallet passes are separate platform capabilities, not something this webpage can universally promise. Social profile links can be added once the correct public accounts are supplied.

## Source references

- [Open Graph protocol](https://ogp.me/)
- [Apple: rich previews for Messages](https://developer.apple.com/documentation/technotes/tn3156-create-rich-previews-for-messages/)
- [MDN: Web Share](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share)
- [vCard 3.0](https://www.rfc-editor.org/rfc/rfc2426)
- [MDN: installable web apps](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)
