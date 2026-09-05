# Resetting a password-locked panel

These panels can be locked with a password from the vendor app. A locked panel
still advertises and still appears in Home Assistant's device list, but every
connection attempt fails — and nothing in the error says why.

The reset needs no app and no tools. It is done entirely through the power
switch.

If you still know the password, you do not need any of this: put it into the
integration options and it is sent automatically after every connect. See
[the README](../README.md#password-protected-panels).

## Is a password even set?

Look at the **Password protection** diagnostic sensor on the device. It reads
`none`, `locked, password set`, or `locked, no password set`.

Under the hood that is byte 10 of the device-info response, which the vendor
app treats as `1` for protected. The same value appears as `password_flag` in
the debug log:

```yaml
logger:
  logs:
    custom_components.ble_led_pixel: debug
```

Look for the `Parsed device info` line. A `password_flag` of `0` means no
password — check the [troubleshooting section](../README.md#troubleshooting)
instead.

> **Note:** a `password_flag` of `255` does not mean "no password". It is the
> value pypixelcolor substitutes when the response was too short to contain
> the flag at all, so it means "not reported". Earlier versions of this page
> said otherwise.

## The reset

1. Power the panel on.
2. **The moment the white light appears**, switch the power off again.
3. Repeat: on → off, on → off, until you have done **five** on/off cycles in a
   row.

The timing is the part that goes wrong. Switch off immediately when the white
light shows — waiting too long, or cutting it too short, will not trigger the
reset. Fewer than five cycles will not either.

After a successful reset the panel accepts connections again without a
password. Any content stored in its memory slots is unaffected.

## Practical notes

A switchable power strip or a smart plug makes this far easier than pulling the
USB plug five times. If you drive the panel from a Home Assistant controlled
socket, you can script the sequence — but watch the timing, the white light
appears about a second after power is applied and the window is short.

If the panel is powered from something that ramps up slowly, the white light
may be hard to catch. Switching the supply itself, rather than the socket
feeding a power bank, gives the cleanest edges.

## Source

The procedure is documented in the manual shipped with these panels, which is
the same across brands — unsurprising, since they are white-label goods from
one manufacturer. See the [supported devices section](../README.md#supported-devices)
for what that means in practice.

It is worth being clear about what is *not* confirmed. The reset happens in
the panel's firmware, so the vendor app plays no part in it and cannot
corroborate the details. The app's own text for a forgotten password reads
only "If you forget your password, reset your device" — it names no procedure
and no number of power cycles. The five cycles and the timing come from the
printed manual alone, and the count may well differ between models.
