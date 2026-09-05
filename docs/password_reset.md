# Resetting a password-locked panel

These panels can be locked with a password from the vendor app. A locked panel
still advertises and still appears in Home Assistant's device list, but every
connection attempt fails — and nothing in the error says why.

The reset needs no app and no tools. It is done entirely through the power
switch.

## Is a password even set?

The device info the panel returns carries a `password_flag`. The integration
reads it, and `255` means no password is set. You will see it in the debug log
when the device info is queried:

```yaml
logger:
  logs:
    custom_components.ble_led_pixel: debug
```

Look for the `Parsed device info` line. If `password_flag` is `255`, a password
is not your problem — check the [troubleshooting section](../README.md#troubleshooting)
instead.

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
