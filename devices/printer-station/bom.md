# Printer station bill of materials

Parts to buy for one printer station, with Amazon listing links. The JST-XH row (J1-J4) and the PCB rows are
for the board build only (see "Board" in the guide). The protoboard build (see "Protoboard build") uses the ElectroCookie
board, the U1 sockets and no plugs; the no-board build wires the modules straight to the C3 and builds the buzzer driver (Q1, RG1,
RP1, D1) on a scrap of protoboard. The refs and use of each part are in the
[build guide](guide.md); this list adds where to get them. "Reference build: yes" marks the listing used in the
reference build; "suggested" marks a listing chosen to match the part. Most listings are multi-packs.

| Ref | Part | Qty | Brand / listing | Link | Reference build | Notes |
|---|---|---|---|---|---|---|
| U1 | ESP32-C3 Super Mini | 1 | Hiraethge ESP32-C3 Super Mini, 6-pack | [B0HJHW5FDL](https://www.amazon.com/dp/B0HJHW5FDL) | yes | Power-left: 5V, GND and 3V3 on the left row, seen from above with USB up, so it takes the power-left board. Any other C3 listing: check the module, which may be either hand (see "Which C3 module do I have?" in the guide) |
| BRD1 | Solderable breadboard prototype board, full size (89 x 52 mm) | 0 or 1 | ElectroCookie solderable breadboard, 5 full boards + 1 mini board | [B07ZYNWJ1S](https://www.amazon.com/dp/B07ZYNWJ1S) | suggested | Protoboard build only; the layout and hole positions in the guide are measured from it. The project standard lists same-size alternatives |
| U2 | PN532 NFC module, Elechouse-style V3 | 1 | DIANN PN532 V3 kit, 1 piece (also sold as a 4-pack, [B0B7L816YS](https://www.amazon.com/dp/B0B7L816YS)) | [B0B7L47YSZ](https://www.amazon.com/dp/B0B7L47YSZ) | yes | Elechouse-style V3 board, the one photographed. Set to I2C mode |
| U3 | SSD1306 OLED, 0.96", 128x64, I2C 0x3C | 1 | Hosyond 0.96" OLED SSD1306, 5-pack | [B09T6SJBV5](https://www.amazon.com/dp/B09T6SJBV5) | yes | |
| SW1 | EC11 rotary encoder with push switch, 5 pins | 1 | WWZMDiB EC11 rotary encoder with knob caps, 6 pieces | [B0C6Q67V97](https://www.amazon.com/dp/B0C6Q67V97) | yes | A bare encoder: the switch legs are separate from the common, as the schematic shows (switch between GPIO 1 and 3V3) |
| BZ1 | 12085 magnetic passive buzzer, 12 x 8.5 mm, 42 Ω coil, 2 leads | 1 | UMLIFE 12085 passive buzzer, 20 pieces ("20Pcs 12085 Passive Buzzer 12MM*8.5MM 42R Resistance 3V 5V 9V 12V") | [B0F1KFHSNK](https://www.amazon.com/dp/B0F1KFHSNK) | yes | Off the board, on J4. The title gives 42 Ω and 3 to 12 V; the bullets also say "3-5V input" and "Active Buzzer", which do not fit a 42 Ω passive part: the 42 Ω coil is what the design relies on, so measure it (about 42 Ω) before fitting. Mind the + mark: + goes to 5V |
| Q1 | BS170 N-MOSFET, TO-92 | 1 | Fairchild BS170, 10 pieces | [B00MMY1WTK](https://www.amazon.com/dp/B00MMY1WTK) | yes | The intake panel's listing. Legs D G S, flat face toward you. If the buzzer is weak, see "Buzzer driver" in the guide |
| RG1, RP1 | 220 Ω and 100 kΩ resistors, 1/4 W | 1 + 1 | Joe Knows Electronics 1/4 W 1% metal film kit, 86 E12 values, 10 of each | [B003UC4FSS](https://www.amazon.com/dp/B003UC4FSS) | yes | The intake panel's listing. 220 Ω gate resistor, 100 kΩ gate pull-down |
| D1 | 1N4001 rectifier diode, 50 V, 1 A, DO-41 | 1 | BOJACK 1N4001, pack of 125 | [B07Q3HBM63](https://www.amazon.com/dp/B07Q3HBM63) | suggested | Flyback diode across the buzzer. The band marks the cathode, which goes to 5V. Any 1N4001 to 1N4007 fits |
| J1-J4 | JST-XH headers and plugs: 4-pin x2, 5-pin x1, 2-pin x1 | 0 or 4 | GeeBat 460-piece JST-XH kit, 2- to 6-pin | [B01MCZE2HM](https://www.amazon.com/dp/B01MCZE2HM) | suggested | Board build only: the protoboard build uses no plugs and solders the device wires into the board. The kit must include 5-pin parts for J3. Crimping needs a crimp tool, not listed here |
| U1 socket | Female pin header, 2.54 mm, cut to 8 pins | 0 or 2 | Haobase 40-pin female headers, 10 pieces | [B01DLX6RSQ](https://www.amazon.com/dp/B01DLX6RSQ) | suggested | Board and protoboard builds; not the no-board build. Cut two 8-pin lengths; a cut loses one pin. U1 plugs in and is never soldered |
| PCB, power-left | Printer station through-hole board, C3 POWER-LEFT, 89 x 52 mm, 2 layers, 1.6 mm | 0 or 1 | Any board maker that takes Gerbers | [gerbers-tht-power-left.zip](board/gerbers-tht-power-left.zip) | suggested | Board build with a power-left C3 (the Hiraethge modules above). Order it bare from JLCPCB or any board maker (see "Board" in the guide) |
| PCB, power-right | Printer station through-hole board, C3 POWER-RIGHT, 89 x 52 mm, 2 layers, 1.6 mm | 0 or 1 | Any board maker that takes Gerbers | [gerbers-tht-power-right.zip](board/gerbers-tht-power-right.zip) | suggested | Board build with a power-right C3 only: 5V, GND and 3V3 on the right row, seen from above with USB up. Order one PCB row, not both |

## Ordering from JLCPCB

The printer station board has no surface-mount parts, so JLCPCB has nothing to assemble: order the board for your
C3's hand, [gerbers-tht-power-left.zip](board/gerbers-tht-power-left.zip) or
[gerbers-tht-power-right.zip](board/gerbers-tht-power-right.zip), bare from JLCPCB or any board maker, and fit the headers yourself (see
"Board" in the [build guide](guide.md)). The rows above cover every part. If you would rather buy the headers from
LCSC with the board, as loose parts, these are the matching part numbers; search a number in JLCPCB's parts library to
see the part. Stock is JLCPCB's figure from its October 2026 parts list and changes daily.

| Ref | Part | Qty | Maker part number | LCSC | Type | Stock (Oct 2026) |
|---|---|---|---|---|---|---|
| J1, J2 | JST-XH header, 4-pin, vertical, through-hole | 2 | JST B4B-XH-A(LF)(SN) | C144395 | Extended | 478,892 |
| J3 | JST-XH header, 5-pin, vertical, through-hole | 1 | JST B5B-XH-A(LF)(SN) | C157991 | Extended | 42,371 |
| J4 | JST-XH header, 2-pin, vertical, through-hole | 1 | JST B2B-XH-A(LF)(SN) | C158012 | Extended | 241,293 |
| U1A, U1B | Female header, 1x8, 2.54 mm, socket for U1 | 2 | BOOMELE 2.54-1*8P | C27438 | Extended | 104,134 |
