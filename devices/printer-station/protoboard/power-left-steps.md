Build order (lowest parts first; the numbers on the wires in the top view are these step numbers):

1. Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
2. Wire 3V3: E3 to G16 (one bend, 43 mm).
3. Wire BUZ: E8 to E9 (straight, 3 mm).
4. Wire SDA: J1 to J19 (straight, 46 mm).
5. Wire SCL: I2 to I18 (straight, 41 mm).
6. Wire DT: B4 to B11 (straight, 18 mm).
7. Wire 3V3: F16 to C14 (one bend, 18 mm).
8. Wire BUZ: D9 to D15 (straight, 15 mm).
9. Wire BZ−: C20 to C26 (straight, 15 mm).
10. Wire SW: C7 to C13 (straight, 15 mm).
11. Wire CLK: A5 to A10 (straight, 13 mm).
12. Wire GND: H21 to H26 (straight, 13 mm).
13. Wire SCL: G18 to G23 (straight, 13 mm).
14. Wire SDA: I19 to I24 (straight, 13 mm).
15. Wire 3V3: J20 to J25 (straight, 13 mm).
16. Wire 3V3: H16 to H20 (straight, 10 mm).
17. Wire 5V: A1 to bottom + rail at number 1 (straight, 9 mm).
18. Wire 5V: bottom + rail at number 27 to A27 (straight, 9 mm).
19. Wire GND: J26 to top − rail at number 26 (straight, 9 mm).
20. Wire BZ−: B29 to B26 (straight, 8 mm).
21. Wire GND: A2 to bottom − rail at number 2 (straight, 7 mm).
22. Wire GND: A12 to bottom − rail at number 12 (straight, 7 mm).
23. Wire GND: bottom − rail at number 22 to A22 (straight, 7 mm).
24. Wire GATE: D21 to D19 (straight, 5 mm).
25. RG1 (220 Ω): A15 to A19, lying flat.
26. RP1 (100 kΩ): B21 to bottom − rail at number 21, lying flat.
27. D1 (1N4001): banded end (K) in bottom + rail at number 29, other end (A) in A29.
28. Q1 (BS170): D in E20, G in E21, S in E22, flat face toward the bottom edge (the A side).
29. U1 sockets: two 1x8 female headers in D1-D8, H1-H8. Plug U1 in while soldering to keep them square, then take it out.
30. J1 (PN532, JST-XH 4-pin): pin 1 in F21, latch side toward the bottom edge (the A side).
31. J2 (OLED, JST-XH 4-pin): pin 1 in F26, latch side toward the bottom edge (the A side).
32. J3 (encoder, JST-XH 5-pin): pin 1 in E10, latch side toward the top edge (the J side).
33. J4 (buzzer, JST-XH 2-pin): pin 1 in E27, latch side toward the bottom edge (the A side).
34. Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-left module.

| Step | Item | Holes |
|---|---|---|
| 1 | − rail link | right link pad, upper to right link pad, lower |
| 2 | wire 3V3 | E3 to G16 (one bend) |
| 3 | wire BUZ | E8 to E9 |
| 4 | wire SDA | J1 to J19 |
| 5 | wire SCL | I2 to I18 |
| 6 | wire DT | B4 to B11 |
| 7 | wire 3V3 | F16 to C14 (one bend) |
| 8 | wire BUZ | D9 to D15 |
| 9 | wire BZ− | C20 to C26 |
| 10 | wire SW | C7 to C13 |
| 11 | wire CLK | A5 to A10 |
| 12 | wire GND | H21 to H26 |
| 13 | wire SCL | G18 to G23 |
| 14 | wire SDA | I19 to I24 |
| 15 | wire 3V3 | J20 to J25 |
| 16 | wire 3V3 | H16 to H20 |
| 17 | wire 5V | A1 to bottom + rail at number 1 |
| 18 | wire 5V | bottom + rail at number 27 to A27 |
| 19 | wire GND | J26 to top − rail at number 26 |
| 20 | wire BZ− | B29 to B26 |
| 21 | wire GND | A2 to bottom − rail at number 2 |
| 22 | wire GND | A12 to bottom − rail at number 12 |
| 23 | wire GND | bottom − rail at number 22 to A22 |
| 24 | wire GATE | D21 to D19 |
| 25 | RG1 220 Ω | A15 to A19 |
| 26 | RP1 100 kΩ | B21 to bottom − rail at number 21 |
| 27 | D1 1N4001 | K bottom + rail at number 29, A A29 |
| 28 | Q1 BS170 | D E20, G E21, S E22 |
| 29 | U1 sockets | D1-D8, H1-H8 |
| 30 | J1 PN532 | pin 1 F21, 2 F20, 3 F19, 4 F18 |
| 31 | J2 OLED | pin 1 F26, 2 F25, 3 F24, 4 F23 |
| 32 | J3 encoder | pin 1 E10, 2 E11, 3 E12, 4 E13, 5 E14 |
| 33 | J4 buzzer | pin 1 E27, 2 E26 |
