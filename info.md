# BLE LED Pixel Display

Put live Home Assistant data on a cheap Bluetooth LED panel — text, images,
animated GIFs, Material Design Icons and composed layouts.

For LED pixel matrix displays speaking the iPIXEL Color protocol, sold as
**BGLight** and as the **B.K. Light LED Pixel Board** at Action. Fully local
over Bluetooth LE — no cloud, no vendor app, no account.

## What you get

- A `text` entity you can write to from any automation
- `send_image_file` — any image or animated GIF from disk
- `send_mdi_icon` — any Material Design Icon, fetched on demand
- `send_layout` — up to 4 icons, an image and 4 text areas combined
- `send_text` — scrolling text rendered by the device itself
- RGB text and background colour, brightness, fonts, clock modes
- Bluetooth proxy support

## After installing

Restart Home Assistant, then add the panel under **Settings → Devices &
Services**. Make sure no phone is connected to it — a connected panel stops
advertising and cannot be discovered.

**Read the "Avoiding flicker" section in the README** before building
automations that update regularly. It explains why the `Auto Update` switch
should be off and the `Update Display` button used instead.

[Full documentation](https://github.com/sphings79/ha-ble-led-pixel-display) ·
[Deutsch](https://github.com/sphings79/ha-ble-led-pixel-display/blob/main/README.de.md)
