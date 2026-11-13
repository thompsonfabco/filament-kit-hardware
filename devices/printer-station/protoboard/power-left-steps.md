Build order (lowest parts first). The numbers are the callouts on the drawing; wire links carry no number:

- Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
- Wire 5V: A1 to bottom + rail at number 1 (straight, 9 mm).
- Wire GND: A2 to bottom − rail at number 2 (straight, 7 mm).
- Wire GND: A11 to bottom − rail at number 11 (straight, 7 mm).
- Wire BZ−: D13 to D15 (straight, 5 mm).
- Part 1, RG1 (220 Ω): C8 to C12, lying flat.
- Part 2, RP1 (100 kΩ): B12 to bottom − rail at number 12, lying flat.
- Part 3, D1 (1N4001): banded end (K) in bottom + rail at number 15, other end (A) in A15.
- Part 4, Q1 (BS170): D in E13, G in E12, S in E11, flat face toward the top edge (the J side).
- Part 5, U1 sockets: two 1x8 female headers in D1-D8, H1-H8. Plug U1 in while soldering to keep them square, then take it out.
- Device wires 6-9, PN532: 6 GND in top − rail at number 1, 7 3V3 in C3, 8 SDA in I1, 9 SCL in I2. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 10-13, OLED: 10 GND in top − rail at number 3, 11 3V3 in B3, 12 SDA in J1, 13 SCL in J2. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 14-18, encoder: 14 CLK in A5, 15 DT in A4, 16 GND in bottom − rail at number 6, 17 SW in A7, 18 3V3 in A3. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 19-20, buzzer: 19 5V in bottom + rail at number 14, 20 BZ− in B13. Solder each wire from the top, then tie the bundle to the board edge.
- Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-left module.

| No. | Item | Holes |
|---|---|---|
|  | − rail link | right link pad, upper to right link pad, lower |
|  | wire 5V | A1 to bottom + rail at number 1 |
|  | wire GND | A2 to bottom − rail at number 2 |
|  | wire GND | A11 to bottom − rail at number 11 |
|  | wire BZ− | D13 to D15 |
| 1 | RG1 220 Ω | C8 to C12 |
| 2 | RP1 100 kΩ | B12 to bottom − rail at number 12 |
| 3 | D1 1N4001 | K bottom + rail at number 15, A A15 |
| 4 | Q1 BS170 | D E13, G E12, S E11 |
| 5 | U1 sockets | D1-D8, H1-H8 |
| 6-9 | PN532 wires | 6 GND top − rail at number 1, 7 3V3 C3, 8 SDA I1, 9 SCL I2 |
| 10-13 | OLED wires | 10 GND top − rail at number 3, 11 3V3 B3, 12 SDA J1, 13 SCL J2 |
| 14-18 | encoder wires | 14 CLK A5, 15 DT A4, 16 GND bottom − rail at number 6, 17 SW A7, 18 3V3 A3 |
| 19-20 | buzzer wires | 19 5V bottom + rail at number 14, 20 BZ− B13 |
