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

## [1.2.0] - 2026-09-05

### Added

- **Full device type table**, recovered from the vendor app. pypixelcolor
  resolves device types 128-147 to 20 LED types; the app carries types up to
  159 and 36 LED types, so twelve models -- every 64-pixel-tall one -- had no
  dimensions at all. Also brings the per-type frame buffer size, which matters:
  32x32 panels take 12288 bytes, not the 4096 default or the 1024 go-ipxl
  assumes.
- **Product ID and Brand sensors.** cid and pid are read from the panel's
  advertisement. They identify the model, and for device types 129, 130 and 137
  the pid decides which hardware generation it is -- same resolution, different
  buffers. Known brands are named: HYPERLITE and EZYEVY.

### Fixed

- Panels whose firmware reports the wrong dimensions now get them from the
  device type instead. An unknown device type is logged with a request to
  report it, and the panel's own numbers are kept rather than guessed at.

## [1.3.0] - 2026-09-05

### Added

- **`show_slot` and `delete_slot` actions.** Panels store pictures internally,
  and displaying a stored one costs seven bytes instead of a full frame buffer
  -- 12288 bytes on a 32x32 panel. Writing was already possible through the
  `save_slot` argument of `send_image_file` and `send_mdi_icon`; the commands to
  recall and erase existed in pypixelcolor but no integration exposed them.
  Showing an empty slot makes the panel cycle through the slots that do hold
  something.

## [1.3.1] - 2026-09-05

### Fixed

- **Product ID and Brand stayed empty.** Two wrong assumptions: Home Assistant
  reports the company id byte-swapped compared to the vendor app (`0x5254`
  against `0x5452`, because it reads the field little-endian per the BLE spec),
  and the `TR` signature lives in the company id rather than in the payload,
  which starts one byte further in. Verified against a real panel:
  `{0x5254: 00720007020081}` resolves to cid 0007, pid 02, device type 129.
- The advertisement also carries the **device type**, so it is now available
  before a connection is made rather than only after the device-info query.

## [1.3.2] - 2026-09-05

### Added

- **B.K. Light recognised as a brand.** cidpid `000702` is the "LED pixel
  board" sold by Action, 13x13 cm and 32x32 pixels. The vendor's own brand
  grouping does not list the `0007` group at all, so this came from hardware.

## [2.8.0] - 2026-11-05

### Fixed

- **Show Slot works on the 64x20 panel.** Probed on the hardware: any unsaved
  send halts the panel's stored play list, and while it is halted the show
  frame is acknowledged and ignored. Show Slot (the button and `show_slot`)
  now first turns DIY mode off (`05 00 04 01 00`), which restarts the play
  list, and then sends pypixelcolor's seven-byte frame `07 00 08 80 01 00 nn`,
  which 2.6.1 had wrongly replaced. The panel briefly shows the stored slot
  it played last on the way. Details in docs/protocol.md, A.8.

## [2.7.1] - 2026-11-05

### Added

- **`ble_led_pixel.send_raw_command`, a diagnostic action.** Sends up to ten
  frames exactly as given (hex), then returns what was sent and every reply
  the panel made, in order. It is for working out commands on real
  hardware, starting with Show Slot.

### Changed

- **Message greys out in clock mode**, like the other settings clock mode
  does not use. Its text is kept, across restarts too. An automation that
  writes to Message while the panel is in clock mode is skipped by Home
  Assistant.
- The actions (`send_text`, `show_slot` and the rest) keep working in clock
  mode. They target the Message entity, and Home Assistant's own action
  dispatch skips unavailable entities, so the integration now dispatches
  them itself.

### Known issue

- **Show Slot still does nothing on some panels.** 2.6.1 said the 64x20
  panel (product 000105) needed the five-byte frame; that was not
  confirmed, and it ignores both forms so far. `send_raw_command` is there
  to find the frame it does accept.

## [2.7.0] - 2026-11-05

### Changed

- **Settings the current mode does not use are greyed out.** On the device
  page and in dashboards they show as unavailable, and come back when you
  switch to a mode that uses them. Clock settings grey out in the text
  modes, text-only settings in textimage and clock, and so on. Mode,
  Message, Brightness, Auto Update, Update Display and the Slot number,
  Show and Clear stay available in every mode.
- Their values are kept, also across a restart while greyed out: each one
  is saved alongside Home Assistant's own restore data, which stores
  "unavailable" for an unavailable entity.
- An automation cannot change a greyed-out setting, since Home Assistant
  skips unavailable entities in actions. Switch the mode first.

## [2.6.2] - 2026-11-05

### Changed

- **Every setting's name says which mode it applies to.** The device page
  has no separators, so the names carry it: `Text & Image:` (both text
  modes), `Text Only:`, `Text Image Only:`, `Clock:` and `Slot:`. For
  example Text Effect is now Text Only: Effect, Image Font Size is Text
  Image Only: Font Size, and Message Font is Text & Image: Font. Entity ids
  do not change.
- Auto Update keeps its plain name: it applies in every mode, clock
  included. The README card now shows it next to Update Display.

- The README dashboard card's sections are titled Text & Text Image Mode,
  Text Mode Only and Text Image Mode Only.

### Fixed

- **Changing Text Only: Speed did not refresh the panel** when the panel's
  entity ids differ from its name (for example after assigning it to an
  area). The mode and Auto Update entities are now looked up by unique id.

## [2.6.1] - 2026-11-05

### Fixed

- **Show Slot did nothing.** The panel ignored the seven-byte frame
  pypixelcolor sends (`07 00 08 80 01 00 nn`). It now sends the vendor
  app's five-byte frame, `05 00 08 80 nn`. (Later testing showed the 64x20
  panel ignores this one too; see 2.7.1.)

### Changed

- **Slot controls sort together.** The buttons are now named Slot Save,
  Slot Show and Slot Clear, so the device page lists them as one block,
  with the Slot number first. Existing entity ids do not change. The
  dashboard card example in the README gains a Slots section.
- **Settings shared by text and textimage mode use a `Message` prefix.**
  Text Font, Text Color and Text Background Color are now Message Font,
  Message Color and Message Background Color, so the `Text` prefix means
  text mode only and `Image` means textimage only. Entity ids do not
  change.
- **The README dashboard card follows the settings' scope**: settings for
  both text modes first, then text mode only, textimage only, clock, and
  slots.

## [2.6.0] - 2026-11-04

### Added

- **Slot controls on the device page.** Pick a slot with the new **Slot**
  number (1-10), then press **Save to Slot**, **Show Slot** or **Clear Slot**
  under Configuration. Save to Slot sends the current message with the
  current mode's settings and keeps a copy in that slot. It works in `text`
  and `textimage` mode; clock mode is drawn by the panel and cannot be
  saved. A failed press shows an error instead of failing silently.
- `textimage` mode can save to a slot too (it previously ignored slots).

## [2.5.0] - 2026-11-04

### Added

- **Delete all stored content** (`ble_led_pixel.delete_all_slots`). Erases
  every saved picture and text on the panel, including what it shows at
  power-up. The panel cannot report which slots are in use, so this is the
  way to a clean state.
- **`send_text` can save the text to a slot** (`save_slot`, 1-10), like
  `send_image_file`, `send_mdi_icon` and `send_layout` already could. A text
  being saved is not dropped by newer content, only by an erase requested
  after it.

## [2.4.1] - 2026-11-04

### Fixed

- **The unbranded 64x20 panel (product id 000105) is now listed as
  Generic.** It is a no-name eBay model, so the "not in the brand table"
  repair notice had nothing to ask. Its manufacturer now shows Generic, and
  the notice clears on the next start.

## [2.4.0] - 2026-11-04

### Added

- **Text Size select for text mode.** Text mode is drawn by the panel in whole
  16px rows, so the select offers 16, 32, 48 and 64 and only the sizes that fit
  the panel (honouring a height override). It used to take its size from the
  Font Size number, which accepts 0.5px steps that text mode silently rounded
  away. On the first start, Text Size is set from that number so nothing
  changes visually.
- **Scroll up and Scroll down text effects** (codes 3 and 4). Offered on
  32x32 panels; on others, turn on *Offer scroll up and scroll down text
  effects* in the options. They work on the 64x20 panel (Type 133), though
  pypixelcolor warns they can boot-loop some devices outside 32x32. The
  `send_text` action lists them too and refuses them while they are off.
- **Your own fonts in `/config/fonts/`.** Searched before the bundled ones,
  and kept across HACS updates, which replace the integration's own `fonts/`
  folder. Reloading the integration picks up newly added fonts.

### Changed

- **The setup picker lists panels only.** It used to list every connectable
  Bluetooth device nearby, with panels starred among them. It now shows only
  devices recognised as panels (an `LED_BLE` name, the vendor's manufacturer
  data, or the panel's service UUID) that are not set up yet, plus **Show all
  Bluetooth devices** for a panel that advertises unusually, and manual entry.
- **Font Size is now called Image Font Size**, since it only affects the
  `textimage` mode. Its entity id is unchanged.
- **Entities are grouped into Controls and Configuration.** The everyday
  controls (Power, Mode, Message, Brightness, Update Display) stay on the
  device page; the settings move under Configuration. Names now come from the
  device, so they read "<panel> Text Font" rather than a bare "Font", and the
  power switch takes the device name. Renamed to say which mode they affect:
  Antialiasing → Image Antialiasing, Font → Text Font, Line Spacing → Image
  Line Spacing, Display → Message, Sync Time → Clock Sync Time, Background
  Color → Text Background Color. Entity ids are unchanged, so automations and
  dashboards keep working.
- **The README has a dashboard card that shows only the settings for the
  current mode.**

### Fixed

- **A failed connection during setup now says so.** The picker used to come
  back with no error message after the panel could not be reached.
- **The bundled fonts' tuning was ignored in text mode.** Each font in
  `fonts/` ships a JSON file with its size, offset, pixel threshold and
  variable width per character height. pypixelcolor 0.4 read those itself;
  0.5 stopped, so every font was drawn with defaults. The integration now
  reads the JSON and passes the closest entry to pypixelcolor. A font without
  one is drawn at the text height with threshold 70, as under 0.4.
- Building text commands (font loading and glyph rendering) now runs off the
  event loop.
- **A slow update can no longer overwrite a newer one.** Text and images are
  rendered off the event loop, so a long text could finish after a later
  image, clock or other text and replace it. A render that has been overtaken
  by any newer display request is now dropped. Saving a picture to a slot is
  never dropped.

## [2.3.8] - 2026-11-04

First release from the scyto/ha-ble-led-pixel-display fork, based on 2.3.7.

### Fixed

- **Two sends at once could corrupt each other.** Writes to the panel now
  take turns, so a chunked image or text can no longer interleave with
  another command and lose its acknowledgements.
- **The power switch showed off for a panel that was plainly on.** The panel
  cannot report its power state and powers up on, but the switch always
  started off. It now starts on, and after a restart restores the last state
  set through Home Assistant.
- **After a restart the panel kept showing its own stored content** (for
  example a message set from the phone app) while Home Assistant showed its
  restored text. Once Home Assistant has started, the restored settings are
  sent to the panel, if Auto Update is on and the power switch is not off. A
  panel that is not connected yet gets them as soon as its link comes up.
  Anything sent meanwhile, such as a start-up automation, wins over the
  restore.

### Changed

- `pillow` is no longer listed as a requirement; Home Assistant ships it.
- Issues and documentation now point at this fork.
- CI: HACS and hassfest validation, unit tests, and a release workflow that
  publishes when the manifest version changes.

## [2.3.7] - 2026-11-01

### Fixed

- **Longer scrolling texts (about 25 characters and up) were not shown; the
  previous text kept scrolling.** `send_text` wrote each window of the text as
  a single BLE packet, which only fits short texts. It now goes through the
  same chunked, acknowledged transport as images and layouts. Reported and
  diagnosed in issue #1 by ServerSystem70.

## [2.3.6] - 2026-10-06

### Fixed

- **2.3.5 shipped an empty `manifest.json`**, so Home Assistant could not load
  the integration at all. The manifest is restored. Nothing else changed from
  2.3.5, which carries the fix for 2.3.4. **Skip 2.3.4 and 2.3.5.**

## [2.3.5] - 2026-10-06

### Fixed

- **2.3.4 could not set up any panel.** The start-up fix looked the panel up
  through Home Assistant's `bluetooth` component, but this package has a
  `bluetooth` subpackage of its own, and importing that replaced the name in
  `__init__.py`. Setup then failed with `AttributeError ... has no attribute
  'async_ble_device_from_address'` and every entry ended in "Setup error".
  The component is now imported under a different name. **Skip 2.3.4.**

## [2.3.4] - 2026-10-06

### Fixed

- **A panel that was out of range no longer holds up Home Assistant's
  start-up.** Setup tried to connect before anything else, and for a panel
  missing from the Bluetooth cache that meant waiting out the rediscovery
  (three lookups, two seconds apart) and then the connection attempts --
  around sixteen seconds per panel, with Home Assistant waiting for each.
  A panel the Bluetooth manager has not seen is now left to the reconnect
  watcher, which already tries at once and again whenever the panel
  advertises. A panel that is known is still connected during setup, so its
  geometry is available when the entities are created, but that attempt is
  capped at fifteen seconds.

## [2.3.3] - 2026-09-10

### Added

- **Inline colour tags are documented and safe to use.** pypixelcolor 0.5.0
  understands `[#ff0000]ALARM[/] Kitchen` in `send_text`, painting single
  characters. The tags win where they apply and the colour parameter fills in
  everywhere else. Nothing had to be built for this to work in `text` mode and
  in the `send_text` action -- the text was already handed over untouched --
  but nothing said so either. The README now shows it in both languages, and
  the action describes it in the field where it is typed.

### Fixed

- **`textimage` mode no longer shows colour tags as markup.** That mode
  renders a whole line into one greyscale mask and tints it afterwards, so it
  has no per-character colour to give; a tag reached the panel written out in
  full. Tags are now stripped there using pypixelcolor's own helpers, so the
  two agree on what a tag is. The text still shows, in one colour.
  Malformed tags are left alone on purpose -- they are literal text somebody
  mistyped, and eating them silently would hide the mistake.

### Notes

- Only six-digit hex is recognised. `[#f00]` is not a tag to the library and
  reaches the panel as written.
- With a text gradient active the panel colours the text itself. How that
  interacts with per-character colours has not been tested on hardware.

## [2.3.2] - 2026-09-10

### Changed

- **pypixelcolor is now pinned to `>=0.5.0,<0.6`.** 0.5.0 landed on 2026-09-08
  and its release notes call `send_text` a breaking change, but the arguments
  it consolidated -- `font_size`, `font_offset`, `pixel_threshold`,
  `var_width` -- are ones this integration never passed. Every call site was
  exercised against 0.5.0 before the pin moved: `send_text` with all nine
  arguments, `send_image_hex` for PNG and GIF in both resize modes and with a
  save slot, `show_slot`, `delete`, `set_clock_mode`, `set_time`,
  `DeviceInfo`, `parse_device_info` and `build_get_device_info_command`.
  `resize_method` still accepts plain strings, so `"fit"` and `"crop"` are
  unchanged.

- Two fixes in 0.5.0 land directly on this integration: transparent areas of a
  PNG or GIF now flatten to black instead of producing artefacts, and the
  framing of large text payloads was corrected.

### Fixed

- **`make_text_command` no longer defaults its font to `VCR_OSD_MONO`**, a
  name pypixelcolor dropped in 0.5.0. The argument is required now. The only
  caller in this integration always passed a resolved absolute path, so
  nothing changes in practice, but a default naming a font that no longer
  exists is a trap for the next caller.

- **The font warning carried since 0.4.0 is settled.** 0.5.0 does drop
  `CUSONG`, `SIMSUN` and `VCR_OSD_MONO`, leaving only `unifont.otf`. Nothing
  breaks, because every font offered in the interface ships inside this
  integration and is handed to the library as an absolute path. `unifont.otf`
  simply joins the list.

## [2.3.1] - 2026-09-06

### Fixed

- **Product ID and Brand no longer sit at "unavailable" on a panel that has
  none.** Not every model broadcasts a product id: a 64x16 B.K. Light
  advertises its name and nothing else, while the 32x32 of the same brand
  reports `000702`. Once the panel has answered at all, the sensors now read
  `not advertised`, which is the difference between a fault that may pass and
  a value that does not exist.

- **The reconnect watcher slept through the very advertisements it waits
  for.** It promised to reconnect as soon as a panel was seen, but the backoff
  used a plain sleep, and the advertisement callback bails out while a
  reconnect loop is running -- so every sighting during a wait of up to 30
  seconds was dropped. The loop now waits on the advertisement instead of
  ignoring it, and tries at once when the panel shows up. The backoff still
  grows on a failed attempt, so a panel that advertises but refuses
  connections cannot spin this into a busy loop.

### Added

- **A panel brought back by an ordinary write now says so.** That path
  recovers the link silently, which made the watcher look worse than it is:
  the log showed a string of failures and never the recovery that followed.
- Advertisements that carry no identity are logged at debug, and separately
  from ones that carry manufacturer data this parser cannot read -- only the
  second kind is something the parser could be taught.

## [2.2.1] - 2026-09-05

### Fixed

- **Text mode `textimage` never reached the panel.** `make_image_command`
  returns a `SendPlan`, which has to go through `send_plan()` so each window
  is chunked and acknowledged. `display_text` still iterated it as if it were
  a list of frames, so every update raised `'SendPlan' object is not
  iterable` and nothing was displayed. Every other caller already did it
  correctly; this one had been missed.
- The same mistake in `display_emoji`, which the `show_emoji` action uses.

## [2.2.0] - 2026-09-05

### Added

- **`set_password` action**, to set or remove a panel's password without the
  vendor app. Left out until now because locking yourself out is easy, but the
  app is unmaintained: if it disappears, so does the only way to set one at
  all. The frame is `08 00 04 02 <flag> p1 p2 p3`, flag 1 to set and 0 to
  remove, with the current password carried on removal -- the app checks it
  against its own copy first, and the panel is expected to as well.
- The action stores the password in the integration options in the same step,
  which is what keeps the integration able to reach the panel afterwards, and
  corrects the cached password flag so the diagnostic sensor is right
  immediately rather than after the next reconnect.

## [2.1.2] - 2026-09-05

### Fixed

- **The font size could be set higher than the panel is tall.** The maximum
  was a fixed 64 regardless of hardware, so a 16px panel offered sizes it
  cannot render. It is now the panel's own height.

## [2.1.1] - 2026-09-05

### Fixed

- **Font size and line spacing silently meant different things per mode, and
  said nothing about it.** In text mode the panel lays the text out itself:
  line spacing has no field in the protocol and is ignored outright, and the
  font size is capped at the panel height, raised to at least 16 and rounded
  down to a multiple of 16 -- so a 32px panel really only offers 16 and 32,
  and a `0` meaning auto-fit becomes 16. Both settings stay visible, but the
  log now says when a value cannot be used as given, once per change rather
  than on every refresh. The behaviour is documented in both READMEs.
- **Removed 14 dead `_attr_entity_description` assignments.** Home Assistant
  expects `entity_description` to be an `EntityDescription` object and never
  reads an `_attr_` variant, so those strings were shown nowhere and only
  looked like documentation.

## [2.1.0] - 2026-09-05

### Breaking

- **`number.<panel>_text_rainbow` is gone, replaced by
  `select.<panel>_text_gradient`.** It was a slider from 0 to 9 with no
  indication of what any value did -- and two of those ten values did nothing
  at all. The eight real gradients are now described rather than numbered, and
  Off is an option instead of a magic zero. An existing numeric selection is
  migrated on first start; automations writing the old entity need updating.

### Added

- **Panels are discovered the way the vendor app discovers them.** The app
  looks for `LED_BLE` anywhere in the name, and accepts a panel with no such
  name at all when its advertisement carries the vendor manufacturer data.
  Discovery here required the name to *start* with `LED_BLE_`, so a panel
  named `LED_BLE1234`, or one rebranded entirely, was invisible to Home
  Assistant while the app found it. Both paths are now matched.

## [2.0.2] - 2026-09-05

### Fixed

- **The retired `text_animation` number was left behind in the entity
  registry**, showing up as permanently unavailable after the 2.0.0 upgrade.
  Dropping an entity from the code does not drop it from the registry, so
  setup now removes entries for entities this version no longer provides.

## [2.0.1] - 2026-09-05

### Fixed


- **Text mode crashed when the font size entity was unavailable.** Two
  mistakes in three lines: the fallback was written to `speed` instead of
  `font_size`, silently resetting the scroll speed to 16, and the following
  `int(font_size)` then raised a `TypeError` on `None`. It triggered exactly
  when a panel was offline, which is when its entities report unavailable --
  so the code meant to handle a missing value was the code that broke.

## [2.0.0] - 2026-09-05

### Breaking

- **`number.<panel>_text_animation` is gone, replaced by
  `select.<panel>_text_effect`.** The effect was only ever settable as a bare
  number with no indication of what any of the codes did. It is now a named
  choice: Fixed, Scroll left, Scroll right, Blinking, Breathing, Snowflake,
  Laser. The new entity migrates an existing numeric selection on first start,
  but **automations and scripts that set the old number entity need updating**
  to select the effect by name.

### Added

- The effect list now includes **Laser** (code 8), which was unreachable while
  the entity capped at 7.

## [1.6.0] - 2026-09-05

### Added

- **Real firmware versions.** The device-info response carries none, so MCU
  Version and WiFi Version had always read "unknown". They now come from a
  second read, opcode `0x8005`, recovered from the vendor app. Traffic-derived
  implementations missed it because nothing visible happens when it is sent --
  it looks like a no-op unless you read the reply.
- **An "MCU build" sensor** giving the same version as the plain integer the
  vendor's own firmware lookup is keyed on: `4.06` becomes `406`.

### Fixed

- **The clock style selector offered nine faces to every panel.** How many
  there are depends on the resolution: eight on most, nine on a 32x32, ten on
  a 32x16, six on a 144x16. Picking one a panel does not have was another
  command it accepts and then ignores. The list now matches the hardware.

## [1.5.0] - 2026-09-05

### Added

- **Password-protected panels can be used again.** A panel locked from the
  vendor app connects normally and then discards everything sent to it without
  an error, which is close to impossible to diagnose. Put the password in the
  integration options and it is sent after every connect -- the panel forgets
  it whenever the link drops. Six digits for most models, four for the two
  that use four, picked from the product id.
- **A "Password protection" diagnostic sensor**, reading `none`,
  `locked, password set` or `locked, no password set`.

Setting or clearing a password is deliberately not offered: locking yourself
out is easy and undoing it needs physical access to the power supply.

### Fixed

- **`docs/password_reset.md` claimed that a `password_flag` of 255 means no
  password is set.** It does not. 255 is the value pypixelcolor substitutes
  when the device-info response was too short to contain the flag, so it means
  "not reported"; the flag itself is `1` for protected. A panel reporting `0`
  would have been read as locked and sent through a pointless reset.
- The same page now says which parts of the reset procedure are actually
  confirmed. The reset happens in firmware, so the vendor app cannot
  corroborate it -- its only text on the subject is "If you forget your
  password, reset your device", with no procedure and no number of cycles.

## [1.4.0] - 2026-09-05

### Added

- **Four actions for features built into the panel firmware**: `show_preset`
  shows one of twenty stored animations for six bytes on the wire,
  `set_scoreboard` puts two scores up, `set_countdown` and `set_stopwatch`
  drive timers the panel runs by itself.
- **A feature table, so those actions are only offered where they work.** Not
  every panel has them, and two panels of the same resolution can differ. The
  table is transcribed from the vendor app's own screen dispatcher, keyed by
  LED type and product id. A **Supported features** diagnostic sensor shows
  what a given panel accepts, and calling an unsupported action fails with an
  explanation instead of doing nothing -- these panels acknowledge unknown
  commands without complaint, so a silent no-op looks exactly like success.
- **An options switch to offer the four anyway**, for hardware newer than the
  table.
- German translations for the options dialog, which previously fell back to
  English.

## [1.3.4] - 2026-09-05

### Fixed

- **The identity cache added in 1.3.3 had nothing to fill it.** cid and pid are
  read from the advertisement, but a panel stops advertising the moment it is
  connected -- and the only place that read them ran right after connecting. So
  Product ID and Brand stayed unknown no matter how often the panel was seen.
  The advertisement is now watched directly, which catches the identity in the
  window it is actually broadcast: while the panel is disconnected.
- **Bluetooth discovery threw away the identity it already had.** The config
  flow stored only address and name, although the discovery advertisement is
  the most reliable source there is -- the panel is disconnected by definition
  at that point. It is now kept with the entry.
- **Product ID and Brand no longer require a connection.** They come from the
  advertisement, not from the device-info query, so they stayed unavailable
  whenever the panel was offline even though the values were known.
- **An entry data change no longer reloads the integration.** The options
  listener fires on any change to the config entry, so writing the identity
  would have restarted the whole entry. It now reloads only when the options
  actually changed.

## [1.3.3] - 2026-09-05

### Added

- **Animated proof in the README** that the panels really do render images: a
  64x16 panel cycling through live values beside a 32x32 panel showing a heart,
  a sun, a battery and a lightning bolt.
- **Named text effects.** `send_text` offered a bare number 0-7; the effects are
  now selectable by name -- Fixed, Scroll left, Scroll right, Blinking,
  Breathing, Snowflake, Laser. The range also runs to **8**, not 7: every
  traffic-derived table stopped one short, so the Laser effect was unreachable.
- **Action article numbers** in the supported-devices table: ACT1026 for the
  32x32 panel, ACT1025 for the 64x16 one.
- `docs/protocol.md` Appendix B: a cross-check against Bk-Light-AppBypass,
  covering the connect handshake, the undocumented opcode `0x8005`, the effect
  code names, and a fourth independent confirmation that no read command for
  device state exists.

### Fixed

- **Product ID and Brand went unknown after a reconnect.** A connected panel
  stops advertising, so there was often no advertisement left to parse. The
  identity is a property of the hardware and does not change, so it is now
  stored on the config entry the first time it is seen and reused when the
  panel is quiet.

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
