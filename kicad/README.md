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
| `ESP32-C3_SuperMini` | ESP32-C3 Super Mini board (U1) | 1 5V, 2 GND, 3 3V3, 4-14 GPIO0-GPIO10, 15 GPIO21, 16 GPIO20. GPIO11-19 aren't on the header | `filament-kit:ESP32-C3_SuperMini` | Limits: catalogue U1, ESP32-C3 datasheet. Pin numbers: the espboards.dev pin table (https://www.espboards.dev/esp32/esp32-c3-super-mini/). Row spacing: protosupplies.com listing, "0.6 in row to row" |
| `MAX98357_Module` | AITRIP MAX98357 I2S amplifier module (U2) | 1 VIN, 2 GND, 3 SD, 4 GAIN, 5 DIN, 6 BCLK, 7 LRC, 8 OUT+, 9 OUT- | none | Limits: catalogue U2, MAX98357A datasheet |
| `SSD1306_I2C_Module` | SSD1306 128x64 OLED module, I2C 0x3C (U3) | 1 GND, 2 VCC, 3 SCL, 4 SDA | stock `PinHeader_1x04_P2.54mm_Vertical` | Limits: catalogue U3, SSD1306 datasheet |
| `BME280_Module` | BME280 board (U4) | 1 VIN, 2 GND, 3 SCL, 4 SDA | stock `PinHeader_1x04_P2.54mm_Vertical` | Limits: catalogue U4, BME280 datasheet |
| `AHT20_BMP280_Module` | BMP280 + AHT20 combination board (U5 and U6) | 1 VIN, 2 GND, 3 SCL, 4 SDA | stock `PinHeader_1x04_P2.54mm_Vertical` | Limits: catalogue U5 and U6. `Datasheet` is the BMP280's, `Datasheet_AHT20` the AHT20's |
| `Buzzer_3pin_Module` | 3-wire passive buzzer module (BZ1) | 1 GND, 2 VCC, 3 S | stock `PinHeader_1x03_P2.54mm_Vertical` | The catalogue lists it as passive, with no datasheet |

Electrical types for ERC: the C3's 5V and 3V3 are power outputs (they feed the panel's rails) and its GND is a power
input, so a schematic needs a `PWR_FLAG` on GND. Module supply pins are power inputs, SDA is bidirectional, and SCL,
S and the amplifier's I2S, SD and GAIN pins are inputs. The amplifier's OUT+ and OUT- are outputs.

Module pin order varies by maker. The panel's harness order is GND 3V3 SDA SCL for the I2C boards and GND 3V3 S for the
buzzer; the J1-J5 headers fix that order, whatever order a module's own pins are in.

## Footprints

- `ESP32-C3_SuperMini`: two 1x8 rows of 1.7 mm pads with 1.0 mm drills, 2.54 mm pitch, 15.24 mm between rows.
  Pads 1-8 are row A and 9-16 row B, both counted from the same end. The F.Fab outline is the board's 18 x 22.52 mm,
  centred on the pins.
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

1. `ESP32-C3_SuperMini` row spacing, 15.24 mm: one listing gives it, with no dimensioned drawing.
2. `ESP32-C3_SuperMini` pad-to-pin mapping: which pins are in which row, and in what order along the row. The sources
   read give a pin table but not the physical layout, so pads 1-8 and 9-16 follow the table's numbering, not the
   board.
3. `ESP32-C3_SuperMini` outline position relative to the pins, and so where the USB-C socket sits.
4. `ESP32-C3_SuperMini`: `Imax_pin`, the per-pin current limit; the board's 3V3 regulator rating and 5 V pin path
   (catalogue U1).
5. `MAX98357_Module`: pin labels, pin order, the SD pull-up, and the screw terminal's position. So the symbol has no
   footprint yet, and its pin numbers are a placeholder.
6. `SSD1306_I2C_Module`: `Imax`, and the module's pin order.
7. `BME280_Module`: `Imax`, and the module's pin order.
8. `AHT20_BMP280_Module`: `Imax`, the module's pin order, and the AHT20's 5.5 V as an absolute maximum. Its `Vmax` is
   4.25 V, the lower of the two chips' figures.
9. `Buzzer_3pin_Module`: `Vmax`, `Imax`, `Datasheet`, and the module's pin order.
10. `ElectroCookie_Full`: the offset of the 2.54 mm hole grid from the board edge. The dots are centred on the board,
    and they are reference marks only.
