# Frontend

The frontend is server-rendered Django templates plus vanilla JavaScript and CSS.

## Template Files

- `templates/base.html`
  - Common layout.
  - Loads base CSS and light/dark theme CSS.
  - Loads Vanta/p5 scripts from jsDelivr.
  - Defines CSRF meta tag.
  - Header contains BSU logo and settings link.
  - Main content target is `#app-content`.
  - Defines `#extra-head` and `#extra-scripts` regions used by partial navigation.
- `templates/home.html`
  - Home grid.
  - New VM tile.
  - Placeholder Ubuntu tile.
  - Includes Create VM modal.
  - Loads `home.js` and `modals.js`.
- `templates/login.html`
  - Login card for AD-backed authentication.
  - Posts JSON to `/login/`.
  - Preserves safe `next` target in hidden input.
- `templates/settings.html`
  - Settings layout with General and Appearance sections.
  - Shows AD-derived account data.
  - Shows template creation access state.
  - Provides logout form.
  - Provides theme segmented control.
- `templates/partials/create_vm_modal.html`
  - Create VM modal scene.
  - Template selector.
  - VM name, hardware, bridge, VLAN, DHCP/static IPv4 fields.
  - Includes Create Template modal as the second scene.
- `templates/partials/create_template_modal.html`
  - Multi-step template wizard.
  - Steps:
    1. OS and ISO source
    2. Software
    3. Hardware
    4. Network
    5. Overview
    6. Build progress

## JavaScript Files

### `static/js/base.js`

Responsibilities:

- Theme preference cookie.
- Effective theme based on explicit light/dark/system.
- Theme stylesheet toggling.
- Calls Vanta reinit on theme changes.
- Same-origin partial navigation.
- Prefetch on `a[data-nav]` hover.
- History push/pop handling.
- Dynamic page head/script replacement.
- Calls `window.pageInit()` after a fragment swap when present.

Partial-navigation headers:

- Real navigation: `X-Requested-With: fetch`
- Hover prefetch: `X-Requested-With: prefetch`

### `static/js/login.js`

Responsibilities:

- Handles login form submit.
- Sends JSON to `/login/`.
- Includes CSRF token.
- Requires JSON response.
- Shows login errors in `#login-error`.
- Redirects to server-provided safe target on success.

### `static/js/modals.js`

Responsibilities:

- Opens/closes Create VM modal.
- Switches between VM scene and template creation scene.
- Drives the Create Template wizard.
- Implements custom select UI.
- Tracks ISO validation state.
- Fetches saved ISO/software sources.
- Inspects new ISO URLs and software URLs.
- Handles package-name software entries.
- Infers artifact types and install strategies client-side.
- Clears incompatible software when target OS changes.
- Builds validation payloads.
- Builds template create payloads.
- Posts to `POST /api/template/validate-software/`.
- Posts to `POST /api/template/create/`.
- Polls `GET /api/template/builds/<uuid>/status/`.
- Renders build timeline, recent activity, worker events, preflight checks, staged ISO assets, transfer progress, last error, and software install results.
- Loads available completed templates from `GET /api/template/list/`.
- Builds VM provisioning payloads.
- Posts to `POST /api/vm/start/`.
- Handles static IPv4 fields for VM provisioning.

Build stage order in JS:

- `queued`
- `preflight`
- `assets`
- `init`
- `validate`
- `build`
- `postprocess`
- `sealing`
- `done`

### `static/js/settings.js`

Responsibilities:

- Settings sidebar section switching.
- Hash persistence for active section.
- Theme segmented-control UI.
- Rebinds after partial navigation through `window.pageInit`.

### `static/js/helpers/vanta.js`

Responsibilities:

- Initializes Vanta topology background.
- Reads theme colors from CSS variables.
- Reinitializes on theme change.
- Reinitializes on resize.
- Avoids initialization when the Vanta element is not measurable.

### `static/js/home.js`

Currently a placeholder for home-specific interactions.

### `static/js/test.js`

Legacy/manual helper for a previous `#start-vm-btn` flow. The current Create VM modal uses `modals.js` and `POST /api/vm/start/`.

## CSS Files

- `static/css/base.css`
  - Global layout, Vanta background, header, logo/settings icon styling.
- `static/css/home.css`
  - Home tile grid and VM/template tiles.
- `static/css/login.css`
  - Login card/form styling.
- `static/css/modals.css`
  - Create VM/Create Template modal layout.
  - Wizard scenes/pages.
  - Buttons, inputs, custom select, saved software list.
  - Build progress UI.
  - Light theme overrides for modal surfaces.
- `static/css/settings.css`
  - Settings sidebar/content layout.
  - Account/access cards.
  - Theme segmented control.
- `static/css/themes/dark.css`
  - Dark theme CSS variables.
- `static/css/themes/light.css`
  - Light theme CSS variables.

## Assets

- `static/assets/images/bsu_logo.png`
- `static/assets/images/settings_icon.svg`

External runtime assets:

- `https://cdn.jsdelivr.net/npm/p5@1.9.0/lib/p5.min.js`
- `https://cdn.jsdelivr.net/npm/vanta@0.5.24/dist/vanta.topology.min.js`
- Ubuntu logo from Wikimedia in the placeholder home tile.

## Current User Interface Behavior

Home:

- Shows New VM tile.
- Opens Create VM modal.
- Includes a static Ubuntu tile that does not currently represent a live VM list.

Create VM:

- Loads only completed templates owned by the user.
- Applies template defaults to VM hardware/network fields.
- Allows DHCP or static network for the provisioned VM.
- Requires template, name, bridge, and valid static fields when static mode is selected.
- Displays provision result or error.

Create Template:

- Requires template name, build profile, inspected ISO URL, and network bridge before progressing.
- Windows profile reveals Windows-only fields.
- Template network mode is locked to DHCP-ready.
- Software entries can be URLs or Linux package names.
- Software compatibility changes based on target OS.
- Final step queues the build and changes into progress polling.

Settings:

- General tab is account/access information.
- Appearance tab sets light/dark/system preference.
- Classes and Resources are visible but disabled placeholders.

## Frontend Constraints

- Do not break `X-Requested-With` partial navigation.
- Do not introduce a frontend framework unless explicitly requested.
- Preserve server-rendered templates as source of truth for initial page HTML.
- Keep CSRF behavior intact for JSON POSTs.
- Keep modal API contracts aligned with `core/views.py`.
