# filament-kit-hardware

Hardware designs for the peripheral devices of [filament-kit](https://github.com/thompsonfabco/filament-kit): the
standard they share, build guides, wiring, parts, enclosures and bench results.

Firmware and the station code that talks to these devices live in filament-kit, not here.

## Devices

| Device | What it is | Status |
|---|---|---|
| [`intake-panel`](devices/intake-panel/guide.md) | Illuminated buttons (LEDs), OLED, speaker and room-air sensor for the intake station | Moving from ESP8266 to ESP32-C3 |
| [`bench-reader`](devices/bench-reader/guide.md) | NFC reader with a knob that loads a spool into a printer slot | ESP32-C3; case in `enclosures/bench-reader/`, fit unchecked |
| [`station-nfc`](devices/station-nfc/guide.md) | PN532 NFC reader on the intake station's USB | Bought board, to be documented |
| [`scale`](devices/scale/guide.md) | DYMO M10 USB postal scale | Bought, to be documented |
| [`webcam`](devices/webcam/guide.md) | USB camera that photographs new spools | Bought, to be documented |

The peripheral standard is in [standard.md](standard.md). The current design is
[specs/2026-11-09-peripheral-standard-design.md](specs/2026-11-09-peripheral-standard-design.md).

## License

Everything outside `enclosures/` is licensed under GPL-3.0-only (see `LICENSE`), (c) 2026 thompsonfabco.

The model files in `enclosures/` are licensed under CC BY-NC-SA 4.0 (see `enclosures/LICENSE`). You are free to use, share and adapt them for any non-commercial purpose, with attribution, and adaptations must be shared under the same licence. No commercial use without permission.
