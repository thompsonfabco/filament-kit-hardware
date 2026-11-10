# Station NFC reader guide (PN532 on a CH340 adapter)

The station reads a spool's NFC tag with a PN532 board. The board is a bought part and has no kit firmware: it
connects to the station PC through a CH340 USB serial adapter, and the station talks to it with nfcpy. This guide
covers the mode switches, the wiring to the adapter and the checks. The checked data is in
[catalogue.xml](catalogue.xml). The station's behaviour is in the kit's user guide, in the station hardware section.

## Parts

| Ref | Part | Qty | Use |
|---|---|---|---|
| U1 | PN532 NFC reader board with mode switches | 1 | Tag reader |
| U2 | CH340 USB to serial adapter with 3.3 V logic | 1 | USB link to the station PC |
| W1 | Female to female jumper wires | 4 | Adapter to board |

The datasheet limits of U1 and U2 are UNCONFIRMED in [catalogue.xml](catalogue.xml): no source was read for them.
Both are bus-powered from the station PC's USB 5 V.

## PN532 mode switches (HSU)

The PN532 board picks its interface from two switches, usually labelled SEL0 and SEL1 or I0 and I1. Set them for
HSU, the high-speed UART:

| Switch | Setting |
|---|---|
| SEL0 (I0) | OFF (0) |
| SEL1 (I1) | OFF (0) |

This is the setting on common boards, but it is UNCONFIRMED for yours: check the table printed on its silkscreen,
because boards label the positions differently. Set the switches with the board unpowered. Record the positions in
the bench results.

## Wiring to the adapter

TX and RX cross: the adapter's TX goes to the board's RX, and the adapter's RX goes to the board's TX.

| Adapter | PN532 board |
|---|---|
| GND | GND |
| 5V or 3V3 (the supply the board's label asks for) | VCC |
| TX | RX |
| RX | TX |

Use the adapter's 3.3 V logic setting if it has a jumper for it. No other signal wire is needed. If the reader never
opens, swap TX and RX first.

## How the station finds it

The station opens the first `ttyUSB` port that the intake panel isn't on (`nfc_path` in the kit's
`server/filament_kit/station/nfc.py`). It does not check the USB vendor. With this adapter that port is the CH340's (vendor `1a86`), but
any other `ttyUSB` adapter would be taken the same way. The panel is an ESP32-C3 on a native USB port, so it doesn't appear as a `ttyUSB` port. To pin a port, set
`NFC_DEVICE` to an nfcpy path such as `tty:USB0:pn532`.

## Baud rate and the 921600 wedge

The PN532 keeps its UART speed until it loses power. nfcpy opens it at 115200, moves it to 921600 baud, and sets it
back to 115200 when it closes. If the station stops without that close, the reader stays at 921600 and every later
open at 115200 times out (Errno 110). The station now closes nfcpy first when it is stopped, and if an open fails with a timeout (`ETIMEDOUT`) or a missing device (`ENODEV`) it
tries 921600, 460800, 230400 and 115200 to set the chip back (`pn532_unwedge` in the kit's `server/filament_kit/station/nfc.py`). Any
other open error is only logged and retried after 5 seconds. If a reader still won't open, unplug and replug the
adapter, which cuts the board's power.

## Bench checklist

- [ ] SEL0 and SEL1 set for HSU, with the board unpowered.
- [ ] TX and RX crossed, and GND and power connected.
- [ ] The adapter appears as a `ttyUSB` port, and `lsusb` shows vendor `1a86`.
- [ ] The station log says "NFC reader open".
- [ ] A tag tap starts the intake flow, and the tag id matches the one in Spoolman.
- [ ] After a restart of the station service, the reader opens again without being unplugged.
- [ ] Supply current measured and recorded (UNCONFIRMED until measured).

## Bench results

| Date | Result | Measured mA | Notes |
|---|---|---|---|
| | | | |
