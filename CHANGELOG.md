# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-09-05

### Fixed

- **The integration still called itself iPIXEL throughout the interface.** The
  1.0.0 rename only changed the domain string, so the discovery dialog read
  "Confirm iPIXEL Device", the options flow "iPIXEL Color options", and every
  device appeared as "LED Matrix Display von iPIXEL". Config flow, options flow
  and both translations are rewritten.
- **Device info claimed a manufacturer that does not exist.** These panels are
  sold under several brands and the protocol reports none, so the field is gone
  rather than guessed. Model is now "LED Pixel Panel".
- The "no devices found" message now names the actual cause: a panel connected
  to a phone app stops advertising and cannot be discovered.
- 118 internal identifiers renamed from the `iPIXEL*` prefix to `BleLedPixel*`.
  The emoji cache moved to `.storage/ble_led_pixel_emoji_cache`.

## [1.0.2] - 2026-09-05

### Fixed

- **Blocking filesystem calls on the event loop.** Home Assistant flagged
  `get_available_fonts()` for scanning font directories synchronously while
  building the font selector — including a recursive walk of the system font
  paths. The 1.0.1 font rework made it worse, because `resolve_font_for_library()`
  now runs on every text change. Font locations are scanned once during
  `async_setup` in an executor thread and cached in an index; lookups afterwards
  take about a microsecond instead of touching the disk.
- **Device registration still said "von iPIXEL".** 1.0.1 dropped the field
  rather than overwriting it, and Home Assistant keeps the previous value when
  a field is omitted. Devices now report `LED_BLE` — what the panels actually
  call themselves in their advertising — instead of an invented manufacturer.

## [1.1.0] - 2026-09-05

### Added

- **Automatic reconnect after the Bluetooth link drops.** Until now a lost
  connection stayed lost until the config entry was reloaded by hand, which is
  what happened after every Home Assistant restart when the panel was not in
  the Bluetooth cache at setup time. Adapted from the work of arcdrake22 in
  upstream PR #44, rebuilt on this fork's client architecture:
  - `ensure_connected()` restores the link and never raises, serialized through
    a connect lock so several entities updating at once cannot stampede the radio
  - when the panel has fallen out of Home Assistant's Bluetooth cache,
    `async_rediscover_address()` is triggered and the lookup retried
  - a watcher subscribes to the panel's advertisements and reconnects the moment
    it reappears, backed by a retry loop with growing delay (5s to 30s)
  - commands retry once after a successful reconnect instead of failing silently

### Changed

- **Setup no longer aborts when the panel is unreachable.** A BLE panel that is
  briefly out of range would fail the whole config entry with
  `ConfigEntryNotReady`, leaving no entities and nothing watching for its
  return. Setup now completes, the entities exist immediately, and the watcher
  connects as soon as the panel advertises.

## [1.1.1] - 2026-09-05

### Fixed

- **The reconnect loop delayed Home Assistant's start-up.** 1.1.0 scheduled it
  with `async_create_task()`, which Home Assistant counts towards the start-up
  phase and waits for — while the loop is meant to run indefinitely. Start-up
  ran into its timeout and logged "Something is blocking Home Assistant from
  wrapping up the start up phase". It now runs as a background task.

## [Unreleased]

### Added

- **Fonts are resolved to file paths** instead of relying on pypixelcolor's
  built-in font names, which change between library versions. Any font in the
  integration's `fonts/` folder, the pypixelcolor package or a system font path
  works, in every mode and in `send_text`, with `VCR_OSD_MONO` as the fallback.
- **`show_emoji`** action, rendering any emoji via Twemoji (PR #37 by bastooky)
- **Options flow to override the panel size** when the firmware reports it wrong
  (PR #38 by bastooky), plus a French translation
- Font metric JSON sidecars for the bundled pixel fonts (PR #24 by scyto)

### Fixed

- **Device info is now retried three times** with a 10 second timeout instead of
  being queried once with 5 seconds, falling back to 64x16 defaults and an error
  in the log when all attempts fail (PR #30 by casef007). Adapted: the PR drove
  the GATT characteristics directly and cycled notifications per attempt; kept
  the persistent-subscription helper and took only the retry behaviour.
- **The clock used the host's naive local time**, which is UTC on most Home
  Assistant installations, so the panel clock was off by the timezone offset
  (PR #32 by MobilGame06)
- **The font size setting was ignored** in native text mode (PR #35 by BAERnado)
- Removed the `display_text` declaration from `services.yaml`. It described an
  action that was never registered anywhere; `send_text` is the working
  equivalent.

### Not merged

- **PR #31** (buffer-safe chunked writes) chunks at 20 bytes with fixed delays,
  while the client inherited from tigers75 already chunks at 244 bytes with
  per-window ACKs. Merging it would have been a regression.

### Changed

- **Forked** from [cagcoach/ha-ipixel-color](https://github.com/cagcoach/ha-ipixel-color)
  (upstream inactive since 2025-12-16) and renamed: domain `ipixel_color` -> `ble_led_pixel`,
  integration name "iPIXEL Color" -> "BLE LED Pixel Display". The new domain allows running
  this integration alongside the original one, so devices can be migrated one at a time.
  All actions are now called `ble_led_pixel.*`.
- Merged the image, MDI icon and layout work from
  [tigers75/ha-ipixel-color](https://github.com/tigers75/ha-ipixel-color).

### Fixed

- **Selected font was silently ignored in text mode.** `_update_text_mode` resolves fonts
  only against the integration's own `fonts/` folder, while the font selector is populated
  from that folder *plus* the pypixelcolor package *plus* system font paths. Picking a font
  that lives outside the integration therefore fell back to `CUSONG` without any notice.
  `VCR_OSD_MONO` is now shipped with the integration, so selecting it actually applies it.
- **Pinned `pypixelcolor` to `>=0.4.0,<0.5`.** The requirement was open-ended, and
  pypixelcolor has since removed the `CUSONG`, `SIMSUN` and `VCR_OSD_MONO` fonts from the
  package (only `unifont.otf` remains). The first release above 0.4.0 would have pulled
  those fonts out from under any existing installation.

### Fixed

- All `ble_led_pixel.*` actions (`send_mdi_icon`, `send_text`, `send_layout`, `send_test_pattern`,
  `send_image_file`) are now registered once at integration setup (`async_setup` in
  `__init__.py`, via the new `services.py`) instead of per-config-entry inside `text.py`'s
  `async_setup_entry`, per Home Assistant's own guidance
  (https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/).
  Previously, an action only existed in Home Assistant's service registry once a specific
  device's config entry had finished loading - automations validated before that (typically
  during Home Assistant startup) could be briefly flagged with "unknown action", even though
  the action worked correctly moments later once setup completed. The entity methods
  themselves (`async_send_mdi_icon`, etc.) are unchanged; only where and how they're
  registered changed, using `homeassistant.helpers.service.async_register_platform_entity_service`.
- `send_layout`'s word-wrap now falls back to splitting character-by-character when a single
  space-free "word" (e.g. a long digit string or ID with no natural spaces) is wider than the
  available width on its own. Previously such text was kept whole and allowed to overflow
  past the panel edge instead of wrapping to a new line.
- `send_layout`'s text `align` ('right'/'center') now actually anchors the corresponding edge
  or center of the text block at `x` (e.g. `align: right` makes the text's right edge land at
  `x`, extending leftward). Previously `align` only affected how multiple `\n`-separated lines
  aligned relative to each other within the block, leaving single-line text always anchored by
  its left edge regardless of `align` - so e.g. a right-aligned single line at `x=32` could run
  off the panel's edge instead of ending at `x=32` as expected.

### Added

- Bundled a new font, `Lepidos` (3x7 pixel font, CC0/public domain, by SurrealEmber -
  https://surrealember.itch.io/lepidos), designed to be rendered at multiples of 16px for
  crisp, correctly-proportioned glyphs.
- New service `ble_led_pixel.send_mdi_icon`: renders any Material Design Icon (fetched on
  demand from the jsDelivr mirror of `@mdi/svg`, no bundling required) and displays it
  centered on the panel, with configurable color, background color, size, and save slot.
- New service `ble_led_pixel.send_text`: sends text via pypixelcolor's native renderer
  (device animation/scroll/speed/rainbow), independent of the `text.{device}_display`
  entity's stored state - safe to call repeatedly from automations.
- New service `ble_led_pixel.send_layout`: composes up to 4 independent MDI icons, a static
  image/GIF-first-frame, and/or up to 4 independent text elements, each at independent (x, y)
  positions, onto a single canvas:
  - Up to 4 icons can be given via the new `icons` list field (YAML-only); the original flat
    `icon`/`icon_x`/... fields remain for a single icon and are ignored if `icons` is given.
    Icons never scroll, but can blink.
  - Text supports dynamic font sizing (any pixel size, including fractional), bundled pixel
    fonts (`3x5-de`, `5x5`, `7x5`, `Lepidos`, plus `OpenSans-Light` and `WP7xn`), automatic
    word-wrap at the panel's edge, forced line breaks via `\n` (works both as a real newline
    from YAML and as a literal backslash-n typed into a plain GUI text field), and
    left/right/center alignment (`align`/`text_align`) within the text's own block.
  - Text width is now measured via the font's advance metrics rather than its ink bounding
    box, so leading/trailing/internal spaces are preserved (useful for manual alignment via
    code) instead of being invisibly trimmed away. Word-wrapping still reflows text and does
    not preserve exact spacing - disable wrap if exact spacing matters.
  - Text too wide to fit can scroll continuously (looping marquee GIF, `scroll: true`)
    instead of being clipped, with configurable shared speed and loop gap.
  - Any icon or text can blink on/off (`blink: true`, `blink_interval_ms`), independent of and
    combinable with scrolling. Multiple scrolling and/or blinking elements are kept in sync
    with each other (their cycles realign together, via the least common multiple of their
    individual cycle lengths, capped to avoid runaway frame counts).
  - Up to 4 texts can be given via the new `texts` list field (YAML-only); the original flat
    `text`/`text_x`/... fields remain for a single text and are ignored if `texts` is given.
  - An existing image or GIF file (its first frame, if animated) can be inserted alongside
    the icons/text via `image_path`, with optional resizing.
  - Templates in `text`/`icon` resolve when the service is called from an automation/script
    (Home Assistant's own engine renders them before the call); they do not resolve if typed
    literally into the Developer Tools → Actions test field, and these services are one-shot
    (no auto-update on sensor changes) - see the README for details.
  - Native device-side text scrolling (`ble_led_pixel.send_text`, below) remains lighter/faster
    but always takes over the whole panel as a single string - it cannot be combined with an
    icon/image/other text, since the device protocol has no sub-region concept; scrolling
    *within* a layout composition is only achievable via generated GIF frames, which is
    inherently heavier to transfer than the native path. Measured: `scroll_step` is the one
    parameter that reliably reduces transfer size/time (doubling it roughly halves both frame
    count and bytes); frame deduplication and palette quantization were also added, though
    they mainly help short text with long pauses rather than a single long scrolling word.
  - The BLE ACK timeout for image/GIF sends (`send_mdi_icon`, `send_layout`,
    `send_test_pattern`, `send_image_file`) was raised from pypixelcolor's 8s default to 25s -
    a complex multi-frame GIF (e.g. several simultaneously-scrolling texts) can need more time
    for the device to process before it acknowledges, and would otherwise fail with
    `cur12k_no_answer: no ack from device` even though the transfer itself was fine.
- New service `ble_led_pixel.send_image_file`: sends an existing image or GIF file (read from
  disk, e.g. under `/config/www/`) as-is - PNG, GIF (including animated, frame-by-frame with
  original durations), JPEG, BMP, TIFF, WEBP, HEIC/HEIF.
- New diagnostic service `ble_led_pixel.send_test_pattern`: sends a 4-quadrant colored test
  image sized to the panel, to help verify how the device's reported width/height maps onto
  the physical panel.

### Changed

- `send_layout` text rendering now thresholds to pure black/white instead of using FreeType's
  default anti-aliasing, which was blurring the crisp square edges pixel-style fonts are
  meant to have on an LED matrix. Applies regardless of font or size.
- `bluetooth/client.py`: replaced the previous per-call `stop_notify`/`start_notify` churn
  with a single persistent Bluetooth notification subscription and a persistent `AckManager`
  for the whole connection lifetime, matching pypixelcolor's own reference
  `DeviceSession`/`Client`. The previous pattern (tearing down and re-enabling the ACK
  listener around every single command) was a likely source of dropped ACKs on real
  hardware, and caused a hard failure in `get_device_info()`
  (`Notifications are already enabled`).
- `get_device_info()` now goes through `BluetoothClient` instead of touching the raw `bleak`
  client/characteristics directly.
- `device/image.py`: `make_image_command()` now forwards `save_slot` through to
  pypixelcolor's `send_image_hex` (previously silently dropped), and returns the raw
  `SendPlan` object so callers can use the new chunked+ACK transport correctly for
  multi-byte image payloads.

### Dependencies

- Added `resvg_py` for SVG-to-PNG rasterization of MDI icons (self-contained wheel, no
  system-level SVG library dependency).

### Notes

- Tested against a real device (64x16 reported / 32x32 physical panel): `send_mdi_icon`,
  `send_text`, `send_layout` (static and scrolling), `send_image_file`, and
  `send_test_pattern` all confirmed working, including automatic text wrapping and forced
  line breaks. Large/complex GIFs may need a longer device-side processing time; see the
  README's troubleshooting section for `cur12k_no_answer` errors.

## [0.1.0] - 2024-11-19

### Added

- Initial release of iPIXEL Color Home Assistant integration
- Bluetooth auto-discovery of iPIXEL devices (`LED_BLE_*` pattern)
- Basic power on/off control via switch entity
- Manual device configuration as fallback
- Proper Home Assistant device registry integration
- Connection management with error handling
- Configuration flow with discovery and manual entry options
- English translations and UI strings

### Technical Details

- Implements core Bluetooth protocol commands based on reverse-engineered documentation
- Uses `bleak` library for cross-platform Bluetooth Low Energy communication
- Follows Home Assistant integration best practices
- Power commands: `[5, 0, 7, 1, 1]` (on) / `[5, 0, 7, 1, 0]` (off)
- Bluetooth UUIDs:
  - Write: `0000fa02-0000-1000-8000-00805f9b34fb`
  - Notify: `0000fa03-0000-1000-8000-00805f9b34fb`

### Limitations

- Only basic power control in this version
- No brightness, color, or image upload features yet
- Single switch entity per device

### Coming in Future Versions

- v0.2.0: Brightness control and basic light entity
- v0.3.0: RGB color control and display modes
- v0.4.0: Image/GIF upload and media player entity
- v1.0.0: Complete feature set and HACS submission
