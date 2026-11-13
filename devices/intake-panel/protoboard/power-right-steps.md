Build order (lowest parts first). The numbers are the callouts on the drawing; wire links carry no number:

- Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
- Wire 3V3: G3 to bottom + rail at number 21 (one bend, 75 mm).
- Wire LAMP R: E3 to F24 (two bends, along the centre channel, 61 mm).
- Wire SCL: E2 to E19 (two bends, along the centre channel, 46 mm).
- Wire SDA: C1 to C18 (straight, 43 mm).
- Wire BCLK: B6 to B11 (straight, 13 mm).
- Wire DIN: A8 to A12 (straight, 10 mm).
- Wire LRC: E7 to E10 (straight, 8 mm).
- Wire GND: A15 to bottom − rail at number 15 (straight, 7 mm).
- Wire 5V: top + rail at number 16 to E16 (straight, 24 mm).
- Wire GND: J2 to top − rail at number 2 (straight, 9 mm).
- Wire GND: J12 to top − rail at number 12 (straight, 9 mm).
- Wire GND: J28 to top − rail at number 28 (straight, 9 mm).
- Wire 5V: J1 to top + rail at number 1 (straight, 6 mm).
- Part 1, RG1 (220 Ω): F7 to F11, lying flat.
- Part 2, RG2 (220 Ω): I24 to I27, lying flat.
- Part 3, RP1 (100 kΩ): J11 to top − rail at number 11, lying flat.
- Part 4, RP2 (100 kΩ): J27 to top − rail at number 27, lying flat.
- Part 6, Q1 (BS170): D in H10, G in H11, S in H12, flat face toward the bottom edge (the A side).
- Part 7, Q2 (BS170): D in G26, G in G27, S in G28, flat face toward the bottom edge (the A side).
- Part 8, U1 sockets: two 1x8 female headers in D1-D8, H1-H8. Plug U1 in while soldering to keep them square, then take it out.
- Part 9, U2 socket: a 1x7 female header in D10-D16. Plug U2 in while soldering to keep it square, then take it out.
- Device wires 10-13, OLED: 10 GND in bottom − rail at number 22, 11 3V3 in bottom + rail at number 22, 12 SDA in D18, 13 SCL in D19. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 14-17, AIR: 14 GND in bottom − rail at number 25, 15 3V3 in bottom + rail at number 25, 16 SDA in B18, 17 SCL in B19. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 18-21, YELLOW: 18 GND in top − rail at number 9, 19 HOLD in I5, 20 5V in top + rail at number 9, 21 LED− Y in J10. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 22-25, RED: 22 GND in top − rail at number 23, 23 DISC in J4, 24 5V in top + rail at number 23, 25 LED− R in J26. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 26-28, BUZZER: 26 GND in top − rail at number 7, 27 3V3 in I3, 28 BUZ in J8. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 29-32, NFC: 29 GND in bottom − rail at number 28, 30 3V3 in bottom + rail at number 28, 31 SDA in E18, 32 SCL in C19. Solder each wire from the top, then tie the bundle to the board edge.
- Leave the + rail link pads beside the left M3 hole open: the top + rail is 5V and the bottom + rail is 3V3. Joining them would short 5V to 3V3. Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND, no short from 5V to 3V3. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-right module. Plug U2 in with its screw terminal toward the bottom edge.

Parts fitted only when needed (marked DNP on the drawing): leave their holes free.

- Part 5, RSD1 (10 kΩ), bottom + rail at number 14 and A14: fit it only if the amplifier's SD pin reads near 0 V in the SD pull-up check.

| No. | Item | Holes |
|---|---|---|
|  | − rail link | right link pad, upper to right link pad, lower |
|  | wire 3V3 | G3 to bottom + rail at number 21 (one bend) |
|  | wire LAMP R | E3 to F24 (along the channel) |
|  | wire SCL | E2 to E19 (along the channel) |
|  | wire SDA | C1 to C18 |
|  | wire BCLK | B6 to B11 |
|  | wire DIN | A8 to A12 |
|  | wire LRC | E7 to E10 |
|  | wire GND | A15 to bottom − rail at number 15 |
|  | wire 5V | top + rail at number 16 to E16 |
|  | wire GND | J2 to top − rail at number 2 |
|  | wire GND | J12 to top − rail at number 12 |
|  | wire GND | J28 to top − rail at number 28 |
|  | wire 5V | J1 to top + rail at number 1 |
| 1 | RG1 220 Ω | F7 to F11 |
| 2 | RG2 220 Ω | I24 to I27 |
| 3 | RP1 100 kΩ | J11 to top − rail at number 11 |
| 4 | RP2 100 kΩ | J27 to top − rail at number 27 |
| 5 | RSD1 10 kΩ (fit only if needed) | bottom + rail at number 14 and A14 |
| 6 | Q1 BS170 | D H10, G H11, S H12 |
| 7 | Q2 BS170 | D G26, G G27, S G28 |
| 8 | U1 sockets | D1-D8, H1-H8 |
| 9 | U2 socket | D10-D16 |
| 10-13 | OLED wires | 10 GND bottom − rail at number 22, 11 3V3 bottom + rail at number 22, 12 SDA D18, 13 SCL D19 |
| 14-17 | AIR wires | 14 GND bottom − rail at number 25, 15 3V3 bottom + rail at number 25, 16 SDA B18, 17 SCL B19 |
| 18-21 | YELLOW wires | 18 GND top − rail at number 9, 19 HOLD I5, 20 5V top + rail at number 9, 21 LED− Y J10 |
| 22-25 | RED wires | 22 GND top − rail at number 23, 23 DISC J4, 24 5V top + rail at number 23, 25 LED− R J26 |
| 26-28 | BUZZER wires | 26 GND top − rail at number 7, 27 3V3 I3, 28 BUZ J8 |
| 29-32 | NFC wires | 29 GND bottom − rail at number 28, 30 3V3 bottom + rail at number 28, 31 SDA E18, 32 SCL C19 |
