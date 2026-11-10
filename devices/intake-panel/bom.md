# Intake panel bill of materials

Parts to buy for one intake panel, with Amazon listing links. The refs, values and use of each part are in the
[build guide](guide.md); this list adds where to get them. "Reference build: yes" marks a listing used in a
reference build (more than one row may be marked for the same part); "suggested" marks a listing chosen to match the part. Most listings are multi-packs, so one pack
covers the quantity shown.

| Ref | Part | Qty | Brand / listing | Link | Reference build | Notes |
|---|---|---|---|---|---|---|
| BRD1 | Solderable breadboard prototype board, full size (89 x 52 mm) | 1 | ElectroCookie solderable breadboard, 5 full boards + 1 mini board | [B07ZYNWJ1S](https://www.amazon.com/dp/B07ZYNWJ1S) | suggested | The board the layout and hole positions in the guide are measured from |
| U1 | ESP32-C3 Super Mini | 1 | Hiraethge ESP32-C3 Super Mini, 6-pack | [B0HJHW5FDL](https://www.amazon.com/dp/B0HJHW5FDL) | yes | |
| Q1, Q2 | BS170 N-MOSFET, TO-92 | 2 | Fairchild BS170, 10 pieces | [B00MMY1WTK](https://www.amazon.com/dp/B00MMY1WTK) | yes | Legs D G S, flat face toward you |
| Q1, Q2 (alternative) | 2N7000 N-MOSFET, TO-92, 60 V, 200 mA | 2 | BOJACK 2N7000, pack of 100 | [B0831RFJ1B](https://www.amazon.com/dp/B0831RFJ1B) | suggested | Instead of the BS170. Pins mirrored: S G D against the BS170's D G S, so fit it turned round or swap the drain and source wires (see "LED MOSFET stages" in the guide) |
| RG1, RG2, RP1, RP2, RI1, RI2 | 220 Ω, 100 kΩ and 4.7 kΩ resistors, 1/4 W | 2 + 2 + 0 or 2 | Joe Knows Electronics 1/4 W 1% metal film kit, 86 E12 values, 10 of each | [B003UC4FSS](https://www.amazon.com/dp/B003UC4FSS) | yes | 220 Ω gate resistors, 100 kΩ gate pull-downs, 4.7 kΩ I2C pull-ups only if no I2C board has them |
| RSD | 10 kΩ resistor, 1/4 W | 0 or 1 | E-Projects 10 kΩ 1/4 W 5% carbon film, pack of 1000 | [B01M15SOWK](https://www.amazon.com/dp/B01M15SOWK) | yes | Through-hole board only, and only if the amplifier's SD reads near 0 V; the kit above also has 10 kΩ |
| U2 | MAX98357 I2S amplifier module, "No Welding" | 0 or 1 | AITRIP MAX98357, 3-pack | [B0912CWB7Z](https://www.amazon.com/dp/B0912CWB7Z) | yes | Not for the JLCPCB board, which carries the amplifier chip |
| LS1 | Speaker, 8 Ω, 3 W rated, sealed double cavity | 1 | Shutao 8 Ω double-cavity mini speaker, 2-pack | [B0DL9SFH49](https://www.amazon.com/dp/B0DL9SFH49) | yes | The listing gives 3 W rated, 5 W maximum. Cut off its JST-PH plug: the bare lead goes into the amplifier's screw terminal, or on the JLCPCB board into a JST-XH 2-pin plug for J6 |
| U3 | SSD1306 OLED, 0.96", 128x64, I2C 0x3C | 1 | Hosyond 0.96" OLED SSD1306, 5-pack | [B09T6SJBV5](https://www.amazon.com/dp/B09T6SJBV5) | yes | |
| U4 | BMP280 board, 6 pins (VCC GND SCL SDA CSB SDO) | 1 | HiLetgo BMP280-3.3, 5 pieces | [B07VNDZ6N4](https://www.amazon.com/dp/B07VNDZ6N4) | yes | Room air, option A: temperature and pressure. Option B (U5 + U6) is optional and not in this BOM |
| U7 | PN532 NFC module, Elechouse-style V3 | 0 or 1 | DIANN PN532 V3 kit, 1 piece (also sold as a 4-pack, [B0B7L816YS](https://www.amazon.com/dp/B0B7L816YS)) | [B0B7L47YSZ](https://www.amazon.com/dp/B0B7L47YSZ) | yes | Elechouse-style V3 board, the one photographed. Optional panel reader. Set to I2C mode |
| BZ1 | Buzzer module | 1 | DIYables passive piezo buzzer module, 5 pieces | [B0DHGP95K4](https://www.amazon.com/dp/B0DHGP95K4) | yes | The listing describes a passive piezo module for 3.3 to 5 V and does not give its pin count or say whether a transistor drives it. The guide's part is a 3-pin low-level-trigger module (VCC, I/O, GND; I/O low = on): check the module before fitting it |
| SW1, SW2 | Illuminated push button, normally open, built-in 5 V LED, yellow and red | 2 | EG Starts 30 mm arcade LED push buttons, 5 V, one each of 5 colours | [B01N11BDX9](https://www.amazon.com/dp/B01N11BDX9) | yes | Use the yellow and the red. Each 5 V LED has its resistor built in, and that is the LED's series resistor: the board adds none. The listing states only "5V", so measure each LED as the bench checklist says (10 to 20 mA expected, 50 mA at most). Needs a 30 mm mounting hole |
| XU1 | Female pin header, 2.54 mm, cut to 8 pins | 2 | Haobase 40-pin female headers, 10 pieces | [B01DLX6RSQ](https://www.amazon.com/dp/B01DLX6RSQ) | yes | Cut two 8-pin lengths; a cut loses one pin |
| XU2 | Female pin header, 2.54 mm, cut to 7 pins | 0 or 1 | Same listing as XU1 | [B01DLX6RSQ](https://www.amazon.com/dp/B01DLX6RSQ) | suggested | Through-hole board only: the socket for U2. Cut one 7-pin length from the same strips |
| J1-J7 | JST-XH headers and plugs: 4-pin x5 (J7 only if U7 is fitted), 3-pin x1, 2-pin x1 (J6, JLCPCB board only) | 5 to 7 | CQRobot JST-XH kit, 2-, 3- and 4-pin headers, housings and crimp terminals | [B0731NHS9R](https://www.amazon.com/dp/B0731NHS9R) | yes | The listing says 2.54 mm; JST-XH is 2.50 mm pitch and fits a 0.1" board. Crimping needs a crimp tool, not listed here |
| J1-J7 (alternative) | JST-XH headers and plugs | 5 to 7 | GeeBat 460-piece JST-XH kit, 2- to 6-pin | [B01MCZE2HM](https://www.amazon.com/dp/B01MCZE2HM) | yes | Same use as the row above |
| F1, F2 | Wire ferrules for the speaker leads | 0 or 2 | cnaodun 800-piece insulated ferrule kit, AWG 22-7 | [B09WMNTVSH](https://www.amazon.com/dp/B09WMNTVSH) | suggested | Through-hole board only. Use the smallest size that grips the speaker wire; needs a ferrule crimper |
| PCB | Intake panel through-hole board, 89 x 52 mm, 2 layers, 1.6 mm | 0 or 1 | Any board maker that takes Gerbers | [gerbers-tht.zip](board/gerbers-tht.zip) | suggested | Instead of BRD1, the ElectroCookie board. Gerbers and drill files are in the repo; see "Board" in the guide. For the JLCPCB assembly board instead, see below |
| C1 | 470 µF electrolytic, 16 V | 0 or 1 | E-Projects 470 µF 16 V 105 °C radial, 5-pack | [B07YN5MZBY](https://www.amazon.com/dp/B07YN5MZBY) | suggested | Only if 5 V sags on speech peaks: + to the amplifier's VIN, - to GND |

## JLCPCB assembly board

The parts JLCPCB fits to the JLCPCB assembly board (see "Board" in the [build guide](guide.md)), with their LCSC
part numbers; search a number in JLCPCB's parts library to see the part. The same rows are in
[board/jlcpcb-bom-smt.csv](board/jlcpcb-bom-smt.csv). JLCPCB fits surface-mount parts only. The board replaces the
PCB, Q1, Q2, the resistors and the amplifier module U2 in the list above; the end user fits the through-hole headers
(XU1, J1-J7) from that list, and the other modules, U1, the buttons, the speaker and the harness parts still come from
it too. U2 is the only extended part, so the order pays one extended-part fee. Stock is
JLCPCB's figure from its October 2026 parts list and changes daily; check it when ordering.

| Ref | Part | Qty | Maker part number | LCSC | Type | Stock (Oct 2026) |
|---|---|---|---|---|---|---|
| Q1, Q2 | AO3400A N-MOSFET, SOT-23, logic-level, in place of the BS170 (see "LED MOSFET stages" in the guide) | 2 | Alpha & Omega AO3400A | C20917 | Basic | 757,862 |
| RG1, RG2 | 220 Ω resistor, 1%, 0603 | 2 | UNI-ROYAL 0603WAF2200T5E | C22962 | Basic | 2,050,208 |
| RP1, RP2 | 100 kΩ resistor, 1%, 0603 | 2 | UNI-ROYAL 0603WAF1003T5E | C25803 | Basic | 19,748,113 |
| U2 | MAX98357A I2S class-D amplifier, TQFN-16 3 x 3 mm (see "MAX98357A chip on the JLCPCB board" in the guide) | 1 | Analog Devices (Maxim) MAX98357AETE+T | C910544 | Extended | 22,133 |
| RSD2 | 1 MΩ resistor, 1%, 0603, SD_MODE pull-up | 1 | UNI-ROYAL 0603WAF1004T5E | C22935 | Basic | 5,647,551 |
| C2 | 100 nF capacitor, 50 V X7R, 0603, VDD bypass | 1 | YAGEO CC0603KRX7R9BB104 | C14663 | Basic | 50,349,394 |
| C3 | 10 µF capacitor, 25 V X5R, 0805, VDD bypass | 1 | Samsung Electro-Mechanics, 0805 X5R | C15850 | Basic | 3,710,191 |
| PCB | Intake panel JLCPCB assembly board, 89 x 52 mm, 2 layers, 1.6 mm, from [gerbers-smt.zip](board/gerbers-smt.zip) | 1 | - | - | - | - |

JLCPCB leaves the parts below off the board, as the through-hole board does (see "Parts fitted only when needed" in
the guide). Each fits the board's surface-mount pads; order it with the board as a loose part, or buy it later, only
if a bench check calls for it.

| Ref | Part | Qty | Maker part number | LCSC | Type | Stock (Oct 2026) |
|---|---|---|---|---|---|---|
| RSD1 | 10 kΩ resistor, 1%, 0603 | 0 or 1 | UNI-ROYAL 0603WAF1002T5E | C25804 | Basic | 32,380,385 |
| RI1, RI2 | 4.7 kΩ resistor, 1%, 0603 | 0 or 2 | UNI-ROYAL 0603WAF4701T5E | C23162 | Basic | 19,500,720 |
| C1 | 470 µF 10 V aluminium electrolytic, SMD, 6.3 x 7.7 mm | 0 or 1 | ROQANG RVT1A471M0607 | C335982 | Extended | 404,316 |
| Q1, Q2 (alternative) | 2N7002 N-MOSFET, SOT-23; same pads as the AO3400A | 0 or 2 | Changjing 2N7002 | C8545 | Basic | 1,830,508 |

The 2N7002 row is not a bench-check part: it is a stand-in for the AO3400A in the BOM, for when the AO3400A is out of
stock. It is not specified at a 3.3 V gate, so each LED then needs both checks in the guide's "LED MOSFET stages" section.

The end user fits the through-hole headers on the JLCPCB board, from the main list. The same headers are in
JLCPCB's parts library, to order with the board as loose parts if you prefer:

| Ref | Part | Qty | Maker part number | LCSC | Type | Stock (Oct 2026) |
|---|---|---|---|---|---|---|
| J1-J4, J7 | JST-XH header, 4-pin, vertical, through-hole | 4 or 5 | JST B4B-XH-A(LF)(SN) | C144395 | Extended | 478,892 |
| J5 | JST-XH header, 3-pin, vertical, through-hole | 1 | JST B3B-XH-A(LF)(SN) | C144394 | Extended | 152,263 |
| J6 | JST-XH header, 2-pin, vertical, through-hole, speaker | 1 | JST B2B-XH-A(LF)(SN) | C158012 | Extended | 241,293 |
| XU1 | Female header, 1x8, 2.54 mm, through-hole, socket for U1 | 2 | BOOMELE 2.54-1*8P | C27438 | Extended | 104,134 |
