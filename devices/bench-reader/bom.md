# Bench reader bill of materials

Parts to buy for one bench reader, with Amazon listing links. The last three rows are for the board build only (see
"Board" in the guide); the no-board build wires the modules straight to the C3. The refs and use of each part are in the
[build guide](guide.md); this list adds where to get them. "Reference build: yes" marks the listing used in the
reference build; "suggested" marks a listing chosen to match the part. Most listings are multi-packs.

| Ref | Part | Qty | Brand / listing | Link | Reference build | Notes |
|---|---|---|---|---|---|---|
| U1 | ESP32-C3 Super Mini | 1 | Hiraethge ESP32-C3 Super Mini, 6-pack | [B0HJHW5FDL](https://www.amazon.com/dp/B0HJHW5FDL) | yes | |
| U2 | PN532 NFC module, Elechouse-style V3 | 1 | DIANN PN532 V3 kit, 1 piece (also sold as a 4-pack, [B0B7L816YS](https://www.amazon.com/dp/B0B7L816YS)) | [B0B7L47YSZ](https://www.amazon.com/dp/B0B7L47YSZ) | yes | Elechouse-style V3 board, the one photographed. Set to I2C mode |
| U3 | SSD1306 OLED, 0.96", 128x64, I2C 0x3C | 1 | Hosyond 0.96" OLED SSD1306, 5-pack | [B09T6SJBV5](https://www.amazon.com/dp/B09T6SJBV5) | yes | |
| SW1 | EC11 rotary encoder with push switch, 5 pins | 1 | WWZMDiB EC11 rotary encoder with knob caps, 6 pieces | [B0C6Q67V97](https://www.amazon.com/dp/B0C6Q67V97) | yes | A bare encoder: the switch legs are separate from the common, as the schematic shows (switch between GPIO 1 and 3V3) |
| BZ1 | Buzzer module | 1 | DIYables passive piezo buzzer module, 5 pieces | [B0DHGP95K4](https://www.amazon.com/dp/B0DHGP95K4) | yes | The listing describes a passive piezo module for 3.3 to 5 V and does not give its pin count or say whether a transistor drives it. The guide's part is a 3-pin low-level-trigger module (VCC, S, GND; S low = on): check the module before fitting it |
| J1-J4 | JST-XH headers and plugs: 4-pin x2, 5-pin x1, 3-pin x1 | 4 | GeeBat 460-piece JST-XH kit, 2- to 6-pin | [B01MCZE2HM](https://www.amazon.com/dp/B01MCZE2HM) | suggested | Board build only. The kit must include 5-pin parts for J3. Crimping needs a crimp tool, not listed here |
| U1 socket | Female pin header, 2.54 mm, cut to 8 pins | 2 | Haobase 40-pin female headers, 10 pieces | [B01DLX6RSQ](https://www.amazon.com/dp/B01DLX6RSQ) | suggested | Board build only. Cut two 8-pin lengths; a cut loses one pin. U1 plugs in and is never soldered |
| PCB | Bench reader through-hole board, 89 x 52 mm, 2 layers, 1.6 mm | 1 | Any board maker that takes Gerbers | [gerbers-tht.zip](board/gerbers-tht.zip) | suggested | Board build only. Gerbers and drill files are in the repo |
