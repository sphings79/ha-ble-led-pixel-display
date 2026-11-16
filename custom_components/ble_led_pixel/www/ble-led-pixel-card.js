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
    frame: "Frame",
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
    frame: "Rahmen",
  },
};

function t(hass, key) {
  const lang = ((hass && hass.language) || "en").slice(0, 2);
  return (TEXTS[lang] || TEXTS.en)[key] || TEXTS.en[key] || key;
}

class BleLedPixelCard extends HTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._loadedKey = null;
    this._source = null; // {width, height, data: Uint8ClampedArray}
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
      frame: true,
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
    if (this._observer || !this._canvasHost) return;
    this._observeSize();
  }

  disconnectedCallback() {
    if (this._observer) {
      this._observer.disconnect();
      this._observer = null;
    }
  }

  _build() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: "open" });
    this._root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        .title { padding: 12px 16px 0; font-weight: 500; color: var(--primary-text-color); }
        .host { position: relative; padding: 12px; }
        .framed .host { padding: 14px; background: #1c1c1c; }
        .framed canvas { box-shadow: 0 0 0 4px #000; }
        canvas { display: block; margin: 0 auto; background: #000; image-rendering: pixelated; }
        .note { position: absolute; inset: 12px; display: flex; align-items: center;
                justify-content: center; text-align: center; color: #cfcfcf;
                font: 500 14px/1.3 var(--paper-font-body1_-_font-family, sans-serif);
                text-shadow: 0 0 6px #000; pointer-events: none; padding: 8px; }
        .badge { position: absolute; top: 18px; right: 20px; padding: 2px 8px; border-radius: 10px;
                 background: #b71c1c; color: #fff; font: 600 11px sans-serif; text-transform: uppercase; }
        .dim canvas { opacity: 0.35; }
        .hidden { display: none; }
      </style>
      <ha-card>
        <div class="title hidden"></div>
        <div class="host"><canvas></canvas>
          <div class="note hidden"></div><div class="badge hidden"></div></div>
      </ha-card>`;
    this._card = this._root.querySelector("ha-card");
    this._title = this._root.querySelector(".title");
    this._canvasHost = this._root.querySelector(".host");
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
    const key = picture ? `${picture}|${state.state}` : null;
    if (key && key !== this._loadedKey) {
      this._loadedKey = key;
      this._load(picture, state.state, key);
    }
    this._render();
  }

  async _load(picture, stamp, key) {
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
      this._source = {
        width: bitmap.width,
        height: bitmap.height,
        data: ctx.getImageData(0, 0, bitmap.width, bitmap.height).data,
      };
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
    this._card.classList.toggle("framed", this._config.frame !== false);
    this._draw();
  }

  _draw() {
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

    const gap = Math.max(0, Number(this._config.gap) || 0);
    const available = Math.max(40, this._width - (this._config.frame !== false ? 28 : 24));
    let pixel = Number(this._config.pixel_size) || 0;
    if (!pixel) pixel = Math.max(2, Math.floor(available / cols));
    const dpr = window.devicePixelRatio || 1;
    const cssW = cols * pixel;
    const cssH = rows * pixel;
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, cssW, cssH);

    const showPicture = kind === "image" || kind === "text";
    const src = showPicture ? this._source : null;
    const round = this._config.shape !== "square";
    const dot = Math.max(1, pixel - gap);
    const radius = dot / 2;
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        let color = "#151515";
        if (src && x < src.width && y < src.height) {
          const i = (y * src.width + x) * 4;
          const r = src.data[i], g = src.data[i + 1], b = src.data[i + 2];
          if (r + g + b > 30) color = `rgb(${r},${g},${b})`;
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
    this._canvasHost.classList.toggle("dim", offline);
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
      { name: "frame", selector: { boolean: {} } },
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
      frame: true,
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

console.info(`%c BLE-LED-PIXEL-CARD %c ${VERSION} `, "background:#222;color:#0f0", "");
