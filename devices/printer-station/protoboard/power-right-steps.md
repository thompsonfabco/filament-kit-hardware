Build order (lowest parts first). The numbers are the callouts on the drawing; wire links carry no number:

- Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
- Wire GND: J2 to top − rail at number 2 (straight, 9 mm).
- Wire GND: J12 to top − rail at number 12 (straight, 9 mm).
- Wire 5V: J1 to top + rail at number 1 (straight, 6 mm).
- Part 1, RG1 (220 Ω): I8 to I13, lying flat.
- Part 2, RP1 (100 kΩ): F13 to bottom − rail at number 13, lying flat.
- Part 3, D1 (1N4001): banded end (K) in top + rail at number 14, other end (A) in I14.
- Part 4, Q1 (BS170): D in H14, G in H13, S in H12, flat face toward the top edge (the J side).
- Part 5, U1 sockets: two 1x8 female headers in C1-C8, G1-G8. Plug U1 in while soldering to keep them square, then take it out.
- Device wires 6-9, PN532: 6 GND in top − rail at number 4, 7 3V3 in H3, 8 SDA in A1, 9 SCL in A2. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 10-13, OLED: 10 GND in top − rail at number 6, 11 3V3 in I3, 12 SDA in B1, 13 SCL in B2. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 14-18, encoder: 14 CLK in H5, 15 DT in H4, 16 GND in top − rail at number 8, 17 SW in H7, 18 3V3 in J3. Solder each wire from the top, then tie the bundle to the board edge.
- Device wires 19-20, buzzer: 19 5V in top + rail at number 16, 20 BZ− in F14. Solder each wire from the top, then tie the bundle to the board edge.
- Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-right module.

| No. | Item | Holes |
|---|---|---|
|  | − rail link | right link pad, upper to right link pad, lower |
|  | wire GND | J2 to top − rail at number 2 |
|  | wire GND | J12 to top − rail at number 12 |
|  | wire 5V | J1 to top + rail at number 1 |
| 1 | RG1 220 Ω | I8 to I13 |
| 2 | RP1 100 kΩ | F13 to bottom − rail at number 13 |
| 3 | D1 1N4001 | K top + rail at number 14, A I14 |
| 4 | Q1 BS170 | D H14, G H13, S H12 |
| 5 | U1 sockets | C1-C8, G1-G8 |
| 6-9 | PN532 wires | 6 GND top − rail at number 4, 7 3V3 H3, 8 SDA A1, 9 SCL A2 |
| 10-13 | OLED wires | 10 GND top − rail at number 6, 11 3V3 I3, 12 SDA B1, 13 SCL B2 |
| 14-18 | encoder wires | 14 CLK H5, 15 DT H4, 16 GND top − rail at number 8, 17 SW H7, 18 3V3 J3 |
| 19-20 | buzzer wires | 19 5V top + rail at number 16, 20 BZ− F14 |
