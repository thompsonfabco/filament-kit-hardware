Build order (lowest parts first). The numbers are the callouts on the drawing; wire links carry no number:

- Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
- Wire 3V3: E3 to top + rail at number 18 (two bends, along the centre channel, 62 mm).
- Wire SCL: F2 to F20 (two bends, along the centre channel, 49 mm).
- Wire LAMP R: F3 to E17 (two bends, along the centre channel, 43 mm).
- Wire SDA: H9 to H19 (straight, 25 mm).
- Wire SDA: G1 to G9 (straight, 20 mm).
- Wire BCLK: J6 to J11 (straight, 13 mm).
- Wire DIN: I8 to I12 (straight, 10 mm).
- Wire GND: J15 to top − rail at number 15 (straight, 9 mm).
- Wire LRC: F7 to F10 (straight, 8 mm).
- Wire 5V: A1 to bottom + rail at number 1 (straight, 9 mm).
- Wire 5V: A16 to bottom + rail at number 16 (straight, 9 mm).
- Wire 5V: E16 to F16 (straight, 8 mm).
- Wire GND: A2 to bottom − rail at number 2 (straight, 7 mm).
- Wire GND: A11 to bottom − rail at number 11 (straight, 7 mm).
- Wire GND: A14 to bottom − rail at number 14 (straight, 7 mm).
- Part 1, RG1 (220 Ω): C7 to C10, lying flat.
- Part 2, RG2 (220 Ω): C17 to C13, lying flat.
- Part 3, RP1 (100 kΩ): B10 to bottom − rail at number 10, lying flat.
- Part 4, RP2 (100 kΩ): B13 to bottom − rail at number 13, lying flat.
- Part 6, Q1 (BS170): D in E9, G in E10, S in E11, flat face toward the bottom edge (the A side).
- Part 7, Q2 (BS170): D in E12, G in E13, S in E14, flat face toward the bottom edge (the A side).
- Part 8, U1 sockets: two 1x8 female headers in D1-D8, H1-H8. Plug U1 in while soldering to keep them square, then take it out.
- Part 9, U2 socket: a 1x7 female header in G10-G16. Plug U2 in while soldering to keep it square, then take it out.
- Device wires 10-13, OLED (J1): 10 GND in top − rail at number 21, 11 3V3 in top + rail at number 21, 12 SDA in J19, 13 SCL in J20. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 14-17, AIR (J2): 14 GND in top − rail at number 25, 15 3V3 in top + rail at number 25, 16 SDA in I19, 17 SCL in I20. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 18-21, YELLOW (J3): 18 GND in bottom − rail at number 7, 19 HOLD in C5, 20 5V in bottom + rail at number 7, 21 LED− Y in D9. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 22-25, RED (J4): 22 GND in bottom − rail at number 4, 23 DISC in A4, 24 5V in bottom + rail at number 4, 25 LED− R in A12. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 26-28, BUZZER (J5): 26 GND in bottom − rail at number 12, 27 3V3 in C3, 28 BUZ in A8. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 29-32, NFC (J7): 29 GND in top − rail at number 29, 30 3V3 in top + rail at number 29, 31 SDA in F19, 32 SCL in H20. Solder each wire from the top, then tie the bundle to the board edge.
- Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-left module. Plug U2 in with its screw terminal toward the top edge.

Parts fitted only when needed (marked DNP on the drawing): leave their holes free.

- Part 5, RSD1 (10 kΩ), top + rail at number 14 and I14: fit it only if the amplifier's SD pin reads near 0 V in the SD pull-up check.

| No. | Item | Holes |
|---|---|---|
|  | − rail link | right link pad, upper to right link pad, lower |
|  | wire 3V3 | E3 to top + rail at number 18 (along the channel) |
|  | wire SCL | F2 to F20 (along the channel) |
|  | wire LAMP R | F3 to E17 (along the channel) |
|  | wire SDA | H9 to H19 |
|  | wire SDA | G1 to G9 |
|  | wire BCLK | J6 to J11 |
|  | wire DIN | I8 to I12 |
|  | wire GND | J15 to top − rail at number 15 |
|  | wire LRC | F7 to F10 |
|  | wire 5V | A1 to bottom + rail at number 1 |
|  | wire 5V | A16 to bottom + rail at number 16 |
|  | wire 5V | E16 to F16 |
|  | wire GND | A2 to bottom − rail at number 2 |
|  | wire GND | A11 to bottom − rail at number 11 |
|  | wire GND | A14 to bottom − rail at number 14 |
| 1 | RG1 220 Ω | C7 to C10 |
| 2 | RG2 220 Ω | C17 to C13 |
| 3 | RP1 100 kΩ | B10 to bottom − rail at number 10 |
| 4 | RP2 100 kΩ | B13 to bottom − rail at number 13 |
| 5 | RSD1 10 kΩ (fit only if needed) | top + rail at number 14 and I14 |
| 6 | Q1 BS170 | D E9, G E10, S E11 |
| 7 | Q2 BS170 | D E12, G E13, S E14 |
| 8 | U1 sockets | D1-D8, H1-H8 |
| 9 | U2 socket | G10-G16 |
| 10-13 | J1 OLED wires | 10 GND top − rail at number 21, 11 3V3 top + rail at number 21, 12 SDA J19, 13 SCL J20 |
| 14-17 | J2 AIR wires | 14 GND top − rail at number 25, 15 3V3 top + rail at number 25, 16 SDA I19, 17 SCL I20 |
| 18-21 | J3 YELLOW wires | 18 GND bottom − rail at number 7, 19 HOLD C5, 20 5V bottom + rail at number 7, 21 LED− Y D9 |
| 22-25 | J4 RED wires | 22 GND bottom − rail at number 4, 23 DISC A4, 24 5V bottom + rail at number 4, 25 LED− R A12 |
| 26-28 | J5 BUZZER wires | 26 GND bottom − rail at number 12, 27 3V3 C3, 28 BUZ A8 |
| 29-32 | J7 NFC wires | 29 GND top − rail at number 29, 30 3V3 top + rail at number 29, 31 SDA F19, 32 SCL H20 |
