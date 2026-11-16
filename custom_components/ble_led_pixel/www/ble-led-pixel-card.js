/*
 * BLE LED Pixel Display card
 *
 * Shows what a panel is displaying, as LEDs. It reads the "Preview" image
 * entity that the integration creates for every panel: the picture is the
 * last content Home Assistant sent, so a change made with the vendor app or
 * a remote is not reflected.
 *
 * Served by the integration itself; nothing to install separately.
 */

const CARD_TYPE = "ble-led-pixel-card";
const VERSION = "2.5.0";

const TEXTS = {
  en: {
    offline: "offline",
    nothing: "Nothing sent yet",
    clock: "Clock mode",
    slot: "Stored picture",
    presets: "Preset",
    scoreboard: "Scoreboard",
    countdown: "Countdown",
    stopwatch: "Stopwatch",
    other: "Drawn by the panel",
    entity: "Preview entity",
    name: "Name",
    shape: "LED shape",
    round: "Round",
    square: "Square",
    pixel_size: "Pixel size (0 = fit the card)",
    gap: "Gap between LEDs",
    frame_width: "Frame width in px (0 = no frame)",
  },
  de: {
    offline: "offline",
    nothing: "Noch nichts gesendet",
    clock: "Uhr-Modus",
    slot: "Gespeichertes Bild",
    presets: "Voreinstellung",
    scoreboard: "Anzeigetafel",
    countdown: "Countdown",
    stopwatch: "Stoppuhr",
    other: "Vom Panel selbst gezeichnet",
    entity: "Vorschau-Entität",
    name: "Name",
    shape: "LED-Form",
    round: "Rund",
    square: "Eckig",
    pixel_size: "Pixelgröße (0 = an Karte anpassen)",
    gap: "Abstand zwischen den LEDs",
    frame_width: "Rahmenbreite in px (0 = kein Rahmen)",
  },
};

function t(hass, key) {
  const lang = ((hass && hass.language) || "en").slice(0, 2);
  return (TEXTS[lang] || TEXTS.en)[key] || TEXTS.en[key] || key;
}


// ---------------------------------------------------------------------------
// Effects
//
// The panel's firmware animates text itself and does not document how, so
// these are close imitations, not copies. What is known: the effect codes, the
// 0-100 speed byte and the text as a line of per-character cells. What is
// assumed is marked below, and every assumption is a constant here to tune.
// ---------------------------------------------------------------------------

const EFFECT = { FIXED: 0, LEFT: 1, RIGHT: 2, UP: 3, DOWN: 4, BLINK: 5, BREATHE: 6 };

// Assumed: a higher speed value scrolls faster, from slow to about 66 px/s.
function scrollSpeed(speed) {
  const value = Number.isFinite(Number(speed)) ? Number(speed) : 80;
  return 6 + Math.max(0, Math.min(100, value)) * 0.6;
}

// Assumed: blinking is a fixed 2 Hz and ignores the speed byte.
const BLINK_HALF_PERIOD = 0.5;
function blinkOn(t) {
  return Math.floor(t / BLINK_HALF_PERIOD) % 2 === 0;
}

// Assumed: breathing is a 3 s sine between 15 % and full brightness.
const BREATHE_PERIOD = 3;
function breatheFactor(t) {
  return 0.15 + 0.85 * (0.5 + 0.5 * Math.cos((2 * Math.PI * t) / BREATHE_PERIOD));
}

// The preview entity serves its picture enlarged by a whole factor (`scale`),
// so it is readable in an ordinary picture card. Take the panel's own pixels
// back out of it: the middle of every block.
function shrink(src, scale) {
  const factor = Math.max(1, Math.round(Number(scale) || 1));
  if (factor === 1) return src;
  const width = Math.floor(src.width / factor);
  const height = Math.floor(src.height / factor);
  const data = new Uint8ClampedArray(width * height * 4);
  const half = factor >> 1;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const from = ((y * factor + half) * src.width + (x * factor + half)) * 4;
      const to = (y * width + x) * 4;
      data[to] = src.data[from];
      data[to + 1] = src.data[from + 1];
      data[to + 2] = src.data[from + 2];
      data[to + 3] = 255;
    }
  }
  return { width, height, data };
}

function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return [0, 0, 0];
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function fillColor(out, rgb) {
  for (let i = 0; i < out.length; i += 4) {
    out[i] = rgb[0];
    out[i + 1] = rgb[1];
    out[i + 2] = rgb[2];
    out[i + 3] = 255;
  }
}

// Copy `src` ({width, height, data}) into `out` (cols x rows) with its top-left
// corner at (ox, oy). Anything outside the panel is clipped.
function blit(out, cols, rows, src, ox, oy) {
  for (let sy = 0; sy < src.height; sy++) {
    const y = oy + sy;
    if (y < 0 || y >= rows) continue;
    for (let sx = 0; sx < src.width; sx++) {
      const x = ox + sx;
      if (x < 0 || x >= cols) continue;
      const i = (sy * src.width + sx) * 4;
      const o = (y * cols + x) * 4;
      out[o] = src.data[i];
      out[o + 1] = src.data[i + 1];
      out[o + 2] = src.data[i + 2];
      out[o + 3] = 255;
    }
  }
}

/*
 * One frame of a panel, `t` seconds after its content arrived.
 *   base  - the first view the integration sent (any size; placed top-left)
 *   strip - the whole line of text, only for the scrolling effects
 * Returns {pixels: Uint8ClampedArray (cols * rows * 4), factor: brightness}.
 */
function composeFrame({ cols, rows, base, strip, effect, speed, bg, t }) {
  const pixels = new Uint8ClampedArray(cols * rows * 4);
  const background = hexToRgb(bg);
  const showBase = () => {
    fillColor(pixels, background);
    if (base) blit(pixels, cols, rows, base, 0, 0);
  };
  let factor = 1;

  const scrolling =
    strip && (effect === EFFECT.LEFT || effect === EFFECT.RIGHT ||
              effect === EFFECT.UP || effect === EFFECT.DOWN);
  if (scrolling) {
    fillColor(pixels, background);
    const pace = scrollSpeed(speed) * t;
    const mid = Math.floor((rows - strip.height) / 2);
    if (effect === EFFECT.LEFT || effect === EFFECT.RIGHT) {
      const span = cols + strip.width;
      const d = Math.floor(pace % span);
      const x = effect === EFFECT.LEFT ? cols - d : d - strip.width;
      blit(pixels, cols, rows, strip, x, mid);
    } else {
      const span = rows + strip.height;
      const d = Math.floor(pace % span);
      const y = effect === EFFECT.UP ? rows - d : d - strip.height;
      blit(pixels, cols, rows, strip, 0, y);
    }
  } else if (effect === EFFECT.BLINK) {
    if (blinkOn(t)) showBase();
    else fillColor(pixels, background);
  } else {
    showBase();
    if (effect === EFFECT.BREATHE) factor = breatheFactor(t);
  }
  return { pixels, factor };
}

// Which effects move: the scrolls need the whole line, blinking and breathing
// work on the first view. Snowflake and anything unknown stay still, because
// how the firmware draws them is not known.
function isAnimated(effect, hasStrip) {
  if (effect === EFFECT.BLINK || effect === EFFECT.BREATHE) return true;
  return hasStrip && effect >= EFFECT.LEFT && effect <= EFFECT.DOWN;
}

// Width of the dark bezel around the panel, in px. `frame: false` (the option
// before there was a width) still means no frame.
const DEFAULT_FRAME_WIDTH = 6;
const MAX_FRAME_WIDTH = 24;
function frameWidth(config) {
  const wanted = config && config.frame_width;
  if (wanted !== undefined && wanted !== null && wanted !== "" && Number.isFinite(Number(wanted))) {
    return Math.max(0, Math.min(MAX_FRAME_WIDTH, Number(wanted)));
  }
  if (config && config.frame === false) return 0;
  return DEFAULT_FRAME_WIDTH;
}

class BleLedPixelCard extends HTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._loadedKey = null;
    this._source = null; // first view: {width, height, data: Uint8ClampedArray}
    this._strip = null; // whole line of text for scrolling effects
    this._stripKey = null;
    this._t0 = 0; // when the current content arrived (ms)
    this._raf = 0;
    this._lastPaint = 0;
    this._wanted = null;
    this._width = 0;
    this._observer = null;
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Choose the preview entity of a panel");
    }
    this._config = {
      shape: "round",
      pixel_size: 0,
      gap: 1,
      ...config,
    };
    this._build();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("ble-led-pixel-card-editor");
  }

  static getStubConfig(hass) {
    const found = Object.keys((hass && hass.states) || {}).find(
      (id) =>
        id.startsWith("image.") &&
        hass.states[id].attributes &&
        "kind" in hass.states[id].attributes
    );
    return { entity: found || "" };
  }

  connectedCallback() {
    if (!this._observer && this._canvasHost) this._observeSize();
    this._draw();
  }

  disconnectedCallback() {
    if (this._observer) {
      this._observer.disconnect();
      this._observer = null;
    }
    this._stopLoop();
  }

  _build() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: "open" });
    this._root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        .title { padding: 12px 16px 0; font-weight: 500; color: var(--primary-text-color); }
        .host { padding: 12px; text-align: center; }
        .bezel { position: relative; display: inline-block; line-height: 0;
                 background: #1c1c1c; border-radius: 10px; }
        .bezel.bare { background: none; border-radius: 0; }
        canvas { display: block; background: #000; border-radius: 4px; image-rendering: pixelated; }
        .bare canvas { border-radius: 0; }
        .note { position: absolute; inset: 0; display: flex; align-items: center;
                justify-content: center; text-align: center; color: #cfcfcf;
                font: 500 14px/1.3 var(--paper-font-body1_-_font-family, sans-serif);
                text-shadow: 0 0 6px #000; pointer-events: none; padding: 8px; box-sizing: border-box; }
        .badge { position: absolute; top: 8px; right: 8px; padding: 2px 8px; border-radius: 10px;
                 background: #b71c1c; color: #fff; font: 600 11px/1.4 sans-serif; text-transform: uppercase; }
        .dim canvas { opacity: 0.35; }
        .hidden { display: none; }
      </style>
      <ha-card>
        <div class="title hidden"></div>
        <div class="host"><div class="bezel"><canvas></canvas>
          <div class="note hidden"></div><div class="badge hidden"></div></div></div>
      </ha-card>`;
    this._card = this._root.querySelector("ha-card");
    this._title = this._root.querySelector(".title");
    this._canvasHost = this._root.querySelector(".host");
    this._bezel = this._root.querySelector(".bezel");
    this._canvas = this._root.querySelector("canvas");
    this._note = this._root.querySelector(".note");
    this._badge = this._root.querySelector(".badge");
    this._observeSize();
  }

  _observeSize() {
    if (typeof ResizeObserver === "undefined" || !this._canvasHost) return;
    this._observer = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0].contentRect.width);
      if (w && w !== this._width) {
        this._width = w;
        this._draw();
      }
    });
    this._observer.observe(this._canvasHost);
  }

  _state() {
    return this._hass && this._config ? this._hass.states[this._config.entity] : undefined;
  }

  _update() {
    const state = this._state();
    if (!state) {
      this._render();
      return;
    }
    const picture = state.attributes.entity_picture;
    const key = picture ? `${picture}|${state.state}|${state.attributes.scale || 1}` : null;
    if (key && key !== this._loadedKey) {
      this._loadedKey = key;
      this._t0 = performance.now(); // an effect starts over with new content
      this._load(picture, state.state, key, state.attributes.scale);
    }
    this._loadStrip(state.attributes.strip);
    this._render();
  }

  // The whole line of text, sent as a base64 PNG for the scrolling effects.
  async _loadStrip(encoded) {
    if (!encoded) {
      this._strip = null;
      this._stripKey = null;
      return;
    }
    if (encoded === this._stripKey) return;
    this._stripKey = encoded;
    try {
      const response = await fetch(`data:image/png;base64,${encoded}`);
      const bitmap = await createImageBitmap(await response.blob());
      if (encoded !== this._stripKey) return;
      const scratch = document.createElement("canvas");
      scratch.width = bitmap.width;
      scratch.height = bitmap.height;
      const ctx = scratch.getContext("2d", { willReadFrequently: true });
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(bitmap, 0, 0);
      this._strip = {
        width: bitmap.width,
        height: bitmap.height,
        data: ctx.getImageData(0, 0, bitmap.width, bitmap.height).data,
      };
      this._draw();
    } catch (err) {
      this._strip = null;
    }
  }

  async _load(picture, stamp, key, scale) {
    try {
      const sep = picture.includes("?") ? "&" : "?";
      const response = await fetch(`${picture}${sep}t=${encodeURIComponent(stamp)}`);
      if (!response.ok) throw new Error(response.status);
      const blob = await response.blob();
      const bitmap = await createImageBitmap(blob);
      if (key !== this._loadedKey) return; // a newer picture was asked for
      const scratch = document.createElement("canvas");
      scratch.width = bitmap.width;
      scratch.height = bitmap.height;
      const ctx = scratch.getContext("2d", { willReadFrequently: true });
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(bitmap, 0, 0);
      const full = {
        width: bitmap.width,
        height: bitmap.height,
        data: ctx.getImageData(0, 0, bitmap.width, bitmap.height).data,
      };
      this._source = shrink(full, scale);
      this._draw();
    } catch (err) {
      this._source = null;
      this._loadedKey = null;
      this._draw();
    }
  }

  _render() {
    if (!this._root || !this._config) return;
    const name = this._config.name;
    this._title.textContent = name || "";
    this._title.classList.toggle("hidden", !name);
    this._draw();
  }

  _stopLoop() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = 0;
  }

  _startLoop() {
    if (this._raf || !this.isConnected) return;
    const tick = (now) => {
      this._raf = 0;
      if (!this.isConnected) return;
      const attrs = (this._state() && this._state().attributes) || {};
      if (!this._animated(attrs)) return;
      this._raf = requestAnimationFrame(tick);
      if (document.hidden || now - this._lastPaint < 33) return; // ~30 fps
      this._lastPaint = now;
      this._draw(true);
    };
    this._raf = requestAnimationFrame(tick);
  }

  _animated(attrs) {
    return (
      attrs.kind === "text" &&
      attrs.connected !== false &&
      isAnimated(Number(attrs.effect_code), !!this._strip)
    );
  }

  _draw(fromLoop) {
    if (!this._canvas || !this._config) return;
    const state = this._state();
    const attrs = (state && state.attributes) || {};
    const kind = attrs.kind || "none";
    const hass = this._hass;
    const cols = attrs.width || (this._source && this._source.width) || 0;
    const rows = attrs.height || (this._source && this._source.height) || 0;
    const canvas = this._canvas;

    if (!cols || !rows) {
      canvas.width = 2;
      canvas.height = 2;
      this._showNote(state ? t(hass, "nothing") : "");
      return;
    }

    const animated = this._animated(attrs);
    if (animated) this._startLoop();
    else this._stopLoop();

    let frame = null;
    let factor = 1;
    if ((kind === "image" || kind === "text") && this._source) {
      const seconds = animated ? (performance.now() - this._t0) / 1000 : 0;
      ({ pixels: frame, factor } = composeFrame({
        cols,
        rows,
        base: this._source,
        strip: this._strip,
        effect: kind === "text" ? Number(attrs.effect_code) : EFFECT.FIXED,
        speed: attrs.speed,
        bg: attrs.bg_color,
        t: seconds,
      }));
    }
    this._paint(canvas, frame, factor, cols, rows);

    if (fromLoop) return; // the note and badge only change with the state
    let note = "";
    if (kind === "none") note = t(hass, "nothing");
    else if (kind === "placeholder") {
      const label = attrs.label || "other";
      note = t(hass, label);
      if (label === "slot" && attrs.text) note += ` ${attrs.text}`;
    }
    this._showNote(note);
    const offline = attrs.connected === false;
    this._badge.textContent = t(hass, "offline");
    this._badge.classList.toggle("hidden", !offline);
    this._bezel.classList.toggle("dim", offline);
  }

  _paint(canvas, frame, factor, cols, rows) {
    const gap = Math.max(0, Number(this._config.gap) || 0);
    const fw = frameWidth(this._config);
    this._bezel.style.padding = `${fw}px`;
    this._bezel.classList.toggle("bare", fw === 0);
    const available = Math.max(40, this._width - 2 * fw);
    let pixel = Number(this._config.pixel_size) || 0;
    if (!pixel) pixel = Math.max(2, Math.floor(available / cols));
    const dpr = window.devicePixelRatio || 1;
    const cssW = cols * pixel;
    const cssH = rows * pixel;
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    const wantW = Math.round(cssW * dpr);
    const wantH = Math.round(cssH * dpr);
    if (canvas.width !== wantW || canvas.height !== wantH) {
      canvas.width = wantW;
      canvas.height = wantH;
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, cssW, cssH);

    const round = this._config.shape !== "square";
    const dot = Math.max(1, pixel - gap);
    const radius = dot / 2;
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        let color = "#151515";
        if (frame) {
          const i = (y * cols + x) * 4;
          const r = frame[i], g = frame[i + 1], b = frame[i + 2];
          if (r + g + b > 30) {
            color = factor === 1
              ? `rgb(${r},${g},${b})`
              : `rgb(${Math.round(r * factor)},${Math.round(g * factor)},${Math.round(b * factor)})`;
          }
        }
        ctx.fillStyle = color;
        const px = x * pixel + (pixel - dot) / 2;
        const py = y * pixel + (pixel - dot) / 2;
        if (round) {
          ctx.beginPath();
          ctx.arc(px + radius, py + radius, radius, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.fillRect(px, py, dot, dot);
        }
      }
    }
  }

  _showNote(text) {
    this._note.textContent = text || "";
    this._note.classList.toggle("hidden", !text);
  }
}

class BleLedPixelCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _schema() {
    const h = this._hass;
    return [
      {
        name: "entity",
        required: true,
        selector: { entity: { domain: "image", integration: "ble_led_pixel" } },
      },
      { name: "name", selector: { text: {} } },
      {
        name: "shape",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "round", label: t(h, "round") },
              { value: "square", label: t(h, "square") },
            ],
          },
        },
      },
      { name: "pixel_size", selector: { number: { min: 0, max: 24, mode: "box" } } },
      { name: "gap", selector: { number: { min: 0, max: 8, step: 0.5, mode: "box" } } },
      { name: "frame_width", selector: { number: { min: 0, max: MAX_FRAME_WIDTH, mode: "box" } } },
    ];
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: ev.detail.value },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = {
      shape: "round",
      pixel_size: 0,
      gap: 1,
      frame_width: frameWidth(this._config),
      ...this._config,
    };
    this._form.schema = this._schema();
    this._form.computeLabel = (item) => t(this._hass, item.name);
  }
}

customElements.define(CARD_TYPE, BleLedPixelCard);
customElements.define("ble-led-pixel-card-editor", BleLedPixelCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TYPE,
  name: "BLE LED Pixel Display",
  description: "Shows what a BLE LED pixel panel is displaying.",
  preview: true,
});

// Lets the effect maths be tested without a browser.
globalThis.__bleLedPixelCard = {
  composeFrame, isAnimated, scrollSpeed, blinkOn, breatheFactor, frameWidth, shrink, EFFECT,
};

console.info(`%c BLE-LED-PIXEL-CARD %c ${VERSION} `, "background:#222;color:#0f0", "");
