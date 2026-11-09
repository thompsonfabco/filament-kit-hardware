# Shared KiCad library

The parts the stock KiCad 10 libraries don't have, shared by every device project under `devices/<device>/kicad/`.

- `filament-kit.kicad_sym`: the symbol library, nickname `filament-kit`.
- `filament-kit.pretty/`: the footprint library, nickname `filament-kit`.

Add both to a project's library tables with the paths relative to the project, for example
`${KIPRJMOD}/../../../kicad/filament-kit.kicad_sym`.

Every module symbol carries `Vmax` (volts), `Imax` (amperes), `Imax_basis` and `Datasheet`, copied from
`devices/intake-panel/catalogue.xml`. Where the catalogue says UNCONFIRMED, so does the symbol.

## Symbols

| Symbol | What it is | Pins | Footprint | Source |
|---|---|---|---|---|
| `ESP32-C3_SuperMini` | ESP32-C3 Super Mini board (U1) | 1-8 GPIO5 GPIO6 GPIO7 GPIO8 GPIO9 GPIO10 GPIO20 GPIO21 (left row), 9-16 5V GND 3V3 GPIO4 GPIO3 GPIO2 GPIO1 GPIO0 (right row). GPIO11-19 aren't on the header | `filament-kit:ESP32-C3_SuperMini` | Limits: catalogue U1, ESP32-C3 datasheet. Pin order, row spacing and pitch: owner photo and measurement of the board in hand |
| `MAX98357_Module` | AITRIP MAX98357 I2S amplifier module (U2) | 1 LRC, 2 BCLK, 3 DIN, 4 GAIN, 5 SD, 6 GND, 7 VIN (header), 8 OUT- and 9 OUT+ (screw terminal - and +) | `filament-kit:MAX98357_Module` | Limits: catalogue U2, MAX98357A datasheet. Pin order: owner photo of the board in hand (silk V914) |
| `SSD1306_I2C_Module` | SSD1306 128x64 OLED module, I2C 0x3C (U3) | 1 GND, 2 VCC, 3 SCL, 4 SDA | stock `PinHeader_1x04_P2.54mm_Vertical` | Limits: catalogue U3, SSD1306 datasheet. Pin order: owner photo of the board in hand |
| `BMP280_GY_6pin` | GY-BME/P280 board carrying a BMP280 (U4): temperature and pressure only. For humidity, fit the AHT20 + BMP280 board (U5) instead | 1 VCC, 2 GND, 3 SCL, 4 SDA, 5 CSB, 6 SDO | stock `PinHeader_1x06_P2.54mm_Vertical` | `Vmax` 4.25 V: BMP280 datasheet (catalogue's BMP280 entry). Board name and pin order: owner photo; the owner confirms the chip is a BMP280 (the photo alone can't tell BME280 from BMP280). The board has its own resistors: CSB is pulled high (I2C), SDO sets address 0x76 or 0x77 and the firmware tries both, so the panel leaves CSB and SDO unconnected |
| `AHT20_BMP280_Module` | BMP280 + AHT20 combination board (U5 and U6) | 1 VIN, 2 GND, 3 SCL, 4 SDA | stock `PinHeader_1x04_P2.54mm_Vertical` | Limits: catalogue U5 and U6. `Datasheet` is the BMP280's, `Datasheet_AHT20` the AHT20's |
| `Buzzer_3pin_Module` | 3-wire buzzer module (BZ1) | 1 VCC, 2 S, 3 GND | stock `PinHeader_1x03_P2.54mm_Vertical` | The catalogue lists it as passive, with no datasheet. Pin order: owner photo, front view, pins down, left to right. The board is marked low-level trigger (transistor-switched) |

Electrical types for ERC: the C3's 5V and 3V3 are power outputs (they feed the panel's rails) and its GND is a power
input, so a schematic needs a `PWR_FLAG` on GND. Module supply pins are power inputs, SDA is bidirectional, and SCL,
S and the amplifier's I2S, SD and GAIN pins are inputs. The amplifier's OUT+ and OUT- are outputs.

Module pin order varies by maker. The panel's harness order is GND 3V3 SDA SCL for the I2C boards and GND 3V3 S for the
buzzer; the J1-J5 headers fix that order, whatever order a module's own pins are in.

## Footprints

- `ESP32-C3_SuperMini`: two 1x8 rows of 1.7 mm pads with 1.0 mm drills, 2.54 mm pitch, 15.24 mm between rows.
  Numbering, viewed from the top (component side) with the USB socket at the top: pads 1-8 are the left row, top to
  bottom (GPIO5, GPIO6, GPIO7, GPIO8, GPIO9, GPIO10, GPIO20, GPIO21); pads 9-16 are the right row, top to bottom (5V,
  GND, 3V3, GPIO4, GPIO3, GPIO2, GPIO1, GPIO0). Pad 1 is square. F.Fab marks the USB end. The F.Fab outline is the
  board's 18 x 22.52 mm, centred on the pins.
- `MAX98357_Module`: one row of seven 1.7 mm pads, 1.0 mm drills, 2.54 mm pitch, viewed from the top with the header
  at the bottom: pad 1 (square) LRC, then BCLK, DIN, GAIN, SD, GND, VIN. Pads 8 (-) and 9 (+) are the screw terminal,
  on the opposite edge, - on the left. Their position (12.7 mm from the header, 5.08 mm apart) is a placeholder,
  UNCONFIRMED; the board outline and its two mounting holes aren't drawn.
- The buzzer and the I2C modules use the stock 2.54 mm pin headers, whose pad 1-N order matches the symbols.
- `ElectroCookie_Full`: the board as an outline, measured by the owner. The origin is one corner, with x along the
  89 mm side.
  - Edge.Cuts: a rectangle 89 x 52 mm.
  - NPTH holes: M3 (3.2 mm) at (7.75, 26) and (81.25, 26); M2 (2.2 mm) at (5.375, 8.25), (83.625, 8.25),
    (5.375, 43.75) and (83.625, 43.75).
  - F.Fab: reference dots on a 2.54 mm grid, centred on the board, left out within 0.6 mm of a mounting hole.
  - Reference designator `PCB`.
  - The breadboard strips aren't modelled as copper. The layout table in the guide is the reference for strip
    connections.

## UNCONFIRMED values

Check each of these against the part in hand before relying on it.

1. `ESP32-C3_SuperMini` row spacing, 15.24 mm: owner-confirmed (measured, 0.6 in).
2. `ESP32-C3_SuperMini` pad-to-pin mapping: owner-confirmed from a photo of the board (see Footprints).
3. `ESP32-C3_SuperMini` USB socket at the top end of the rows: owner-confirmed. How far the outline overhangs the
   pins at each end is still UNCONFIRMED.
4. `ESP32-C3_SuperMini`: `Imax_pin`, the per-pin current limit; the board's 3V3 regulator rating and 5 V pin path
   (catalogue U1).
5. `MAX98357_Module`: pin labels and order owner-confirmed, and the board has its own SD pull-up. Still UNCONFIRMED:
   the screw terminal's position, the board outline and the mounting holes.
6. `SSD1306_I2C_Module`: `Imax`. The pin order is owner-confirmed.
7. `BMP280_GY_6pin`: `Imax`. The board name, pin order and chip (BMP280) are owner-confirmed.
8. `AHT20_BMP280_Module`: `Imax`, the module's pin order, and the AHT20's 5.5 V as an absolute maximum. Its `Vmax` is
   4.25 V, the lower of the two chips' figures.
9. `Buzzer_3pin_Module`: `Vmax`, `Imax`, `Datasheet`. The pin order is owner-confirmed.
10. `ElectroCookie_Full`: the offset of the 2.54 mm hole grid from the board edge. The dots are centred on the board,
    and they are reference marks only.
