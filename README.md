# filament-kit-hardware

Hardware designs for the peripheral devices of [filament-kit](https://github.com/thompsonfabco/filament-kit): the
standard they share, build guides, wiring, parts, enclosures and bench results.

Firmware and the station code that talks to these devices live in filament-kit, not here.

## Devices

| Device | What it is | Status |
|---|---|---|
| [`intake-panel`](devices/intake-panel/guide.md) | Illuminated buttons (LEDs), OLED, speaker and room-air sensor for the intake station | ESP32-C3 (kit firmware 11); two board designs, a DIY through-hole board and a JLCPCB board |
| [Printer station (`printer-station`)](devices/printer-station/guide.md) | NFC reader with a knob that loads a spool into a printer slot | ESP32-C3; printer scan station case (Body, Face, Retainer and a 3MF print file) in `enclosures/printer-station/`, CC BY-NC-SA 4.0; fit unchecked |
| [`station-nfc`](devices/station-nfc/guide.md) | PN532 NFC reader on the intake station's USB | Bought (Teyleten PN532 V2.0, USB) |
| [`scale`](devices/scale/guide.md) | DYMO M10 USB postal scale | Bought; guide and parts list |
| [`webcam`](devices/webcam/guide.md) | USB camera that photographs new spools | Bought; guide and parts list |

The peripheral standard is in [standard.md](standard.md). The current design is
[specs/2026-11-09-peripheral-standard-design.md](specs/2026-11-09-peripheral-standard-design.md).

## Releases

Each release (a `vX.Y.Z` tag) carries the enclosure models from `enclosures/`:

- one zip per enclosure folder, `<device>-step-<version>.zip`, holding that folder's STEP files and the model `LICENSE` inside a folder named `<device>`;
- each print file (3MF), copied out as `<name>-<version>.3mf`.

Names are lowercase with hyphens. `python -I tools/make_release.py --version vX.Y.Z --out <dir>` builds the same files locally.

A tag `<group>-vX.Y` (for example `intake-station-v1.0`) releases one group: only the enclosure folders named `<group>` or `<group>-...` are built, and the version in the file names is the `vX.Y` part. Locally, add `--only <group>`.

## License

Everything outside `enclosures/` is licensed under GPL-3.0-only (see `LICENSE`), (c) 2026 thompsonfabco.

The model files in `enclosures/` are licensed under CC BY-NC-SA 4.0 (see `enclosures/LICENSE`). You are free to use, share and adapt them for any non-commercial purpose, with attribution, and adaptations must be shared under the same licence. No commercial use without permission.
