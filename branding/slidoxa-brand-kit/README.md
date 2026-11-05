# Slidoxa Brand Asset Pack — Draft 01

This pack contains a vector app-icon concept and common platform exports.

## Design tokens

- Ink / dark background: `#0F1020`
- Primary violet: `#7A5AF8`
- Accent blue (optional): `#60A5FA`
- White: `#FFFFFF`
- Wordmark type direction: Plus Jakarta Sans Bold, lowercase `slidoxa`, violet `x`

## Icon concept

The standalone application mark is a custom-drawn, continuous S-ribbon in violet on a deep-ink rounded-square field. It is independent of the existing stacked-slide symbol. The foreground SVG is transparent for adaptive icon systems.

## Files

- `svg/slidoxa-app-icon.svg` — editable dark app icon source.
- `svg/slidoxa-app-icon-light.svg` — editable light app icon variant.
- `svg/slidoxa-app-icon-foreground.svg` — transparent foreground for adaptive icons.
- `svg/slidoxa-wordmark-light-template.svg` and `svg/slidoxa-wordmark-dark-template.svg` — editable text templates using Plus Jakarta Sans Bold. These are templates; keep the separately refined Inkscape wordmark files as the canonical wordmark artwork.
- `png/` — raster icon exports at common sizes.
- `windows/slidoxa.ico` — multi-resolution Windows icon.
- `macos/slidoxa.icns` — macOS icon container, when supported by this build environment.
- `web/` — favicon, Apple touch icon, PWA icons and web manifest.
- `android/` — adaptive-icon foreground/background resources and sample XML.
- `brand-colors.json`, `brand-tokens.css` — reusable brand colors.

## Integration notes

1. Keep the existing user-refined `slidoxa-wordmark-only.svg`, `slidoxa-wordmark-outlined.svg`, `slidoxa-wordmark.png`, and `slidoxa-wordmark-dark.png` files. Do not overwrite them with the wordmark templates in this pack.
2. Review the S-ribbon app icon at 16px, 32px, 48px, and 128px before replacing any existing production icon.
3. Replace product references only after approving the artwork and updating all relevant Electron, frontend, favicon, PWA, Windows, and macOS paths.
4. macOS may apply its own icon mask in some contexts; retain the full-square source and the rounded-square preview source.
5. The wordmark SVG templates use live text. They require Plus Jakarta Sans to be installed to match the intended design.

## Provenance and review

This is an assistant-created vector draft, not a human-only design. It has not been checked for trademark conflicts or similarity against all existing marks. Obtain human design review and trademark clearance before treating it as the final commercial identity.
