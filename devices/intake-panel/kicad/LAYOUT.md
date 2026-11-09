# Intake panel: layout on the ElectroCookie board

Placement of `intake-panel.kicad_pcb` on the ElectroCookie full-size solderable breadboard. Hole names and positions come from `kicad/electrocookie_full.xml`: columns 1-30 from left to right, rows J I H G F (upper half, J at the top) and E D C B A (lower half, A at the bottom), top view with the U1 USB socket to the left. A hole is written column then row, for example `13F`. Each column has two strips, F-J and A-E; nothing crosses the channel between F and E. The four rails run the full length of the board.

Rule: every strip carries one net. `python -I tools/strip_check.py` checks this against the board file. U2's screw-terminal pads 8-9 sit on the module, not in the board (`Board_pads` = `1-7`).

## Rails

| Rail | Net |
|---|---|
| top − rail | GND |
| top + rail | +5V |
| bottom − rail | GND |
| bottom + rail | +3V3 |

The two GND rails are joined by a wire link (listed below).

## Strips by net

Only strips that hold a part pin are listed; every other strip is empty.

| Strip | Net | Pins in it |
|---|---|---|
| 4 F-J | +5V | U1.9 at 4H |
| 5 F-J | GND | U1.10 at 5H |
| 6 F-J | +3V3 | U1.11 at 6H |
| 7 F-J | BTN_DISCARD | U1.12 at 7H |
| 8 F-J | BTN_HOLD | U1.13 at 8H |
| 9 F-J | not connected (U1-GPIO2 pad 14) | U1.14 at 9H |
| 10 F-J | LAMP_HOLD | U1.15 at 10H |
| 11 F-J | BUZZER | U1.16 at 11H, J5.3 at 11J |
| 12 F-J | +3V3 | J5.2 at 12J |
| 13 F-J | GND | J5.1 at 13J, RP2.2 at 13G |
| 15 F-J | HOLD_LAMP- | J3.4 at 15F |
| 16 F-J | +5V | J3.3 at 16F |
| 17 F-J | BTN_HOLD | J3.2 at 17F |
| 18 F-J | GND | J3.1 at 18F, J4.1 at 18J |
| 19 F-J | BTN_DISCARD | J4.2 at 19J |
| 20 F-J | +5V | J4.3 at 20J |
| 21 F-J | DISCARD_LAMP- | J4.4 at 21J, Q2.1 at 21G |
| 22 F-J | Q2_G | Q2.2 at 22G |
| 23 F-J | GND | Q2.3 at 23G |
| 24 F-J | LAMP_HOLD | RG1.1 at 24J |
| 25 F-J | Q1_G | RG1.2 at 25F |
| 26 F-J | HOLD_LAMP- | Q1.1 at 26G |
| 27 F-J | Q1_G | Q1.2 at 27G, RP1.1 at 27J |
| 28 F-J | GND | Q1.3 at 28G |
| 4 A-E | SDA | U1.1 at 4D, RI1.2 at 4A |
| 5 A-E | SCL | U1.2 at 5D |
| 6 A-E | LAMP_DISCARD | U1.3 at 6D |
| 7 A-E | not connected (U1-GPIO8 pad 4) | U1.4 at 7D |
| 8 A-E | not connected (U1-GPIO9 pad 5) | U1.5 at 8D |
| 9 A-E | I2S_BCLK | U1.6 at 9D |
| 10 A-E | I2S_LRC | U1.7 at 10D |
| 11 A-E | I2S_DIN | U1.8 at 11D |
| 12 A-E | SCL | RI2.2 at 12A |
| 13 A-E | Q2_G | RG2.2 at 13B, RP2.1 at 13E |
| 15 A-E | AMP_SD | RSD1.2 at 15A |
| 16 A-E | LAMP_DISCARD | RG2.1 at 16E |
| 18 A-E | GND | J1.1 at 18E, J2.1 at 18A |
| 19 A-E | +3V3 | J1.2 at 19E, J2.2 at 19A |
| 20 A-E | SDA | J1.3 at 20E, J2.3 at 20A |
| 21 A-E | SCL | J1.4 at 21E, J2.4 at 21A |
| 23 A-E | +5V | U2.7 at 23C |
| 24 A-E | GND | U2.6 at 24C |
| 25 A-E | AMP_SD | U2.5 at 25C |
| 26 A-E | not connected (U2-GAIN pad 4) | U2.4 at 26C |
| 27 A-E | I2S_DIN | U2.3 at 27C |
| 28 A-E | I2S_BCLK | U2.2 at 28C |
| 29 A-E | I2S_LRC | U2.1 at 29C |
| bottom + rail | +3V3 | RI1.1 at bottom + rail at column 5, RI2.1 at bottom + rail at column 10, RSD1.1 at bottom + rail at column 14 |
| top − rail | GND | RP1.2 at top − rail at column 25, C1.2 at top − rail at column 21 |
| top + rail | +5V | C1.1 at top + rail at column 21 |

## Wire links

Insulated solid-core wire, soldered hole to hole on the top side. A link marked "fit before U1" or "fit before U2" has an end under that module: solder it before the module's header goes in, and keep it flat. Lengths are hole-to-hole, straight line.

| # | Net | From | To | Length (mm) | Note |
|---|---|---|---|---|---|
| 1 | SDA | 4C | 20C | 40.6 |  |
| 2 | SCL | 5E | 12E | 17.8 | fit before U1 |
| 3 | SCL | 12C | 21C | 22.9 |  |
| 4 | LAMP_DISCARD | 6C | 16C | 25.4 |  |
| 5 | I2S_BCLK | 9E | 28E | 48.3 | fit before U1 |
| 6 | I2S_LRC | 10E | 29E | 48.3 | fit before U1 |
| 7 | I2S_DIN | 11E | 27E | 40.6 | fit before U1 |
| 8 | +5V | top + rail at column 4 | 4J | 6.1 |  |
| 9 | +5V | top + rail at column 16 | 16J | 6.1 |  |
| 10 | +5V | 16H | 20H | 10.2 |  |
| 11 | +5V | 20F | 23E | 10.8 |  |
| 12 | GND | top − rail at column 5 | 5J | 8.6 |  |
| 13 | GND | top − rail at column 23 | 23J | 8.6 |  |
| 14 | GND | 23F | 24E | 8.0 |  |
| 15 | GND | top − rail at column 28 | 28J | 8.6 |  |
| 16 | GND | 23I | 18H | 13.0 |  |
| 17 | GND | top − rail at column 13 | 13H | 13.7 |  |
| 18 | GND | 24D | 18C | 15.5 |  |
| 19 | +3V3 | bottom + rail at column 19 | 19C | 14.1 |  |
| 20 | +3V3 | bottom + rail at column 6 | 6F | 26.8 | fit before U1 |
| 21 | +3V3 | 6G | 12G | 15.2 | fit before U1 |
| 22 | BTN_DISCARD | 7G | 19H | 30.6 | fit before U1 |
| 23 | BTN_HOLD | 8G | 17H | 23.0 | fit before U1 |
| 24 | LAMP_HOLD | 10F | 24F | 35.6 | fit before U1 |
| 25 | AMP_SD | 25E | 15E | 25.4 |  |
| 26 | HOLD_LAMP- | 15I | 26I | 27.9 |  |
| 27 | Q1_G | 27I | 25I | 5.1 |  |
| 28 | Q2_G | 13D | 22F | 25.0 |  |

28 wire links in all.

## Bent leads

Pads more than 0.1 mm from their hole (the strip check warns above 0.5 mm):

- RG1 pad 1 at 24J: 0.16 mm
- RG1 pad 2 at 25F: 0.16 mm
- RG2 pad 1 at 16E: 0.31 mm
- RG2 pad 2 at 13B: 0.31 mm
- RI1 pad 1 at bottom + rail at column 5: 0.39 mm
- RI1 pad 2 at 4A: 0.39 mm
- RI2 pad 1 at bottom + rail at column 10: 0.10 mm
- RI2 pad 2 at 12A: 0.10 mm
- RSD1 pad 1 at bottom + rail at column 14: 0.39 mm
- RSD1 pad 2 at 15A: 0.39 mm
- C1 pad 1 at top + rail at column 21: 0.50 mm
- C1 pad 2 at top − rail at column 21: 0.50 mm

JST-XH headers have a 2.50 mm pitch against the board's 2.54 mm; centred on their holes, each pin is at most 0.06 mm off.

## Placement

| Part | Pins (pin at hole) |
|---|---|
| U1 | 1 4D, 2 5D, 3 6D, 4 7D, 5 8D, 6 9D, 7 10D, 8 11D, 9 4H, 10 5H, 11 6H, 12 7H, 13 8H, 14 9H, 15 10H, 16 11H |
| U2 | 1 29C, 2 28C, 3 27C, 4 26C, 5 25C, 6 24C, 7 23C |
| J1 | 1 18E, 2 19E, 3 20E, 4 21E |
| J2 | 1 18A, 2 19A, 3 20A, 4 21A |
| J3 | 1 18F, 2 17F, 3 16F, 4 15F |
| J4 | 1 18J, 2 19J, 3 20J, 4 21J |
| J5 | 1 13J, 2 12J, 3 11J |
| Q1 | 1 26G, 2 27G, 3 28G |
| Q2 | 1 21G, 2 22G, 3 23G |
| RG1 | 1 24J, 2 25F |
| RG2 | 1 16E, 2 13B |
| RP1 | 1 27J, 2 top − rail at column 25 |
| RP2 | 1 13E, 2 13G |
| RI1 | 1 bottom + rail at column 5, 2 4A |
| RI2 | 1 bottom + rail at column 10, 2 12A |
| RSD1 | 1 bottom + rail at column 14, 2 15A |
| C1 | 1 top + rail at column 21, 2 top − rail at column 21 |

Positions of holes, rails and pad pairs are approximate (from photos, see the XML); strip membership is exact. Mounting-hole positions are measured.
