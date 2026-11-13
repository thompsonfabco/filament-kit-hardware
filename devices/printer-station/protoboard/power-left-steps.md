Build order (lowest parts first; the numbers on the wires in the top view are these step numbers):

1. Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
2. Wire 3V3: E3 to G19 (one bend, 51 mm).
3. Wire CLK: E5 to F15 (one bend, 33 mm).
4. Wire BUZ: E8 to E9 (straight, 3 mm).
5. Wire SCL: I2 to I21 (straight, 48 mm).
6. Wire SDA: J1 to J17 (straight, 41 mm).
7. Wire DT: C4 to C13 (straight, 23 mm).
8. Wire 3V3: B3 to B10 (straight, 18 mm).
9. Wire BUZ: D9 to D15 (straight, 15 mm).
10. Wire BZ−: C20 to C26 (straight, 15 mm).
11. Wire CLK: H15 to E16 (one bend, 15 mm).
12. Wire SCL: H21 to H26 (straight, 13 mm).
13. Wire 3V3: J19 to J24 (straight, 13 mm).
14. Wire SDA: G20 to G25 (straight, 13 mm).
15. Wire GND: I23 to top − rail at number 23 (straight, 11 mm).
16. Wire SW: A7 to A11 (straight, 10 mm).
17. Wire 5V: A1 to bottom + rail at number 1 (straight, 9 mm).
18. Wire 5V: bottom + rail at number 27 to A27 (straight, 9 mm).
19. Wire GND: J18 to top − rail at number 18 (straight, 9 mm).
20. Wire BZ−: B29 to B26 (straight, 8 mm).
21. Wire SDA: H17 to H20 (straight, 8 mm).
22. Wire GND: A2 to bottom − rail at number 2 (straight, 7 mm).
23. Wire GND: A12 to bottom − rail at number 12 (straight, 7 mm).
24. Wire GND: bottom − rail at number 22 to A22 (straight, 7 mm).
25. Wire GATE: D21 to D19 (straight, 5 mm).
26. Wire CLK: C14 to C16 (straight, 5 mm).
27. RG1 (220 Ω): A15 to A19, lying flat.
28. RP1 (100 kΩ): B21 to bottom − rail at number 21, lying flat.
29. D1 (1N4001): banded end (K) in bottom + rail at number 29, other end (A) in A29.
30. Q1 (BS170): D in E20, G in E21, S in E22, flat face toward the bottom edge (the A side).
31. U1 sockets: two 1x8 female headers in D1-D8, H1-H8. Plug U1 in while soldering to keep them square, then take it out.
32. J1 (PN532, JST-XH 4-pin): pin 1 in F18, latch side toward the bottom edge (the A side).
33. J2 (OLED, JST-XH 4-pin): pin 1 in F23, latch side toward the bottom edge (the A side).
34. J3 (encoder, JST-XH 5-pin): pin 1 in E14, latch side toward the top edge (the J side).
35. J4 (buzzer, JST-XH 2-pin): pin 1 in E27, latch side toward the top edge (the J side).
36. Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-left module.

| Step | Item | Holes |
|---|---|---|
| 1 | − rail link | right link pad, upper to right link pad, lower |
| 2 | wire 3V3 | E3 to G19 (one bend) |
| 3 | wire CLK | E5 to F15 (one bend) |
| 4 | wire BUZ | E8 to E9 |
| 5 | wire SCL | I2 to I21 |
| 6 | wire SDA | J1 to J17 |
| 7 | wire DT | C4 to C13 |
| 8 | wire 3V3 | B3 to B10 |
| 9 | wire BUZ | D9 to D15 |
| 10 | wire BZ− | C20 to C26 |
| 11 | wire CLK | H15 to E16 (one bend) |
| 12 | wire SCL | H21 to H26 |
| 13 | wire 3V3 | J19 to J24 |
| 14 | wire SDA | G20 to G25 |
| 15 | wire GND | I23 to top − rail at number 23 |
| 16 | wire SW | A7 to A11 |
| 17 | wire 5V | A1 to bottom + rail at number 1 |
| 18 | wire 5V | bottom + rail at number 27 to A27 |
| 19 | wire GND | J18 to top − rail at number 18 |
| 20 | wire BZ− | B29 to B26 |
| 21 | wire SDA | H17 to H20 |
| 22 | wire GND | A2 to bottom − rail at number 2 |
| 23 | wire GND | A12 to bottom − rail at number 12 |
| 24 | wire GND | bottom − rail at number 22 to A22 |
| 25 | wire GATE | D21 to D19 |
| 26 | wire CLK | C14 to C16 |
| 27 | RG1 220 Ω | A15 to A19 |
| 28 | RP1 100 kΩ | B21 to bottom − rail at number 21 |
| 29 | D1 1N4001 | K bottom + rail at number 29, A A29 |
| 30 | Q1 BS170 | D E20, G E21, S E22 |
| 31 | U1 sockets | D1-D8, H1-H8 |
| 32 | J1 PN532 | pin 1 F18, 2 F19, 3 F20, 4 F21 |
| 33 | J2 OLED | pin 1 F23, 2 F24, 3 F25, 4 F26 |
| 34 | J3 encoder | pin 1 E14, 2 E13, 3 E12, 4 E11, 5 E10 |
| 35 | J4 buzzer | pin 1 E27, 2 E26 |
