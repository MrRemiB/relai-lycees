---
name: "Relai Lycées"
description: "Built geographic mission console for simulated lycée replacements."
colors:
  navy: "#142638"
  primary: "#087b70"
  primary-hover: "#05655c"
  selection: "#7252bb"
  canvas: "#f4f7f9"
  surface: "#fff"
  text: "#203347"
  muted: "#54677a"
  line: "#dbe3ea"
  input-border: "#c9d5df"
  quiet: "#eef3f6"
  quiet-text: "#284158"
  quiet-hover: "#e0e9ef"
  secondary-text: "#31495e"
  rail-text: "#cdd9e5"
  rail-active: "#2a4055"
  brand-accent: "#63d4c4"
  link: "#315e96"
  school: "#456580"
  cluster: "#365a77"
  cluster-halo: "#c9d9e8"
  selected-row: "#f0edf8"
  map-canvas: "#e8eef0"
  demo-bg: "#eaf3f2"
  demo-text: "#315750"
  tag-bg: "#edf3f6"
  tag-text: "#496171"
  open-bg: "#fff1d7"
  open-text: "#80541b"
  assigned-bg: "#e3f2ee"
  assigned-text: "#11685b"
  closed-bg: "#edf1f5"
  closed-text: "#516577"
  message-bg: "#eef4f7"
  message-border: "#bccfda"
  error-bg: "#fff2ee"
  error-text: "#973429"
  error-border: "#eac5b8"
  success-bg: "#e9f6f1"
  success-text: "#126558"
  success-border: "#b7d6cc"
  text-selection: "#dcd2f2"
  backdrop: "#14263880"
typography:
  body:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif"
    fontSize: "14px"
  headline:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif"
    fontSize: "25px"
    fontWeight: 750
    letterSpacing: "-.7px"
  panel-title:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif"
    fontSize: "21px"
    letterSpacing: "-.4px"
  school-title:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif"
    fontSize: "17px"
    lineHeight: "1.35"
  label:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif"
    fontSize: "12px"
    fontWeight: 650
  distance:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif"
    fontSize: "13px"
    fontWeight: 700
  help:
    fontFamily: "-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif"
    fontSize: "12px"
    lineHeight: "1.6"
rounded:
  tag: "4px"
  field: "5px"
  button: "6px"
  dialog: "10px"
  circle: "50%"
spacing:
  px-7: "7px"
  px-8: "8px"
  px-9: "9px"
  px-10: "10px"
  px-12: "12px"
  px-14: "14px"
  px-15: "15px"
  px-16: "16px"
  px-18: "18px"
  px-20: "20px"
  px-22: "22px"
  px-24: "24px"
  px-26: "26px"
  px-28: "28px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.button}"
    padding: "12px 15px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary-text}"
    rounded: "{rounded.button}"
    padding: "10px"
  button-secondary-hover:
    backgroundColor: "{colors.quiet}"
  button-quiet:
    backgroundColor: "{colors.quiet}"
    textColor: "{colors.quiet-text}"
    rounded: "{rounded.button}"
    padding: "0 14px"
  button-quiet-hover:
    backgroundColor: "{colors.quiet-hover}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.field}"
    padding: "9px 10px"
  navigation:
    backgroundColor: "transparent"
    textColor: "{colors.rail-text}"
    rounded: "{rounded.button}"
    width: "62px"
  navigation-active:
    backgroundColor: "{colors.rail-active}"
    textColor: "{colors.surface}"
  simulation-tag:
    backgroundColor: "{colors.tag-bg}"
    textColor: "{colors.tag-text}"
    rounded: "{rounded.tag}"
    padding: "5px 7px"
  candidate:
    padding: "15px 0"
  need-open:
    backgroundColor: "{colors.open-bg}"
    textColor: "{colors.open-text}"
    rounded: "{rounded.tag}"
    padding: "4px 7px"
---

# Design System: Relai Lycées

## Overview

**Creative North Star: "Geographic mission console"**

A cool slate-white operational canvas pairs a deep navy utility rail with an opaque white mission workspace. Teal marks compatible profiles and primary actions; violet distinguishes the selected lycée. Firm borders and compact labels carry the hierarchy instead of ornamental gradients or glow.

This is an Operate interface. The system UI workhorse stack is intentional for task completion, not a remote display-font dependency. The implementation uses no remote fonts and no generated illustrations; externally requested OpenStreetMap raster tiles are geographic content, not owned brand imagery.

**Key Characteristics:**
- Map plus mission workspace, not KPI-card composition.
- Navy navigation, teal actions, violet selection, white surfaces.
- Compact system UI typography and 44px minimum main controls.
- Explicit simulation, sector, state and distance text.

This is a source-extracted record of `static/index.html`, `static/styles.css`, `static/app.js` and `static/utils.js`, reconciled with PRODUCT.md and the workspace direction contract. No implementation files were edited. Browser rendering and tests were not run for this documentation pass. CSS declarations, rather than sampled computed styles, are authoritative here; browser defaults and vendored Leaflet internals remain dependencies, not new house tokens.

## Colors

### Primary
Teal (`primary`) colors the main action, compatible-profile marker, distance, active-tab underline, checkbox and dashed geographical link. The primary hover darkens; it does not glow.

### Secondary
Violet (`selection`) colors the selected lycée marker, initial identity symbol, caret and keyboard focus. The selected directory row uses `selected-row`; text selection uses `text-selection`.

### Neutral
Navy anchors the rail. White is the topbar, controls, directory and mission surface; the cool canvas remains behind the shell. `text`, `muted`, `line` and `input-border` separate hierarchy without excessive elevation. Slate `school` dots and numbered clusters are distinct from violet selection and teal candidates. `brand-accent` is confined to the wordmark dot.

### State colors
Amber `open-*`, teal `assigned-*` and gray `closed-*` are paired with “À pourvoir”, “Affectation simulée” and “Clôturé”. Error and success messages use their own foreground/background/border triplets and explanatory text. The persistent demo strip has separate subdued teal tokens.

**The Text Before Color Rule.** Sector and workflow state must remain readable as text; marker color alone is not a sector key.

## Typography

One installed-system stack serves the app. No `@font-face`, font CDN or remote font request is present. Root size is 14px; controls inherit it. This is a system UI workhorse for Operate, not an expressive display pairing.

- Main heading: headline token; subtitle is 14px/500 on wide screens, 12px and block-level at 1100px and below.
- Mission heading: panel-title token, 23px at 800px and below.
- School identity: school-title token. Result and empty-state headings are also 17px.
- Labels, tabs, help, school rows and status badges: 12px. Field labels and school names use 650 weight; base buttons use 600.
- Candidate name: 13px; distance: 13px/700 with tabular numerals.
- Need title: 14px; dialog heading: 22px; dialog subheading: 15px; dialog prose: 13px with 1.7 line height.
- Help and identity prose: 1.6 line height; reasons and exclusions: 1.7. Root body line height is not explicitly set; do not invent a universal leading scale.

The 38px/800 wordmark (33px on mobile) is a logo treatment, not a reusable system display role. SVG line icons are local and text-labelled; no icon font is required.

## Layout

Wide shell: flex layout with a 78px vertical navy rail, 88px white topbar and minimum 36px demo banner. Operations use `minmax(0,1fr) 400px`: fluid geography alongside a fixed mission panel. Mission padding is 22px 24px; its height is `calc(100vh - 124px)` with its own overflow. The map is `calc(100vh - 347px)`, minimum 390px. This is not a fixed-height, overflow-hidden application shell: the page can grow.

Filters use three columns (`minmax(160px,1fr) minmax(130px,.65fr) 110px`), 12px gaps and 20px 22px 14px padding. The map toolbar wraps only at the smaller breakpoint. Directory rows use two columns and a 175px capped scrolling list. Mission dates and numeric fields use two equal columns and 12px gaps; field separation is 13px. The spacing entries are observed repeated dimensions, not a fabricated mathematical scale.

- **At least 1600px:** mission padding becomes 25px 28px; map minimum height becomes 480px; filter top padding becomes 24px.
- **At most 1100px:** rail is 66px; mission is 370px with 20px padding; filters use two columns with full-width search and 15px padding; toolbar wraps; map height is 440px (minimum still applies); directory uses one column; main subtitle moves below title.
- **At most 800px:** rail becomes a 64px horizontal bar; topbar is 82px; demo copy wraps; map precedes directory and mission in a single operations column. Mission becomes auto-height, page-scrolled, with a top border and 24px 20px padding. Map height is 390px, minimum reset to zero. Directory returns to two columns, capped at 170px. Sources navigation retains its SVG and title but hides visible text. Selecting a school scrolls to the mission; tab navigation focuses it.
- **At most 360px:** directory and candidate actions each use one column; mission padding is 22px 16px; rail, filters and legend tighten; toolbar count gets its own row; scenario button can wrap; dialog heading wraps. Paired mission fields remain two columns.

Source dialog width is `min(680px,calc(100% - 32px))`, maximum height 85vh, padding 26px. Metadata remains a 150px/remaining-width definition-list grid even on narrow screens: no mobile override is implemented.

## Elevation & Depth

Most application surfaces are flat white with fine dividers. Depth is reserved for map pins and the modal, plus upstream Leaflet control/tooltip treatments.

- Map pin shadow: `0 2px 5px #00000026`.
- Dialog shadow: `0 12px 24px #00000026`.
- Dialog backdrop: `backdrop` token.

No app CSS transition or decorative animation is defined. JS debounces search by 230ms and uses Leaflet navigation and mobile scroll. Reduced-motion CSS disables transitions, animations and smooth scroll; selection and result framing explicitly consult reduced motion. Candidate-link fitting and territory changes do not explicitly pass a reduced-motion option: do not claim complete map-motion suppression.

## Shapes

Main buttons use the button radius; inputs, messages and legend use the field radius; compact state/count tags use the tag radius; the modal uses the dialog radius. Directory rows and tabs are square-edged, divided rather than raised. Pins are circles with white borders: ordinary school 10px/2px border, selected school 23px/3px border, compatible profile 17px/3px border. Their Leaflet interactive containers are 44px square. Zoom links are overridden to 44px square.

## Components

### Buttons and navigation
Primary is white text on teal with 12px 15px padding; hover uses primary-hover. Secondary is white, outlined input-border, with 10px padding and quiet hover. Quiet is slate-tinted, outlined line, with horizontal 14px padding and quiet-hover. Base button minimum height is 44px. Candidate buttons use 12px type and 8px padding. Disabled buttons use opacity .55 and a not-allowed cursor; no dedicated active or disabled palette is defined.

Rail items combine 22px outlined SVGs and 12px labels, 62px width and minimum 66px height. Active and hover share rail-active with white content. On mobile they become horizontal with 19px icons and minimum 48px height. Tabs expose aria-selected, an active teal bottom border and navy text; arrow keys, Home and End move selection and focus. There is no CSS-only hover treatment for tabs.

### Inputs and focus
Inputs/selects are white with input-border, 9px 10px padding, minimum 44px height and field radius. A 3px violet focus-visible outline, offset 3px, applies to buttons, inputs, selects and links; summary receives the outline without an explicitly declared offset. Checkbox uses an 18px native control within a 44px minimum label and teal accent. Fieldset is disabled until school selection or during processing. Validation uses native form validity plus readable date/error messages; there is no custom invalid-field border or custom disabled-input style.

### Directory and identity
School row buttons show the name, city and sector; selected rows expose aria-pressed and selected-row background, also used on hover. Public is the default sector filter; private is selected via the filter; all sectors also include unknowns. Unknown sector is explicitly “Statut non renseigné”. **There are no public/private/unknown sector-specific icons in the shipped build.** Uniform slate school markers encode neither sector nor status. Text in the directory and identity panel is the non-color distinction; do not infer sector from dots or invent a sector icon legend.

The initial school identity has a violet outlined building SVG and instructional empty state; selection replaces it with title, academy/sector/address/UAI and the official-directory link. Schools lacking coordinates remain selectable from the directory, with a clear geography limitation. List starts with 60 results and loads 60 more per request.

### Map and legend
Leaflet is vendored; raster tiles come from OpenStreetMap with visible attribution. Numbered clusters use slate plus a pale halo. Legend labels describe lycée, selection and compatible profile—not sector. Size and text support the color distinction, but the three legend swatches themselves are the same circle size. Failure to load the map library exposes a list-oriented fallback and disables map framing/territory controls; tile failure can show an error while points and list stay available.

Candidate link is teal, weight 2, dash pattern `6 7`, with permanent distance tooltip explicitly labelled “à vol d’oiseau · pas un itinéraire”. Only the chosen candidate link is shown; rendering matches chooses the nearest candidate first. Do not describe all shortlisted profiles as simultaneously connected.

### Candidates, needs and messages
Candidate articles use top dividers and 15px vertical padding, not raised cards. They show distance, fictitious administrative base, capacity, textual eligibility reasons and map/simulated-assignment actions. At most ten nearest compatible profiles render. Exclusions use native details/summary, reason counts and at most forty individual details.

Need rows use bottom dividers, 17px vertical padding and text-labelled state chips. Open needs can recalculate or close; assigned needs can release; closed needs can be consulted. Busy controls disable actions and change preview text to “Traitement en cours…”. Saved state changes button wording and disables repeat save. Empty lists explain recovery; API failures show readable messages and bootstrap retry. Global/form status containers use polite live regions. There is no skeleton animation.

### Sources dialog and calendar
Native modal dialog opens from navigation or footer, closes via Fermer, native Escape or outside-bound click. Its source/privacy copy distinguishes official institutions from fictitious profiles and local simulations, and discloses external tile requests. Calendar hints are ordinary help text, not blocking alerts: they preserve Europe/Paris date interpretation, explain coverage limits and link to official data. Metadata is rendered from the source, including license; this record adds no new license claim.

## Do's and Don'ts

### Do:
- **Do** preserve labelled simulation and source/limitations access.
- **Do** pair sector and need states with words, not color alone.
- **Do** reuse the implemented control sizes, focus outline and compact system UI stack.
- **Do** keep distances labelled as straight-line, never road journeys.

### Don't:
- **Don’t** describe the demo as authenticated or officially endorsed.
- **Don’t** invent sector-specific marker icons: the shipped map markers do not encode sector.
- **Don’t** treat preview-only tonal ramps as shipped CSS tokens.
- **Don’t** add remote font requirements or decorative gradients to this recorded world.

Documentation limitations: extracted from source, not a new rendered accessibility certification. Native field states, font metrics and Leaflet's shipped assets/CSS depend on browser/platform and vendor implementation. The sidecar's eight-step tonal ramps are derived preview metadata only, not implementation colors. No generated brand raster is present in these inspected frontend sources. Sector icons and custom field-error styles are absent, not silently documented as features. No UI defects were repaired or legitimized by changing tokens.
