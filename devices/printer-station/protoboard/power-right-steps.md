Build order (lowest parts first; the numbers on the wires in the top view are these step numbers):

1. Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
2. Wire 3V3: F3 to D16 (one bend, 43 mm).
3. Wire BUZ: F8 to F9 (straight, 3 mm).
4. Wire SDA: A1 to A19 (straight, 46 mm).
5. Wire SCL: B2 to B18 (straight, 41 mm).
6. Wire DT: I4 to I11 (straight, 18 mm).
7. Wire 3V3: E16 to H14 (one bend, 18 mm).
8. Wire BUZ: G9 to G15 (straight, 15 mm).
9. Wire SW: H7 to H13 (straight, 15 mm).
10. Wire CLK: J5 to J10 (straight, 13 mm).
11. Wire GND: C21 to C26 (straight, 13 mm).
12. Wire SCL: D23 to D18 (straight, 13 mm).
13. Wire SDA: B19 to B24 (straight, 13 mm).
14. Wire BZ−: H22 to H27 (straight, 13 mm).
15. Wire 3V3: A20 to A25 (straight, 13 mm).
16. Wire 3V3: C16 to C20 (straight, 10 mm).
17. Wire GND: J2 to top − rail at number 2 (straight, 9 mm).
18. Wire GND: J12 to top − rail at number 12 (straight, 9 mm).
19. Wire GND: top − rail at number 20 to J20 (straight, 9 mm).
20. Wire GND: A26 to bottom − rail at number 26 (straight, 7 mm).
21. Wire 5V: J1 to top + rail at number 1 (straight, 6 mm).
22. Wire 5V: top + rail at number 26 to J26 (straight, 6 mm).
23. Wire GATE: G21 to G19 (straight, 5 mm).
24. RG1 (220 Ω): J15 to J19, lying flat.
25. RP1 (100 kΩ): I21 to top − rail at number 21, lying flat.
26. D1 (1N4001): banded end (K) in top + rail at number 27, other end (A) in I27.
27. Q1 (BS170): D in F22, G in F21, S in F20, flat face toward the top edge (the J side).
28. U1 sockets: two 1x8 female headers in C1-C8, G1-G8. Plug U1 in while soldering to keep them square, then take it out.
29. J1 (PN532, JST-XH 4-pin): pin 1 in E21, latch side toward the top edge (the J side).
30. J2 (OLED, JST-XH 4-pin): pin 1 in E26, latch side toward the top edge (the J side).
31. J3 (encoder, JST-XH 5-pin): pin 1 in F10, latch side toward the bottom edge (the A side).
32. J4 (buzzer, JST-XH 2-pin): pin 1 in F26, latch side toward the bottom edge (the A side).
33. Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-right module.

| Step | Item | Holes |
|---|---|---|
| 1 | − rail link | right link pad, upper to right link pad, lower |
| 2 | wire 3V3 | F3 to D16 (one bend) |
| 3 | wire BUZ | F8 to F9 |
| 4 | wire SDA | A1 to A19 |
| 5 | wire SCL | B2 to B18 |
| 6 | wire DT | I4 to I11 |
| 7 | wire 3V3 | E16 to H14 (one bend) |
| 8 | wire BUZ | G9 to G15 |
| 9 | wire SW | H7 to H13 |
| 10 | wire CLK | J5 to J10 |
| 11 | wire GND | C21 to C26 |
| 12 | wire SCL | D23 to D18 |
| 13 | wire SDA | B19 to B24 |
| 14 | wire BZ− | H22 to H27 |
| 15 | wire 3V3 | A20 to A25 |
| 16 | wire 3V3 | C16 to C20 |
| 17 | wire GND | J2 to top − rail at number 2 |
| 18 | wire GND | J12 to top − rail at number 12 |
| 19 | wire GND | top − rail at number 20 to J20 |
| 20 | wire GND | A26 to bottom − rail at number 26 |
| 21 | wire 5V | J1 to top + rail at number 1 |
| 22 | wire 5V | top + rail at number 26 to J26 |
| 23 | wire GATE | G21 to G19 |
| 24 | RG1 220 Ω | J15 to J19 |
| 25 | RP1 100 kΩ | I21 to top − rail at number 21 |
| 26 | D1 1N4001 | K top + rail at number 27, A I27 |
| 27 | Q1 BS170 | D F22, G F21, S F20 |
| 28 | U1 sockets | C1-C8, G1-G8 |
| 29 | J1 PN532 | pin 1 E21, 2 E20, 3 E19, 4 E18 |
| 30 | J2 OLED | pin 1 E26, 2 E25, 3 E24, 4 E23 |
| 31 | J3 encoder | pin 1 F10, 2 F11, 3 F12, 4 F13, 5 F14 |
| 32 | J4 buzzer | pin 1 F26, 2 F27 |
