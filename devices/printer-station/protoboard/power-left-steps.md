Build order (lowest parts first; the numbers on the wires in the top view are these step numbers):

1. Rail link (+): wire from the left link pad, upper to the left link pad, lower. It joins the top and bottom + rails.
2. Rail link (−): wire from the right link pad, upper to the right link pad, lower. It joins the top and bottom − rails.
3. Wire SW: H19 to E8 (one bend, 41 mm).
4. Wire DT: G22 to E10 (one bend, 41 mm).
5. Wire CLK: F21 to E11 (one bend, 33 mm).
6. Wire 3V3: G23 to G26 (straight, 8 mm).
7. Wire 3V3: F26 to E26 (straight, 8 mm).
8. Wire 3V3: B26 to B14 (straight, 30 mm).
9. Wire GATE: I14 to I4 (straight, 25 mm).
10. Wire SDA: C25 to C15 (straight, 25 mm).
11. Wire SCL: D24 to D16 (straight, 20 mm).
12. Wire 3V3: D14 to D7 (straight, 18 mm).
13. Wire 5V: A4 to bottom + rail, column 4 (straight, 9 mm).
14. Wire GND: J24 to top − rail, column 24 (straight, 9 mm).
15. Wire GND: J27 to top − rail, column 27 (straight, 9 mm).
16. Wire GND: J3 to top − rail, column 3 (straight, 9 mm).
17. Wire GND: F27 to E27 (straight, 8 mm).
18. Wire BZ−: F5 to E5 (straight, 8 mm).
19. Wire GND: A13 to bottom − rail, column 13 (straight, 7 mm).
20. Wire GND: A9 to bottom − rail, column 9 (straight, 7 mm).
21. Wire 5V: J25 to top + rail, column 25 (straight, 6 mm).
22. RG1 (220 Ω): J18 to J14, lying flat.
23. RP1 (100 kΩ): J4 to top − rail, column 4, lying flat.
24. D1 (1N4001): banded end (K) in bottom + rail, column 5, other end (A) in A5.
25. Q1 (BS170): D in H5, G in H4, S in H3, flat face toward the top edge (row J side).
26. U1 sockets: two 1x8 female headers in E18-E25, I18-I25. Plug U1 in while soldering to keep them square, then take it out.
27. J1 (PN532, JST-XH 4-pin): pin 1 in A27, latch side toward the bottom edge (row A side).
28. J2 (OLED, JST-XH 4-pin): pin 1 in E13, latch side toward the top edge (row J side).
29. J3 (encoder, JST-XH 5-pin): pin 1 in B11, latch side toward the top edge (row J side).
30. J4 (buzzer, JST-XH 2-pin): pin 1 in C4, latch side toward the top edge (row J side).
31. Check with a meter: no short from 5V, 3V3 or SDA/SCL to GND. Then plug U1 in, USB-C toward the board edge as drawn, after checking it is a power-left module.

| Step | Item | Holes |
|---|---|---|
| 1 | + rail link | left link pad, upper to left link pad, lower |
| 2 | − rail link | right link pad, upper to right link pad, lower |
| 3 | wire SW | H19 to E8 (one bend) |
| 4 | wire DT | G22 to E10 (one bend) |
| 5 | wire CLK | F21 to E11 (one bend) |
| 6 | wire 3V3 | G23 to G26 |
| 7 | wire 3V3 | F26 to E26 |
| 8 | wire 3V3 | B26 to B14 |
| 9 | wire GATE | I14 to I4 |
| 10 | wire SDA | C25 to C15 |
| 11 | wire SCL | D24 to D16 |
| 12 | wire 3V3 | D14 to D7 |
| 13 | wire 5V | A4 to bottom + rail, column 4 |
| 14 | wire GND | J24 to top − rail, column 24 |
| 15 | wire GND | J27 to top − rail, column 27 |
| 16 | wire GND | J3 to top − rail, column 3 |
| 17 | wire GND | F27 to E27 |
| 18 | wire BZ− | F5 to E5 |
| 19 | wire GND | A13 to bottom − rail, column 13 |
| 20 | wire GND | A9 to bottom − rail, column 9 |
| 21 | wire 5V | J25 to top + rail, column 25 |
| 22 | RG1 220 Ω | J18 to J14 |
| 23 | RP1 100 kΩ | J4 to top − rail, column 4 |
| 24 | D1 1N4001 | K bottom + rail, column 5, A A5 |
| 25 | Q1 BS170 | D H5, G H4, S H3 |
| 26 | U1 sockets | E18-E25, I18-I25 |
| 27 | J1 PN532 | pin 1 A27, 2 A26, 3 A25, 4 A24 |
| 28 | J2 OLED | pin 1 E13, 2 E14, 3 E15, 4 E16 |
| 29 | J3 encoder | pin 1 B11, 2 B10, 3 B9, 4 B8, 5 B7 |
| 30 | J4 buzzer | pin 1 C4, 2 C5 |
