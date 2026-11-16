// Effect maths of the dashboard card, run without a browser: node --test tests/js
import test from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";

globalThis.HTMLElement = class {};
globalThis.customElements = { define() {} };
globalThis.window = globalThis;
globalThis.document = { createElement() { return {}; } };

const file = path.resolve("custom_components/ble_led_pixel/www/ble-led-pixel-card.js");
await import(pathToFileURL(file).href);
const {
  composeFrame, isAnimated, scrollSpeed, blinkOn, breatheFactor, frameWidth, EFFECT,
} = globalThis.__bleLedPixelCard;

// A picture of one solid colour, `width` x `height`.
function solid(width, height, [r, g, b]) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = r; data[i + 1] = g; data[i + 2] = b; data[i + 3] = 255;
  }
  return { width, height, data };
}

const px = (frame, cols, x, y) => Array.from(frame.pixels.slice((y * cols + x) * 4, (y * cols + x) * 4 + 3));
const lit = (frame, cols, rows) => {
  const xs = [];
  for (let x = 0; x < cols; x++) {
    for (let y = 0; y < rows; y++) {
      if (px(frame, cols, x, y)[0] > 0) { xs.push(x); break; }
    }
  }
  return xs;
};

const RED = [255, 0, 0];
const strip = solid(10, 4, RED);
const base = solid(20, 8, [0, 0, 255]);
const common = { cols: 20, rows: 8, base, strip, speed: 50, bg: "000000" };

test("a fixed picture is shown as it is", () => {
  const f = composeFrame({ ...common, effect: EFFECT.FIXED, t: 0 });
  assert.deepEqual(px(f, 20, 5, 3), [0, 0, 255]);
  assert.equal(f.factor, 1);
});

test("a picture smaller than the panel sits top-left on the background", () => {
  const small = solid(4, 2, [0, 255, 0]);
  const f = composeFrame({ ...common, base: small, bg: "102030", effect: EFFECT.FIXED, t: 0 });
  assert.deepEqual(px(f, 20, 0, 0), [0, 255, 0]);
  assert.deepEqual(px(f, 20, 10, 5), [0x10, 0x20, 0x30]);
});

test("scroll left starts off the right edge and moves left", () => {
  const start = composeFrame({ ...common, effect: EFFECT.LEFT, t: 0 });
  assert.deepEqual(lit(start, 20, 8), []);
  const later = composeFrame({ ...common, effect: EFFECT.LEFT, t: 0.1 });
  const xs = lit(later, 20, 8);
  assert.ok(xs.length > 0 && xs[xs.length - 1] === 19);
  const even = composeFrame({ ...common, effect: EFFECT.LEFT, t: 0.2 });
  assert.ok(lit(even, 20, 8)[0] < xs[0]);
});

test("scroll right moves the other way", () => {
  const a = lit(composeFrame({ ...common, effect: EFFECT.RIGHT, t: 0.4 }), 20, 8);
  const b = lit(composeFrame({ ...common, effect: EFFECT.RIGHT, t: 0.5 }), 20, 8);
  assert.ok(b[b.length - 1] > a[a.length - 1]);
});

test("the scroll repeats once the line has left", () => {
  const span = (20 + 10) / scrollSpeed(50); // seconds for one pass
  const a = composeFrame({ ...common, effect: EFFECT.LEFT, t: 0.4 });
  const b = composeFrame({ ...common, effect: EFFECT.LEFT, t: 0.4 + span });
  assert.deepEqual(lit(a, 20, 8), lit(b, 20, 8));
});

test("the line is centred vertically on the panel", () => {
  const f = composeFrame({ ...common, effect: EFFECT.LEFT, t: 0.4 }); // strip at x = 6..15
  const rows = [];
  for (let y = 0; y < 8; y++) if (px(f, 20, 10, y)[0] > 0) rows.push(y);
  assert.deepEqual(rows, [2, 3, 4, 5]);
});

test("vertical scrolls move the line up or down", () => {
  const firstRow = (f) => { for (let y = 0; y < 8; y++) if (px(f, 20, 2, y)[0] > 0) return y; return -1; };
  const up1 = firstRow(composeFrame({ ...common, effect: EFFECT.UP, t: 0.1 }));
  const up2 = firstRow(composeFrame({ ...common, effect: EFFECT.UP, t: 0.2 }));
  assert.ok(up2 < up1, `up: ${up1} -> ${up2}`);
  const down1 = firstRow(composeFrame({ ...common, effect: EFFECT.DOWN, t: 0.1 }));
  const down2 = firstRow(composeFrame({ ...common, effect: EFFECT.DOWN, t: 0.2 }));
  assert.ok(down2 > down1, `down: ${down1} -> ${down2}`);
});

test("without the whole line a scroll effect shows the first view", () => {
  const f = composeFrame({ ...common, strip: null, effect: EFFECT.LEFT, t: 0.4 });
  assert.deepEqual(px(f, 20, 5, 3), [0, 0, 255]);
  assert.equal(isAnimated(EFFECT.LEFT, false), false);
  assert.equal(isAnimated(EFFECT.LEFT, true), true);
});

test("blinking alternates the picture and the background", () => {
  assert.equal(blinkOn(0), true);
  assert.equal(blinkOn(0.6), false);
  const on = composeFrame({ ...common, effect: EFFECT.BLINK, t: 0.1 });
  const off = composeFrame({ ...common, effect: EFFECT.BLINK, t: 0.6 });
  assert.deepEqual(px(on, 20, 5, 3), [0, 0, 255]);
  assert.deepEqual(px(off, 20, 5, 3), [0, 0, 0]);
});

test("breathing dims the picture between 15 % and full", () => {
  assert.ok(Math.abs(breatheFactor(0) - 1) < 1e-9);
  assert.ok(Math.abs(breatheFactor(1.5) - 0.15) < 1e-9);
  for (let t = 0; t < 6; t += 0.1) {
    const v = breatheFactor(t);
    assert.ok(v >= 0.15 - 1e-9 && v <= 1 + 1e-9);
  }
  assert.ok(composeFrame({ ...common, effect: EFFECT.BREATHE, t: 1.5 }).factor < 0.2);
});

test("snowflake and unknown effects stay still", () => {
  assert.equal(isAnimated(7, true), false);
  assert.equal(isAnimated(8, true), false);
  const a = composeFrame({ ...common, effect: 7, t: 0 });
  const b = composeFrame({ ...common, effect: 7, t: 5 });
  assert.deepEqual(a.pixels, b.pixels);
});

test("speed is clamped and defaults sensibly", () => {
  assert.equal(scrollSpeed(0), 6);
  assert.equal(scrollSpeed(100), 66);
  assert.equal(scrollSpeed(500), 66);
  assert.equal(scrollSpeed(undefined), scrollSpeed(80));
});

test("the frame width defaults, is clamped, and still honours the old frame switch", () => {
  assert.equal(frameWidth({}), 6);
  assert.equal(frameWidth({ frame_width: 3 }), 3);
  assert.equal(frameWidth({ frame_width: 0 }), 0);
  assert.equal(frameWidth({ frame_width: "8" }), 8);
  assert.equal(frameWidth({ frame_width: -4 }), 0);
  assert.equal(frameWidth({ frame_width: 99 }), 24);
  assert.equal(frameWidth({ frame_width: "x" }), 6);
  assert.equal(frameWidth({ frame: false }), 0);
  assert.equal(frameWidth({ frame: false, frame_width: 5 }), 5);
  assert.equal(frameWidth({ frame: true }), 6);
});
