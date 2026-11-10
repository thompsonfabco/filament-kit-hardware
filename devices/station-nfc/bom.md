# Station NFC reader bill of materials

Parts to buy for the station's USB NFC reader, with Amazon listing links. The refs and use of each part are in the
[guide](guide.md); this list adds where to get them. "Reference build: yes" marks the listing used in the reference
build; "suggested" marks a listing chosen to match the part.

| Ref | Part | Qty | Brand / listing | Link | Reference build | Notes |
|---|---|---|---|---|---|---|
| U1 | Teyleten PN532 V2.0 USB NFC reader, on-board CH340E | 1 | Teyleten Robot PN532 V2.0 with mini USB | [B0DKTK9VS9](https://www.amazon.com/dp/B0DKTK9VS9) | yes | The station's external USB reader. Needs no separate adapter or jumper wires. It shows up as CH340, USB vendor `1a86` |
| U1 (alternative) | PN532 NFC module, Elechouse-style V3 | 1 | DIANN PN532 V3 kit, 1 piece (also sold as a 4-pack, [B0B7L816YS](https://www.amazon.com/dp/B0B7L816YS)) | [B0B7L47YSZ](https://www.amazon.com/dp/B0B7L47YSZ) | suggested | For the separate-adapter route. Set to HSU mode |
| U2 (alternative) | CH340 USB to serial adapter, 3.3 V logic | 1 | Maikrt CH340G USB to TTL module, 5 V / 3.3 V jumper | [B07DYS8HKS](https://www.amazon.com/dp/B07DYS8HKS) | suggested | Set its jumper to 3.3 V. Shows as USB vendor `1a86`, as the guide's checklist expects |
| U2 (alternative) | PL2303 USB to serial cable, 3.3 V logic | 1 | DTECH USB to TTL cable, PL2303, 3.3 V signals, 5 V VCC | [B0DXKF2992](https://www.amazon.com/dp/B0DXKF2992) | suggested | Ends in a 4-pin female housing, so no jumper wires are needed; wire it by its TXD, RXD, VCC and GND labels. It shows as vendor `067b`, not `1a86`. The station accepts it, because it takes any `ttyUSB` port that is not the panel's |
| W1 | Jumper wires, female to female | 4 | ELEGOO 120-piece Dupont wire kit, 20 cm (40 each M-M, M-F, F-F) | [B01EV70C78](https://www.amazon.com/dp/B01EV70C78) | suggested | For the separate-adapter route with the CH340 module |
