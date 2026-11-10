# Peripheral hardware standard

### Board

New kit-built peripherals use the **ESP32-C3 Super Mini** on the same pinned platform as the reader: pioarduino
53.03.13 (Arduino core 3.1.3), native USB serial. Bought devices such as the scale and webcam are exempt.

### Bought devices

- **Scale:** the intake station uses the DYMO M10, the DYMO Digital Postal Scale, 10-Pound (model 1772057, Amazon
  ASIN B0053HCWRE). Other DYMO USB postal scales share its USB vendor ID but are untested.

Pin rules:

- Use GPIO 5 and 6 for I2C SDA and SCL on every device, as the reader does.
- Use GPIO 0 for the buzzer on every device, as the reader does.
- Avoid the strapping pins GPIO 2, 8 and 9. GPIO 8 also drives the board's LED and GPIO 9 the BOOT button.
- Leave GPIO 18 and 19 alone. They are the USB pair.
- Every firmware keeps its pins in one block of named constants at the top of one source file.

### Power

- Power comes from the host's USB 5 V. A device's measured total stays at or under 500 mA, the USB 2.0 limit.
- Logic is 3.3 V. I2C parts run from 3V3.
- A load a GPIO pin can't drive directly goes through an N-MOSFET with a 220 Ω gate resistor and a 100 kΩ gate
  pull-down, so it stays off during reset. This is the panel's existing stage.

### Audio

A kit-built device with a speaker uses a MAX98357 I2S amplifier breakout board, powered from 5 V, and one sealed 8 Ω
speaker rated at 3 W or more. Speaker wires go only to the board's two outputs, because neither output is a ground. The
bench reader's speech through its buzzer is exempt.

### Connectors

Parts off the main board plug in through JST-XH connectors (2.50 mm pitch; they fit a 0.1" board). I2C always uses the pin order GND, 3V3, SDA, SCL.
Each connector is listed in the device's catalogue file.

- Every header carries a label on the board naming its function (for example I2C, YELLOW, RED, BUZZER), and the guide
  shows how to find pin 1 on a header and on a plug. The builder plugs each harness into its labelled header.

The one exception to the JST-XH rule is the speaker, which goes into the amplifier board's screw terminal. This rule
applies when a device is next built or rebuilt. Nothing is rewired for it alone.

### Assembly and enclosures

- A kit-built device is assembled on an ElectroCookie solderable breadboard prototype board (Amazon ASIN B07ZYNWJ1S,
  sold in packs with a mini board). Its strips follow a standard breadboard, so a layout proven on a breadboard moves
  across hole for hole.
- The full board measures 89 x 52 mm, with 1.2 mm through holes. Its mounting holes, measured from one corner
  and centred on the board:

  | Holes | Count | Spacing, centre to centre | Positions (mm) |
  |---|---|---|---|
  | M3 (3.2 mm) | 2 | 73.5 mm, on the long centreline | (7.75, 26), (81.25, 26) |
  | M2 (2.2 mm) | 4 | 78.25 x 35.5 mm rectangle | (5.375, 8.25), (83.625, 8.25), (5.375, 43.75), (83.625, 43.75) |

  The mini board in the same packs is listed as 50.8 x 38.1 mm; measure it before designing around it.
- Enclosures are designed around that board. They hold it on its two M3 holes with standoffs; the M2 holes are spare.
  The hole positions are also recorded in the device's catalogue file.
- The main board and the parts off it (buttons and their LEDs, display, speaker) connect through the connectors above, so the
  board can come out of its case without desoldering.

### Firmware identity and updates

- A USB device answers `?` with `HELLO <device> <version> <chip>`, for example `HELLO intake-panel 10 esp32c3`. It also
  says this at boot.
- Versions are whole numbers, kept in the source, and bumped on every firmware change.
- A USB device is updated by the station, over USB, from an image bundled in the release.
- A Wi-Fi device is updated over the air with a signed image, as the reader is today.
- Pure logic lives in `lib/<device>_core` with host tests, as the reader does.

### Discovery

The kit never guesses a port when it can identify one.

- USB devices are matched by USB vendor ID first and identified by `HELLO`. Ports of other vendors are never opened
  while looking for a C3 device. Opening a port can reset an attached device such as a printer board.
- Bought devices are matched by vendor ID or a stable `by-id` path, with a config override.
- Wi-Fi devices reach the server by DNS name.

### Data and secrets

Each peripheral has one XML catalogue file (see "Hardware catalogue"). Committed files and public firmware
images hold no secrets, network addresses, hostnames, serial numbers or personal names.

### Adding a peripheral

A new peripheral is complete when it has a catalogue file, a build guide with a bench checklist, a bill of materials
(`bom.md`) with listing links, passing paper and build checks, and a recorded bench result.
