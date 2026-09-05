<div align="center">
  <img src="assets/banner.svg" alt="BLE LED Pixel Display Banner: eine Home-Assistant-Integration für Bluetooth-LE-LED-Pixelmatrix-Panels, daneben zwei 64-mal-16-Pixel-Panels mit den Anzeigen PV 2400W in Grün und H100M 57 in Rot" width="100%">

  # BLE LED Pixel Display — Bluetooth-LE-Pixelmatrix-Panels für Home Assistant

  **Live-Daten aus Home Assistant auf ein günstiges Bluetooth-LED-Panel bringen — Text, Bilder, animierte GIFs, Material Design Icons und zusammengesetzte Layouts.**
  Eine Custom Integration für LED-Pixelmatrix-Displays mit iPIXEL-Color-Protokoll, verkauft als **BGLight** und als **B.K. Light LED Pixel Board** bei Action. Vollständig lokal über Bluetooth LE — keine Cloud, keine Hersteller-App, kein Konto.

  [![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge)](https://hacs.xyz)
  [![Release](https://img.shields.io/github/v/release/sphings79/ha-ble-led-pixel-display?style=for-the-badge&color=7C7CF5)](https://github.com/sphings79/ha-ble-led-pixel-display/releases)
  [![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-41BDF5?style=for-the-badge)](https://www.home-assistant.io)
  [![Lizenz](https://img.shields.io/badge/Lizenz-GPL--3.0-3ddc97?style=for-the-badge)](LICENSE)

  [English](README.md) · **Deutsch**
</div>

<div align="center">
  <img src="assets/panels.gif" alt="Animation: ein 64x16-BLE-LED-Pixel-Panel wechselt durch H 99M 62, PV 2400W, SoC 78% und B 1557W, daneben ein 32x32-Panel mit Herz, Sonne, Batterie und Blitz" width="100%">

  <sub>Links: Live-Text auf einem 64×16-Panel. Rechts: Bilder auf einem 32×32-Panel — beides aus Home Assistant gesteuert.</sub>
</div>

## Inhalt

- [Was die Integration macht](#was-die-integration-macht)
- [Unterstützte Geräte](#unterstützte-geräte)
- [Aktionen](#aktionen)
- [Installation](#installation)
- [Entitäten](#entitäten)
- [Anzeigemodi](#anzeigemodi)
- [Flackern vermeiden: wie Updates wirklich funktionieren](#flackern-vermeiden-wie-updates-wirklich-funktionieren)
- [Beispiele](#beispiele)
- [Schriften](#schriften)
- [Warum dieser Fork](#warum-dieser-fork)
- [Fehlersuche](#fehlersuche)
- [Häufige Fragen](#häufige-fragen)
- [Weitere Home-Assistant-Projekte](#weitere-home-assistant-projekte)
- [Mitmachen](#mitmachen)
- [Haftungsausschluss](#haftungsausschluss)
- [Lizenz](#lizenz)

## Was die Integration macht

Diese Panels werden als Spielerei verkauft — man setzt per Handy-App über Bluetooth eine Nachricht, das war's. Diese Integration macht daraus ein vollwertiges Ausgabegerät für Home Assistant: eine `text`-Entität, die jede Automation beschreiben kann, dazu Aktionen für Bilder, GIFs, Icons und mehrteilige Layouts.

Typische Anwendungen:

- **Energieanzeige an der Wand** — aktuelle PV-Erzeugung, Batterie-Ladestand, Hausverbrauch, Restzeit bis der Speicher voll ist
- **Status-Ticker** — wer zu Hause ist, nächster Kalendereintrag, ob das Garagentor offen steht
- **Warnungen** — rotes Panel, wenn ein Fenster offen ist während die Heizung läuft, oder wenn die Waschmaschine fertig ist
- **Umgebungsinfos** — Wetter-Icon plus Temperatur, zusammengesetzt in einem Layout

Alles läuft lokal über Bluetooth LE. Bluetooth-Proxys von Home Assistant werden unterstützt, das Panel muss also nicht in der Nähe des Home-Assistant-Hosts stehen.

## Unterstützte Geräte

Jedes Panel, das sich als `LED_BLE_*` mit der Service-UUID `0000fa01-0000-1000-8000-00805f9b34fb` meldet und das iPIXEL-Color-Protokoll spricht. Bekannte Marken:

| Marke | Anmerkung |
| --- | --- |
| **B.K. Light** | Bei Action. Auf der Verpackung steht „LED pixel board" (Artikel **ACT1026**, 13×13 cm, 32×32) bzw. „LED fun screen" (Artikel **ACT1025**, 37×9 cm, 64×16); die Shop-Bezeichnung ist je nach Land übersetzt, in den Niederlanden etwa „Led-pixelbord" und „Led-pixel scherm". Produkt-ID `000702`. |
| **HYPERLITE** | Produkt-IDs `002501`–`002509`, `002513`, `002514` |
| **EZYEVY** | Produkt-IDs `002510`–`002512` |
| **BGLight** | Gleiches Protokoll |
| Generische „iPixel Color"-Panels | Alles, wo die Hersteller-App iPixel Color heißt |

Die Auflösung wird vom Gerät selbst gemeldet, üblich ist 64×16. Meldet dein Panel falsche Maße, siehe [Fehlersuche](#fehlersuche).

## Aktionen

<img src="assets/actions.svg" alt="Die fünf Aktionen der Integration: send_text für gerätegerenderten Lauftext, send_image_file für Bilder und animierte GIFs, send_mdi_icon für Material Design Icons, send_layout zum Kombinieren von bis zu vier Icons, einem Bild und vier Textbereichen, sowie send_test_pattern zur Prüfung von Größe und Farbreihenfolge" width="100%">

Alle Aktionen richten sich an die `text`-Entität des Panels und lassen sich aus Automationen, Skripten und den Entwicklerwerkzeugen → Aktionen aufrufen.

## Installation

### HACS (empfohlen)

1. HACS in Home Assistant öffnen
2. Drei-Punkte-Menü oben rechts → **Benutzerdefinierte Repositories**
3. Repository-URL: `https://github.com/sphings79/ha-ble-led-pixel-display`
4. Kategorie: **Integration** → **Hinzufügen**
5. Nach **BLE LED Pixel Display** suchen und installieren
6. Home Assistant neu starten

### Manuell

1. `custom_components/ble_led_pixel` in das `custom_components`-Verzeichnis von Home Assistant kopieren
2. Home Assistant neu starten

### Panel hinzufügen

Panel einschalten und sicherstellen, dass **kein Handy damit verbunden ist** — ein verbundenes Panel sendet keine Bluetooth-Werbepakete mehr und ist für Home Assistant unsichtbar.

Normalerweise findet Home Assistant es von selbst und bietet es unter **Einstellungen → Geräte & Dienste** an. Andernfalls manuell hinzufügen: **Integration hinzufügen → BLE LED Pixel Display**, dann das Panel aus der Liste wählen. Geräte, deren Name mit `LED_BLE_` beginnt, sind mit einem Stern markiert. Die manuelle Eingabe einer MAC-Adresse gibt es als Rückfallebene.

## Entitäten

| Entität | Domain | Funktion |
| --- | --- | --- |
| **Display** | `text` | Der angezeigte Text. Aus jeder Automation beschreibbar. |
| **Text Color** | `light` | Vordergrundfarbe als RGB |
| **Background Color** | `light` | Hintergrundfarbe als RGB |
| **Brightness** | `number` | 1–100 |
| **Mode** | `select` | `textimage`, `text` oder `clock` — siehe [Anzeigemodi](#anzeigemodi) |
| **Font** | `select` | TTF/OTF-Schriften, siehe [Schriften](#schriften) |
| **Font Size**, **Line Spacing** | `number` | Layout im Modus `textimage` |
| **Text Animation**, **Text Speed**, **Text Rainbow** | `number` | Lauftext und Effekte im Modus `text` |
| **Clock Style** | `select` | 9 Uhrendesigns |
| **Clock 24h**, **Clock Show Date** | `switch` | Uhr-Optionen |
| **Antialiasing** | `switch` | Kantenglättung im Modus `textimage` |
| **Auto Update** | `switch` | **Vorher [Flackern vermeiden](#flackern-vermeiden-wie-updates-wirklich-funktionieren) lesen** |
| **Update Display** | `button` | Überträgt den gespeicherten Zustand ans Panel |
| **Sync Time** | `button` | Stellt die Geräteuhr |
| Device Type, Display Width, Display Height, MCU-/WiFi-Version | `sensor` | Diagnose |

## Anzeigemodi

| Modus | Rendering | Geeignet für |
| --- | --- | --- |
| **`text`** | Das Gerät rendert den Text selbst | Lauftext, geringste Bluetooth-Last, flüssigste Animation |
| **`textimage`** | Home Assistant rendert den Text mit Pillow zu einem Bild und überträgt es | Eigene TTF-Schriften, exakte Größen, Kantenglättung, mehrzeilig mit `\n` |
| **`clock`** | Uhr im Gerät | Eine Uhr, in 9 Varianten |

## Flackern vermeiden: wie Updates wirklich funktionieren

Das ist der nicht offensichtliche Teil — und er entscheidet darüber, ob das Panel ruhig läuft oder bei jeder Änderung flackert.

**Mit eingeschaltetem `Auto Update` löst jede einzelne Änderung sofort ein Rendern aus.** Den Text zu setzen ist ein Bluetooth-Schreibvorgang, die Farbe zu setzen ein zweiter. Dazwischen zeigt das Panel kurz den alten Wert in der neuen Farbe — oder den neuen Wert in der alten Farbe. Bei träger Bluetooth-Verbindung dauert das über eine Sekunde und ist deutlich sichtbar.

**Mit ausgeschaltetem `Auto Update` speichern `text.set_value` und `light.turn_on` den Wert nur.** Nichts erreicht das Panel, bis der Button `Update Display` gedrückt wird — der überträgt dann Text und Farbe **gemeinsam in einem einzigen Schreibvorgang**.

Für alles, was sich regelmäßig aktualisiert, also so:

```yaml
# Einmalig von Hand: den Schalter "Auto Update" ausschalten.
actions:
  - action: text.set_value
    target: { entity_id: text.display }
    data: { value: "PV 2400W" }
  - action: light.turn_on
    target: { entity_id: light.text_color }
    data: { rgb_color: [0, 255, 0] }
  - action: button.press          # beides landet gleichzeitig auf dem Panel
    target: { entity_id: button.update_display }
```

Zwei weitere Vorteile: Es ist schneller, weil ein Bluetooth-Durchlauf zwei oder drei ersetzt, und das Timing wird berechenbar.

Der einzige Haken: Mit ausgeschaltetem `Auto Update` bewirkt eine Änderung von Text oder Farbe in der Home-Assistant-Oberfläche nichts Sichtbares, bis der Button gedrückt wird. Wenn ohnehin eine Automation regelmäßig drückt, fällt das nicht auf.

> **Tipp:** Die Farbe nur schreiben, wenn sie sich tatsächlich geändert hat. Bei einem Panel, das durch fünf Anzeigen rotiert und nur eine davon grün ist, spart das vier Bluetooth-Schreibvorgänge pro Durchlauf.

## Beispiele

### Energieanzeige, die durch mehrere Werte rotiert

Eine einzige Automation, die alle fünf Sekunden zwischen PV-Erzeugung, Ladestand und Hausverbrauch wechselt:

```yaml
alias: LED-Panel Energie-Rotation
triggers:
  - trigger: time_pattern
    seconds: /5
mode: single
max_exceeded: silent
variables:
  screens: >-
    {% set pv = states('sensor.pv_leistung') | float(0) %}
    {% set soc = states('sensor.batterie_soc') | float(0) %}
    {% set haus = states('sensor.hausverbrauch') | float(0) %}
    {% set ns = namespace(l=[]) %}
    {% if pv > 0 %}
      {% set ns.l = ns.l + [{'text': 'PV %d W' | format(pv), 'color': [0, 255, 0]}] %}
    {% endif %}
    {% set ns.l = ns.l + [{'text': 'SoC %d%%' | format(soc), 'color': [255, 0, 0]}] %}
    {% set ns.l = ns.l + [{'text': 'H %d W' | format(haus), 'color': [255, 0, 0]}] %}
    {{ ns.l }}
actions:
  - variables:
      screen: "{{ screens[(states('counter.panel_schritt') | int(0)) % (screens | length)] }}"
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
    target: { entity_id: counter.panel_schritt }
```

Die Anzeigenliste wird als Daten aufgebaut, dadurch fallen Anzeigen ohne Aussage von selbst aus dem Zyklus — nachts also keine PV-Anzeige. Ein `counter`-Helfer hält die Position.

> **Auf die Zeichenzahl achten.** Viele Panels schalten auf eine zweite Ansicht um, sobald der Text länger ist als hineinpasst — das sieht aus, als würde die Anzeige springen. Zeichenketten kurz und vorhersehbar halten und Zahlen auf feste Breite auffüllen.

### Ein Bild oder animiertes GIF

```yaml
- action: ble_led_pixel.send_image_file
  target: { entity_id: text.display }
  data:
    file_path: /config/www/panel/regen.gif
    resize_method: fit          # oder "crop"
```

Der Pfad muss für Home Assistant lesbar sein und in `allowlist_external_dirs` stehen, wenn er außerhalb von `/config` liegt.

### Ein Material Design Icon

```yaml
- action: ble_led_pixel.send_mdi_icon
  target: { entity_id: text.display }
  data:
    icon: mdi:weather-pouring
    color: [65, 189, 245]
    scale: 1.0
```

Icons werden bei Bedarf geladen, jeder MDI-Name funktioniert also, ohne den Icon-Satz mitzuliefern.

### Wetter-Icon und Temperatur nebeneinander

```yaml
- action: ble_led_pixel.send_layout
  target: { entity_id: text.display }
  data:
    icon: mdi:weather-sunny
    icon_x: 0
    icon_y: 0
    icon_size: 16
    icon_color: [255, 193, 7]
    text: "{{ states('sensor.aussentemperatur') | round(0) }}°C"
    text_x: 20
    text_y: 4
    text_color: [230, 237, 243]
```

`send_layout` setzt bis zu vier Icons, ein Bild und vier unabhängige Textbereiche zusammen, jeweils mit eigener Position, Farbe, Ausrichtung und optionalem Scrollen oder Blinken.

### Lauftext, vom Gerät gerendert

```yaml
- action: ble_led_pixel.send_text
  target: { entity_id: text.display }
  data:
    text: "Klingel — jemand steht an der Haustür"
    color: [255, 107, 107]
    animation: 1        # scrollen
    speed: 60
```

Das ist die sparsamste Variante: Das Panel scrollt selbst, Home Assistant überträgt die Zeichenkette nur einmal.

### Ein neues Panel prüfen

```yaml
- action: ble_led_pixel.send_test_pattern
  target: { entity_id: text.display }
```

Vier farbige Quadranten — prüft Auflösung und Reihenfolge der Farbkanäle in einem Durchgang.

## Schriften

Die Schrift wird in der Select-Entität **Font** gewählt und in dieser Reihenfolge gesucht:

1. `custom_components/ble_led_pixel/fonts/` — mit der Integration ausgeliefert
2. Das Paket `pypixelcolor`
3. Systemschriftverzeichnisse

Die gewählte Schrift wird zu einem absoluten Pfad aufgelöst und so an den Renderer übergeben — dieselbe Schrift funktioniert also in jedem Modus und in der Aktion `send_text`. Für eigene Schriften eine `.ttf` oder `.otf` in den Ordner `fonts/` der Integration legen und neu starten. Lässt sich eine Schrift nirgends finden, wird `VCR_OSD_MONO` verwendet und eine Warnung protokolliert.

Mitgeliefert: `3x5-de`, `5x5`, `7x5`, `WP7xn`, `OpenSans-Light`, `Lepidos`, `VCR_OSD_MONO`.

> **Warum über Pfade:** pypixelcolor kennt auch eigene Schriftnamen, die sind aber nicht stabil — 0.4 lieferte `CUSONG`, `SIMSUN` und `VCR_OSD_MONO` mit, spätere Versionen ersetzten alle drei durch ein einzelnes `UNIFONT`. Upstream reichte diese Namen unverändert weiter, ein Bibliotheks-Update hätte die Schrift also verändert oder unbrauchbar gemacht. Dieser Fork löst stattdessen alles zu einem Dateipfad auf und liefert `VCR_OSD_MONO` mit, damit sie immer vorhanden ist.

## Warum dieser Fork

Er führt [cagcoach/ha-ipixel-color](https://github.com/cagcoach/ha-ipixel-color) von Christian Grund fort, wo es seit Dezember 2025 keine Commits mehr gab, während sich Pull Requests und Issues ansammelten. Er übernimmt die Arbeit an Bildern, MDI-Icons und Layouts von [tigers75](https://github.com/tigers75/ha-ipixel-color) und ergänzt eigene Korrekturen — darunter den oben beschriebenen Schrift-Rückfall und die Festlegung von `pypixelcolor` auf Versionen unter 0.5, weil die Bibliothek inzwischen genau die Schriften entfernt hat, auf die bestehende Installationen angewiesen sind.

**Die Domain heißt `ble_led_pixel`, nicht `ipixel_color`.** Beide Integrationen lassen sich dadurch parallel installieren, sodass sich ein Panel nach dem anderen umziehen lässt, statt alles auf einmal umzustellen.

## Fehlersuche

**Das Panel wird nicht gefunden.** Zuerst die Hersteller-App trennen — ein verbundenes Panel sendet keine Werbepakete mehr. Prüfen, ob die Bluetooth-Integration von Home Assistant eingerichtet ist und das Panel in Reichweite des Hosts oder eines Bluetooth-Proxys steht.

**Falsche Breite oder Höhe.** Die Maße kommen vom Gerät. Manche Firmware meldet sie falsch; die Sensoren Display Width und Display Height mit der Realität abgleichen.

**Text wird abgeschnitten oder die Anzeige springt zwischen zwei Ansichten.** Die Zeichenkette ist länger, als auf das Panel passt. Kürzen oder `send_text` mit Lauftext verwenden.

**Die gewählte Schrift wirkt nicht.** Im Protokoll nach `Font ... not found in any location` suchen. Schriftdateien gehören in den Ordner `fonts/` der Integration, danach ist ein Neustart nötig.

**Farbe und Text ändern sich zu unterschiedlichen Zeitpunkten.** Siehe [Flackern vermeiden](#flackern-vermeiden-wie-updates-wirklich-funktionieren).

**In der Oberfläche passiert nichts, wenn ich etwas ändere.** `Auto Update` ist aus. `Update Display` drücken.

Debug-Protokollierung:

```yaml
logger:
  logs:
    custom_components.ble_led_pixel: debug
```

## Häufige Fragen

**Braucht das die Hersteller-App oder ein Konto?** Nein. Alles läuft lokal über Bluetooth LE.

**Funktioniert das mit einem Bluetooth-Proxy?** Ja, das Panel muss nicht in der Nähe des Home-Assistant-Hosts stehen.

**Kann ich das parallel zur originalen `ipixel_color`-Integration betreiben?** Ja — andere Domain, kein Konflikt. Nur nicht beide gleichzeitig mit demselben Panel verbinden.

**Kann ich auslesen, ob das Panel eingeschaltet ist?** Nein. Das Protokoll kennt einen Befehl zum Schalten, aber keinen zum Abfragen. Der Schalter zeigt, was Home Assistant zuletzt gesendet hat — nicht den Gerätezustand.

**Wie viele Panels gehen?** So viele, wie das Bluetooth-Setup verkraftet. Jedes wird ein eigenes Gerät.

**Welche Auflösungen funktionieren?** Was das Gerät meldet, typischerweise 64×16.

## Weitere Home-Assistant-Projekte

- [Marstek Venus Modbus](https://github.com/sphings79/marstek_venus_modbus_dev) — Marstek-Venus-Speicher über lokales Modbus TCP
- [Shelly Modbus](https://github.com/sphings79/shelly-modbus-home-assistant) — Shelly-Energiezähler und -Relais über Modbus TCP, ohne Cloud
- [StateGuard](https://github.com/sphings79/stateguard-home-assistant) — meldet, wenn Entitäten ausfallen oder aufhören zu senden
- [IntegrationGuard](https://github.com/sphings79/integrationguard-home-assistant) — welche deiner HACS-Erweiterungen noch gepflegt wird
- [MyIP.wtf](https://github.com/sphings79/myip-wtf-home-assistant) — öffentliche IPv4/IPv6, Provider und Geolokalisierung als Sensoren
- [Leasing KM](https://github.com/sphings79/leasing-km-home-assistant) — Kilometerkontingent eines Leasingfahrzeugs
- [Marstek Venus BLE](https://github.com/sphings79/ha-marstek-ble) — Marstek Venus E über Bluetooth LE
- [Marstek offline endpoint](https://github.com/sphings79/Marstek-offline-endpoint) — Venus-Speicher ohne Cloud betreiben
- [Power Flow Card Plus Mushroom](https://github.com/sphings79/power-flow-card-plus-mushroom) — Energiefluss-Karte mit mehreren Speichern und PV-Quellen

## Mitmachen

Issues und Pull Requests sind willkommen — besonders Rückmeldungen von Panels anderer Marken, gerne mit genauer Modellbezeichnung und gemeldeter Auflösung.

Wenn diese Integration deine Energiedaten an die Wand gebracht hat, hilft ein ⭐ auf dem Repository anderen wirklich dabei, es zu finden.

<a href="https://buymeacoffee.com/sphings"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black" alt="Buy me a coffee"></a>

## Haftungsausschluss

Inoffizielle, von der Community gebaute Integration. Nicht verbunden mit, unterstützt oder freigegeben von Home Assistant, Nabu Casa, Action, BGLight oder einem Panel-Hersteller. Markennamen dienen ausschließlich der Beschreibung der Kompatibilität. Siehe [NOTICE](NOTICE).

## Lizenz

[GPL-3.0](LICENSE) — übernommen aus dem ursprünglichen Werk von Christian Grund. Die Protokollbibliothek [pypixelcolor](https://github.com/lucagoc/pypixelcolor) von lucagoc steht unter MIT.

---

<sub>Home Assistant LED-Matrix · Bluetooth-LE-Pixeldisplay · BGLight Home Assistant · B.K. Light LED Pixel Board Action · Led-pixelbord Action · Led-pixel scherm · LED fun screen · iPixel Color Integration · LED_BLE · 64x16 Pixel-Panel · HACS Custom Integration · Sensorwert auf LED-Panel anzeigen · animiertes GIF auf LED-Matrix · Material Design Icon auf Display · Lauftext-Ticker · Energie-Dashboard Wandanzeige · PV-Erzeugung anzeigen · Batterie-Ladestand Panel · ohne Cloud · lokales Bluetooth · pypixelcolor</sub>
