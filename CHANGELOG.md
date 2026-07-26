# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New service `ipixel_color.send_mdi_icon`: renders any Material Design Icon (fetched on
  demand from the jsDelivr mirror of `@mdi/svg`, no bundling required) and displays it
  centered on the panel, with configurable color, background color, size, and save slot.
- New service `ipixel_color.send_text`: sends text via pypixelcolor's native renderer
  (device animation/scroll/speed/rainbow), independent of the `text.{device}_display`
  entity's stored state - safe to call repeatedly from automations.
- New service `ipixel_color.send_layout`: composes an MDI icon, a static image/GIF-first-frame,
  and/or text, each at independent (x, y) positions, onto a single canvas:
  - Text supports dynamic font sizing (any pixel size, including fractional), bundled pixel
    fonts (`3x5-de`, `5x5`, `7x5`, plus `OpenSans-Light` and `WP7xn`), automatic word-wrap at
    the panel's edge, and forced line breaks via `\n` (works both as a real newline from YAML
    and as a literal backslash-n typed into a plain GUI text field).
  - Text too wide to fit can scroll continuously (looping marquee GIF, `text_scroll: true`)
    instead of being clipped, with configurable speed and loop gap.
  - An existing image or GIF file (its first frame, if animated) can be inserted alongside
    the icon/text via `image_path`, with optional resizing.
  - Templates in `text`/`icon` resolve when the service is called from an automation/script
    (Home Assistant's own engine renders them before the call); they do not resolve if typed
    literally into the Developer Tools → Actions test field, and these services are one-shot
    (no auto-update on sensor changes) - see the README for details.
- New service `ipixel_color.send_image_file`: sends an existing image or GIF file (read from
  disk, e.g. under `/config/www/`) as-is - PNG, GIF (including animated, frame-by-frame with
  original durations), JPEG, BMP, TIFF, WEBP, HEIC/HEIF.
- New diagnostic service `ipixel_color.send_test_pattern`: sends a 4-quadrant colored test
  image sized to the panel, to help verify how the device's reported width/height maps onto
  the physical panel.

### Changed

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
