<div align="center">
  <img src="assets/banner.svg" alt="BLE LED Pixel Display banner: a Home Assistant integration for Bluetooth LE LED pixel matrix panels, beside two 64 by 16 pixel panels rendering PV 2400W in green and H100M 57 in red" width="100%">

  # BLE LED Pixel Display — Bluetooth LE Pixel Matrix Panels for Home Assistant

  **Put live Home Assistant data on a cheap Bluetooth LED panel — text, images, animated GIFs, Material Design Icons and composed layouts.**
  A custom integration for LED pixel matrix displays that speak the iPIXEL Color protocol, sold as **BGLight** and as the **B.K. Light LED Pixel Board** at Action. Fully local over Bluetooth LE — no cloud, no vendor app, no account.

  [![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge)](https://hacs.xyz)
  [![Release](https://img.shields.io/github/v/release/sphings79/ha-ble-led-pixel-display?style=for-the-badge&color=7C7CF5)](https://github.com/sphings79/ha-ble-led-pixel-display/releases)
  [![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-41BDF5?style=for-the-badge)](https://www.home-assistant.io)
  [![License](https://img.shields.io/badge/License-GPL--3.0-3ddc97?style=for-the-badge)](LICENSE)

  **English** · [Deutsch](README.de.md)
</div>

## Table of contents

- [What this integration does](#what-this-integration-does)
- [Supported devices](#supported-devices)
- [Actions](#actions)
- [Installation](#installation)
- [Entities you get](#entities-you-get)
- [Display modes](#display-modes)
- [Avoiding flicker: how updates actually work](#avoiding-flicker-how-updates-actually-work)
- [Examples](#examples)
- [Fonts](#fonts)
- [Why this fork exists](#why-this-fork-exists)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [More Home Assistant projects](#more-home-assistant-projects)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)

## What this integration does

These panels are sold as toys — you set a message with a phone app over Bluetooth and that is it. This integration makes them a proper Home Assistant output device: a `text` entity you can write to from any automation, plus actions for images, GIFs, icons and multi-element layouts.

Typical uses:

- **Energy dashboard on the wall** — current PV production, battery state of charge, house consumption, time until the battery is full
- **Status ticker** — who is home, next calendar entry, whether the garage door is open
- **Alerts** — a red panel when a window is open while the heating runs, or when the washing machine finishes
- **Ambient info** — weather icon plus temperature, composed as a single layout

Everything runs locally over Bluetooth LE. Home Assistant's Bluetooth proxies are supported, so the panel does not have to be near the Home Assistant host.

## Supported devices

Any panel that advertises as `LED_BLE_*` with service UUID `0000fa01-0000-1000-8000-00805f9b34fb` and speaks the iPIXEL Color protocol. Known brands:

| Brand | Notes |
| --- | --- |
| **B.K. Light LED Pixel Board** | Sold at Action, the most common one in Europe |
| **BGLight** | Same protocol |
| Generic "iPixel Color" panels | Whatever the vendor app is called iPixel Color |

Panel resolution is read from the device itself; 64×16 is the usual size. If your panel reports the wrong dimensions, see [Troubleshooting](#troubleshooting).

## Actions

<img src="assets/actions.svg" alt="The five actions the integration provides: send_text for device-rendered scrolling text, send_image_file for images and animated GIFs, send_mdi_icon for Material Design Icons, send_layout to combine up to four icons an image and four text areas, and send_test_pattern to verify panel size and colour order" width="100%">

All actions target the panel's `text` entity and are callable from automations, scripts, and Developer Tools → Actions.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Three dots menu, top right → **Custom repositories**
3. Repository URL: `https://github.com/sphings79/ha-ble-led-pixel-display`
4. Category: **Integration** → **Add**
5. Search for **BLE LED Pixel Display**, install it
6. Restart Home Assistant

### Manual

1. Copy `custom_components/ble_led_pixel` into your Home Assistant `custom_components` directory
2. Restart Home Assistant

### Adding the panel

Power the panel on and make sure no phone is connected to it — a panel that is already connected to the vendor app will not advertise, and Home Assistant cannot find it.

Home Assistant usually discovers it by itself and offers it under **Settings → Devices & Services**. Otherwise add it manually: **Add Integration → BLE LED Pixel Display**, then pick your panel from the list. Devices whose name starts with `LED_BLE_` are marked with a star. Manual entry of a MAC address is available as a fallback.

## Entities you get

| Entity | Domain | What it does |
| --- | --- | --- |
| **Display** | `text` | The text shown on the panel. Write to it from any automation. |
| **Text Color** | `light` | Foreground colour as RGB |
| **Background Color** | `light` | Background colour as RGB |
| **Brightness** | `number` | 1–100 |
| **Mode** | `select` | `textimage`, `text` or `clock` — see [Display modes](#display-modes) |
| **Font** | `select` | TTF/OTF fonts, see [Fonts](#fonts) |
| **Font Size**, **Line Spacing** | `number` | Layout in `textimage` mode |
| **Text Animation**, **Text Speed**, **Text Rainbow** | `number` | Scrolling and effects in `text` mode |
| **Clock Style** | `select` | 9 clock faces |
| **Clock 24h**, **Clock Show Date** | `switch` | Clock options |
| **Antialiasing** | `switch` | Smoothing in `textimage` mode |
| **Auto Update** | `switch` | **Read [Avoiding flicker](#avoiding-flicker-how-updates-actually-work) before touching this** |
| **Update Display** | `button` | Renders the stored state to the panel |
| **Sync Time** | `button` | Sets the device clock |
| Device Type, Display Width, Display Height, MCU/WiFi Version | `sensor` | Diagnostics |

## Display modes

| Mode | Rendering | Good for |
| --- | --- | --- |
| **`text`** | The device renders the text itself | Scrolling tickers, lowest Bluetooth traffic, smoothest animation |
| **`textimage`** | Home Assistant renders text to an image with Pillow, then sends the image | Custom TTF fonts, precise sizing, antialiasing, multiline with `\n` |
| **`clock`** | Device-side clock | A clock, with 9 styles |

## Avoiding flicker: how updates actually work

This is the part that is not obvious, and it decides whether your panel looks smooth or flickers on every change.

**With `Auto Update` on, every single change renders immediately.** Setting the text is one Bluetooth write, setting the colour is another. Between the two, the panel briefly shows the old value in the new colour, or the new value in the old colour. On a slow Bluetooth link that gap is over a second and clearly visible.

**With `Auto Update` off, `text.set_value` and `light.turn_on` only store the value.** Nothing reaches the panel until you press the `Update Display` button — which then renders text and colour together, in a single write.

So for anything that updates regularly:

```yaml
# Once, manually: turn the Auto Update switch off.
actions:
  - action: text.set_value
    target: { entity_id: text.display }
    data: { value: "PV 2400W" }
  - action: light.turn_on
    target: { entity_id: light.text_color }
    data: { rgb_color: [0, 255, 0] }
  - action: button.press          # both land on the panel at once
    target: { entity_id: button.update_display }
```

Two further benefits: it is faster, because one Bluetooth round trip replaces two or three, and the timing gets predictable.

The one trade-off: with `Auto Update` off, changing text or colour by hand in the Home Assistant UI does nothing visible until the button is pressed. If an automation presses it regularly anyway, you will not notice.

> **Tip:** Only write the colour when it actually changed. On a panel that cycles through five screens where only one is green, that saves four Bluetooth writes per cycle.

## Examples

### Energy display cycling through several values

A single automation that rotates through PV production, battery state of charge and house consumption every five seconds:

```yaml
alias: LED panel energy cycle
triggers:
  - trigger: time_pattern
    seconds: /5
mode: single
max_exceeded: silent
variables:
  screens: >-
    {% set pv = states('sensor.pv_power') | float(0) %}
    {% set soc = states('sensor.battery_soc') | float(0) %}
    {% set house = states('sensor.house_consumption') | float(0) %}
    {% set ns = namespace(l=[]) %}
    {% if pv > 0 %}
      {% set ns.l = ns.l + [{'text': 'PV %d W' | format(pv), 'color': [0, 255, 0]}] %}
    {% endif %}
    {% set ns.l = ns.l + [{'text': 'SoC %d%%' | format(soc), 'color': [255, 0, 0]}] %}
    {% set ns.l = ns.l + [{'text': 'H %d W' | format(house), 'color': [255, 0, 0]}] %}
    {{ ns.l }}
actions:
  - variables:
      screen: "{{ screens[(states('counter.panel_step') | int(0)) % (screens | length)] }}"
  - action: text.set_value
    target: { entity_id: text.display }
    data: { value: "{{ screen.text }}" }
  - if:
      - "{{ (state_attr('light.text_color', 'rgb_color') or []) | list != screen.color }}"
    then:
      - action: light.turn_on
        target: { entity_id: light.text_color }
        data: { rgb_color: "{{ screen.color }}" }
  - action: button.press
    target: { entity_id: button.update_display }
  - action: counter.increment
    target: { entity_id: counter.panel_step }
```

The screen list is built as data, so screens without meaning drop out of the cycle by themselves — no PV screen at night. A `counter` helper holds the position.

> **Mind the character limit.** Many panels switch to a second view when the text is longer than fits, which looks like the display jumping. Keep strings short and predictable, and pad numbers to a fixed width.

### An image or animated GIF

```yaml
- action: ble_led_pixel.send_image_file
  target: { entity_id: text.display }
  data:
    file_path: /config/www/panel/rain.gif
    resize_method: fit          # or "crop"
```

The path must be readable by Home Assistant and listed under `allowlist_external_dirs` if it is outside `/config`.

### A Material Design Icon

```yaml
- action: ble_led_pixel.send_mdi_icon
  target: { entity_id: text.display }
  data:
    icon: mdi:weather-pouring
    color: [65, 189, 245]
    scale: 1.0
```

Icons are fetched on demand, so any MDI name works without shipping the icon set.

### Weather icon and temperature side by side

```yaml
- action: ble_led_pixel.send_layout
  target: { entity_id: text.display }
  data:
    icon: mdi:weather-sunny
    icon_x: 0
    icon_y: 0
    icon_size: 16
    icon_color: [255, 193, 7]
    text: "{{ states('sensor.outside_temperature') | round(0) }}°C"
    text_x: 20
    text_y: 4
    text_color: [230, 237, 243]
```

`send_layout` composes up to four icons, an image and four independent text areas, each with its own position, colour, alignment and optional scrolling or blinking.

### Scrolling text rendered by the device

```yaml
- action: ble_led_pixel.send_text
  target: { entity_id: text.display }
  data:
    text: "Doorbell — someone is at the front door"
    color: [255, 107, 107]
    animation: 1        # scroll
    speed: 60
```

This is the lightest option: the panel does the scrolling itself, Home Assistant sends the string once.

### Checking a new panel

```yaml
- action: ble_led_pixel.send_test_pattern
  target: { entity_id: text.display }
```

Four coloured quadrants — verifies resolution and colour channel order in one shot.

## Fonts

Fonts are picked in the **Font** select entity and looked up in this order:

1. `custom_components/ble_led_pixel/fonts/` — shipped with the integration
2. The `pypixelcolor` package
3. System font directories

> **Important:** In `text` mode, only location 1 is used for rendering, while the selector lists fonts from all three. Selecting a font that lives outside the integration folder silently falls back to `CUSONG`. This fork ships `VCR_OSD_MONO` for exactly that reason. To use your own font, drop the `.ttf` or `.otf` into the integration's `fonts/` folder and restart.

Bundled: `3x5-de`, `5x5`, `7x5`, `WP7xn`, `OpenSans-Light`, `Lepidos`, `VCR_OSD_MONO`.

## Why this fork exists

This continues [cagcoach/ha-ipixel-color](https://github.com/cagcoach/ha-ipixel-color) by Christian Grund, which has had no commits since December 2025 while pull requests and issues piled up. It merges the image, MDI icon and layout work from [tigers75](https://github.com/tigers75/ha-ipixel-color) and adds fixes of its own — among them the font fallback above, and pinning `pypixelcolor` below 0.5 because the library has since removed the fonts that existing installations depend on.

**The domain is `ble_led_pixel`, not `ipixel_color`.** Both integrations can therefore be installed side by side, so you can migrate one panel at a time instead of switching everything at once.

## Troubleshooting

**The panel is not discovered.** Disconnect the vendor app first — a connected panel stops advertising. Check that Home Assistant's Bluetooth integration is set up and the panel is within range of the host or a Bluetooth proxy.

**Wrong width or height.** The dimensions come from the device. Some firmware reports them incorrectly; check the Display Width and Display Height sensors against reality.

**Text is cut off or the display jumps between two views.** The string is longer than the panel fits. Shorten it, or use `send_text` with scrolling.

**The selected font has no effect.** See [Fonts](#fonts) — in `text` mode only the integration's own folder is searched.

**Colour and text change at different times.** See [Avoiding flicker](#avoiding-flicker-how-updates-actually-work).

**Nothing happens when I change something in the UI.** `Auto Update` is off. Press `Update Display`.

Debug logging:

```yaml
logger:
  logs:
    custom_components.ble_led_pixel: debug
```

## FAQ

**Does this need the vendor app or an account?** No. Everything is local Bluetooth LE.

**Does it work with a Bluetooth proxy?** Yes, the panel does not have to be near the Home Assistant host.

**Can I run this next to the original `ipixel_color` integration?** Yes — different domain, no conflict. Do not connect both to the same panel at the same time.

**Can I read whether the panel is switched on?** No. The protocol has a command to switch power, but none to query it. The switch reflects what Home Assistant last sent, not the device.

**How many panels can I use?** As many as your Bluetooth setup handles. Each becomes its own device.

**Which resolutions work?** Whatever the device reports, typically 64×16.

## More Home Assistant projects

- [Marstek Venus Modbus](https://github.com/sphings79/marstek_venus_modbus_dev) — Marstek Venus battery storage over local Modbus TCP
- [Shelly Modbus](https://github.com/sphings79/shelly-modbus-home-assistant) — Shelly energy meters and relays over Modbus TCP, no cloud
- [StateGuard](https://github.com/sphings79/stateguard-home-assistant) — alerts when entities go unavailable or stop reporting
- [IntegrationGuard](https://github.com/sphings79/integrationguard-home-assistant) — which of your HACS extensions is still maintained
- [MyIP.wtf](https://github.com/sphings79/myip-wtf-home-assistant) — public IPv4/IPv6, ISP and geolocation as sensors
- [Leasing KM](https://github.com/sphings79/leasing-km-home-assistant) — mileage allowance for a leased car
- [Marstek Venus BLE](https://github.com/sphings79/ha-marstek-ble) — Marstek Venus E over Bluetooth LE
- [Marstek offline endpoint](https://github.com/sphings79/Marstek-offline-endpoint) — run a Venus battery without the cloud
- [Power Flow Card Plus Mushroom](https://github.com/sphings79/power-flow-card-plus-mushroom) — power flow card with multiple batteries and PV sources

## Contributing

Issues and pull requests are welcome — especially reports from panels of other brands, and the exact model name and reported resolution.

If this integration got your energy data onto the wall, a ⭐ on the repository genuinely helps other people find it.

<a href="https://buymeacoffee.com/sphings"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black" alt="Buy me a coffee"></a>

## Disclaimer

Unofficial, community-built integration. Not affiliated with, endorsed by, or supported by Home Assistant, Nabu Casa, Action, BGLight, or any panel manufacturer. Brand names are used only to describe compatibility. See [NOTICE](NOTICE).

## License

[GPL-3.0](LICENSE) — inherited from the original work by Christian Grund. Protocol library [pypixelcolor](https://github.com/lucagoc/pypixelcolor) by lucagoc is MIT.

---

<sub>Home Assistant LED matrix · Bluetooth LE pixel display · BGLight Home Assistant · B.K. Light LED Pixel Board Action · iPixel Color integration · LED_BLE · 64x16 pixel panel · HACS custom integration · display sensor value on LED panel · animated GIF on LED matrix · Material Design Icon on display · scrolling text ticker · energy dashboard wall display · PV production display · battery state of charge panel · no cloud · local Bluetooth · pypixelcolor</sub>
