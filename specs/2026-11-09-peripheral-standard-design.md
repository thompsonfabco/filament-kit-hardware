# Peripheral hardware standard and intake panel move to ESP32-C3: design

Status: awaiting the owner's review. Nothing here is built. Moved from `filament-kit` on 2026-11-09.

## Goal

Every peripheral the kit talks to is built to one standard, checked the same way, and documented in one place. The
owner's order of work is: update, standardize and validate, then document. The owner's decision of 2026-11-09 is that
the intake panel moves from the ESP8266 to the ESP32-C3.

Priorities follow the kit's order: functionality, then ease of use, then security.

## Where things live

Hardware design lives in this repository, `filament-kit-hardware`, which is private. Firmware and the station code stay in
`filament-kit`, which is public:

| Kept here | Kept in filament-kit |
|---|---|
| The standard, device guides, catalogue files, wiring diagrams, enclosures, bench results | Panel and reader firmware, the bundled panel image, station code, firmware build and host tests |

The kit's docs link here with one line. Because this repository is private, people using the public kit can't open that
link, so the kit keeps enough in its own docs to install and run the station: which devices it supports, and how the
station finds and updates them.

## Scope

This design covers three things, built in this order:

1. **The standard** (below), which applies to every peripheral.
2. **The intake panel's move to the ESP32-C3**, in firmware, station code and hardware.
3. **The hardware catalogue, its checks and the documentation** for all five peripherals.

Two pieces follow as their own designs, because each is a separate change that can land alone:

- **Reader setup without a compiled-in network.** See "Follow-up: reader setup".
- **Enclosures.** See "Follow-up: enclosures".

Items 1 and 3 are done in this repository. Item 2 is mostly firmware and station work in `filament-kit`, plus the
panel's guide and catalogue file here.

The printer's own NFC reader (nfc2klipper with a PN532) is third-party and stays out of scope. `docs/klipper.md` keeps
covering it.

## Current peripherals

| Device | Hardware | Link | Found by |
|---|---|---|---|
| Intake panel | Wemos D1 mini (ESP8266), CH340 | USB serial | `HELLO` answer on each `ttyUSB` port |
| Bench reader | ESP32-C3 Super Mini, PN532 on I2C, OLED, encoder | Wi-Fi, HTTPS | Compiled-in server URL |
| Station NFC reader | PN532 on a CH340 adapter, UART | USB serial | The `ttyUSB` port that is not the panel |
| Scale | DYMO M10 or M25 | USB HID | Vendor ID 0922 on `hidraw` |
| Webcam | Any USB camera | V4L2 | First `/dev/v4l/by-id` entry |

## The standard

The standard is kept in [standard.md](../standard.md).

## Intake panel on the ESP32-C3

### What stays the same

The station's flow, display text and `panel_swap` setting keep working. The lamps and their MOSFET stages, OLED, air
sensor, buzzer and buttons are the same parts. The lamp gates still see 3.3 V, so those stages need no new values.

### What changes in the parts

The speaker stage is replaced by a MAX98357 breakout board:

- **Removed:** Q3 (BS170) with its 220 Ω and 100 kΩ, Q4 (KSC2073), Q5 (KSA940), RU (1 kΩ), C1 (470 µF) and the two
  headset drivers.
- **Added:** one AITRIP MAX98357 module (ASIN B0912CWB7Z, the "No Welding" version, sold in packs of 3), with a screw
  terminal for the speaker. VIN goes to 5 V, GND to G, and BCLK, LRC and DIN to the C3.
- **GAIN and SD:** both stay unconnected, which gives 9 dB and a mix of both channels on boards with an SD pull-up.
- **Speaker:** one Shutao double-cavity speaker (ASIN B0DL9SFH49), 8 Ω, in a sealed plastic body about 100 × 45 × 21 mm
  with two mounting holes. Its 2-pin plug is cut off and the bare wires go into the module's screw terminal, red to +
  and black to −, with no capacitor. The wires get ferrules or stay twisted and untinned, because solder creeps under a
  screw terminal and the joint loosens. The leads stay short, because the outputs switch at high speed.

A 5 V supply limits what the amplifier can put into 8 Ω: about 3.1 W in the worst case, a full-scale square wave, and
about 1.6 W for a full-scale sine. That stays within the speaker's 3 W rating in practice, so the speaker needs no
protection from the volume setting. Current is the tighter limit: 8 Ω at 5 V can peak at about 625 mA, which the bench
check measures against the USB limit.

### Pins

| Function | C3 GPIO | Constant | D1 mini pin it replaces |
|---|---|---|---|
| I2C SDA (OLED, air sensor) | 5 | `PIN_SDA` | D3 |
| I2C SCL (OLED, air sensor) | 6 | `PIN_SCL` | D4 |
| Buzzer signal | 0 | `PIN_BUZZER` | D7 |
| Yellow switch, other side to G | 3 | `PIN_BTN_HOLD` | D1 |
| Red switch, other side to G | 4 | `PIN_BTN_DISCARD` | D2 |
| Yellow lamp MOSFET gate | 1 | `PIN_LAMP_HOLD` | D5 |
| Red lamp MOSFET gate | 7 | `PIN_LAMP_DISCARD` | D6 |
| Amplifier BCLK | 10 | `PIN_I2S_BCLK` | D8, the speaker gate |
| Amplifier LRC | 20 | `PIN_I2S_LRC` | New |
| Amplifier DIN | 21 | `PIN_I2S_DIN` | New |

This uses every free GPIO except the strapping pins. GPIO 20 and 21 are the C3's default UART, which the firmware
doesn't use because its serial link is native USB. The ROM's boot text on GPIO 21 is harmless, because the amplifier
stays silent with no I2S clock.

The ESP8266's boot-pin rules for the I2C and speaker pins no longer apply. I2C still needs pull-ups: keep the sensor
board's, or add 4.7 kΩ to 3V3 on a board that has none.

### Firmware changes

- **Build:** `platformio.ini` moves to the reader's pinned platform and board with the same USB flags. `build.sh` merges
  the bootloader, partition table and application into one image written at address 0, so the file name
  `intake-panel.bin` and the install paths stay as they are.
- **Radio:** Wi-Fi and Bluetooth are never started.
- **USB serial:** `Serial.setTxTimeoutMs(0)` keeps a missing host from stalling the main loop. The receive buffer stays
  at 2048 bytes.
- **I2C:** the bus clock is set to 400 kHz, so a full OLED update stays short.
- **Logic:** the line parser, lamp modes and button timing move to `lib/panel_core` with host tests.

### Speech

The ESP8266 firmware times every PWM edge by hand on `timer1`. The C3 replaces this with I2S and DMA, so the hand-timed
code and the whine it caused both go away:

- **Output:** I2S runs at 8 kHz with 16-bit samples, and needs no master clock. The firmware writes each sample to both
  channels, so the sound is right whichever channel a breakout board's SD wiring selects.
- **Stream:** the `A <n>` frames stay unsigned 8-bit at 8 kHz, but on the C3 a byte means a sample and 128 means silence.
  The firmware converts each byte to signed 16-bit and applies the volume.
- **Playing:** a small FreeRTOS task above the main loop's priority moves samples from the 1 s ring buffer to I2S. While
  the ring is empty it sends silence, so the amplifier stays settled between phrases.
- **Gaps:** no capacitor sits between the amplifier and the speaker now, so a gap doesn't hold the last sample as the
  ESP8266 did. The output fades to silence over 50 ms instead.
- **Volume:** a new `V <percent>` line from the PC sets the level in the 16-bit samples, without losing resolution or
  needing a reflash. The new setting `station.speaker_volume` starts at 50, which keeps peak speaker current near
  310 mA. The owner sets the final value on the bench, by ear and against the USB current check.
- **Buzzer:** it stays on its own pin and LEDC channel, independent of speech.

The station's speech code has to change for the C3. It ramps each phrase up from a duty of 0 to protect C1, and on the
C3 that byte would be a full negative sample and a loud thump. See "Station changes".

The station's voicing filter was picked for a small open-air headset driver: nothing below 450 Hz, 8 dB of lift at
2.5 kHz and hard compression. The sealed speaker can play lower, so C3 panels get their own starting filter: a high-pass
at 150 Hz, the same 3.6 kHz low-pass, and light compression. The final filter is picked by ear on the bench, as the
current one was.

Sample rate and width stay at 8 kHz and 8 bits for the first build. The better speaker may make their limits audible. If
it does, raising them changes only the firmware and station code, not the hardware.

### Station changes

- **Port list:** `state.py` gains a panel port list: `ttyACM` ports whose USB vendor ID is 303A, read from sysfs, then
  `ttyUSB` ports. `usb_ttys()` stays `ttyUSB`-only for the PN532. A C3 panel is found first, so the PN532's port is not
  opened in that search.
- **Writes:** the panel's serial port gets a 1 s write timeout. A USB port can block when the device stops reading,
  which a UART never did. A timeout falls into `panel_send`'s existing handling, which drops the panel and finds it
  again.
- **Speech:** `speech.py` picks its output by the panel's chip. For an `esp32c3` panel, `to_panel` uses the sealed
  speaker's filter, adds silence at 128 with no ramp from 0, and a phrase cut off by a newer one fades toward 128. A
  panel with no chip token keeps today's filter, ramp and fade. The station sends `V` once after finding a C3 panel and again when the setting changes.
- **Flashing:** `flash_panel` uses `--chip esp32c3` with esptool's USB reset. The existing guards stay: once per version
  per run, and never the reader's port.
- **Old panels:** a panel whose `HELLO` has no chip token is an ESP8266 on firmware 9 or older. The station keeps using
  it, logs that it runs old firmware, and never flashes it. Firmware 10 onward is the C3 only.
- **First flash:** `sudo filament-kit station flash-panel` writes a blank board. It stops the station service, lists the
  303A ports that give no `HELLO`, asks for confirmation naming the port, flashes it, and restarts the service. A blank
  board is never flashed without that confirmation, because a reader plugged in for power looks the same.

### Rollout

The working D1 mini panel stays in service until the new one has passed:

1. Build firmware 10 and the station changes on a branch.
2. Flash a spare C3 and run the panel checklist with a spare set of parts, including the amplifier and speaker, on a
   breadboard.
3. Set the volume and voicing filter by ear, and compare speech with the D1 mini.
4. Move the parts to the C3 and rerun the checklist on the finished panel.

The ESP8266 source stays available in git history. The bundled image and source are replaced by the C3 ones.

## Hardware catalogue

One file per device, `devices/<device>/catalogue.xml` in this repository. For the intake panel:

```xml
<device id="intake-panel" schema="1">
  <board family="esp32-c3" model="ESP32-C3 Super Mini"/>
  <link type="usb-serial" vendor="303a" hello="intake-panel"/>
  <firmware source="station/panel/src/main.cpp" bundled="station/panel/firmware/VERSION" update="station-usb"/>
  <pins>
    <pin gpio="5" constant="PIN_SDA" role="i2c-sda"/>
  </pins>
  <parts>
    <part ref="Q1" name="BS170" qty="1" use="yellow lamp switch"/>
  </parts>
  <connectors>
    <connector ref="J1" type="JST-XH-4" order="GND 3V3 SDA SCL" to="OLED"/>
  </connectors>
  <power measured_ma=""/>
  <validated firmware="" date=""/>
</device>
```

The `firmware` paths are paths inside `filament-kit`. Bought devices use the same file with no `pins` or `firmware`,
and with `<example model="..." source="..."/>` entries for models named in the kit's docs (a bench test is recorded in the guide's Bench results table, not here). These files are documentation and are not shipped to installed systems.

## Validation

| Level | What it checks | Where it runs |
|---|---|---|
| Paper | Every catalogue pin matches the firmware constant and the guide's pin table; no strapping pin is used; `HELLO` name and chip match the source; every active part names its datasheet voltage and current limits | This repository's CI, which checks out the public `filament-kit` at its `main` branch to read the firmware |
| Build | Both firmwares build; host tests pass, including the BME280 and AHT20 tests, which CI doesn't run today | `filament-kit` CI: a new `panel.yml` and the existing `reader.yml` |
| Station | Port selection with fake sysfs entries, including a non-Espressif `ttyACM` board that must never be opened; chip token handling; old panel never flashed; write timeout recovery; first-flash confirmation; no C3 stream or cut-off fade ever leaves 128 at its start or end | `filament-kit` CI, in `server/tests` |
| Bench | Real hardware, by checklist | The owner, recording the firmware version and date in the catalogue file here |

Bench checklist for the panel:

- [ ] A cold boot gives `HELLO intake-panel 10 esp32c3`, with both lamps dark during reset.
- [ ] The station finds the panel, and the PN532 opens as the station's reader.
- [ ] Unplugging and replugging the panel recovers without a service restart.
- [ ] The station updates the panel from an older C3 firmware by itself.
- [ ] Each button gives a short and a long press, and each lamp shows all modes.
- [ ] The OLED shows all rows, and "Station offline" 5 s after the service stops.
- [ ] Air readings appear in `/state` for the fitted sensor.
- [ ] Beeps play at the flow's frequencies, and a beep during speech leaves the speech intact.
- [ ] Speech is clear at the chosen volume and filter, with no whine and no buzzing or rattle from the speaker.
- [ ] Power-up, reset, phrase start, phrase end and a phrase cut off by a newer one make no thump.
- [ ] Idle hiss between phrases is not noticeable at working distance.
- [ ] A full intake runs from scan to save with a real spool.
- [ ] USB current with both lamps lit and speech at the chosen volume is at or under 500 mA, and the 5 V and 3V3 rails
  hold. If 5 V sags on speech peaks, fit the removed 470 µF capacitor across the amplifier's VIN and GND and measure
  again.

Facts not yet confirmed on real hardware, which the bench checks settle:

- The Super Mini's 3V3 regulator rating and its 5 V pin path are not in the sources found. The current and rail check
  covers both.
- A C3's USB serial number appeared as its MAC address in one example only. The design doesn't depend on it, because
  vendor ID and `HELLO` identify the panel.
- Whether opening the C3's port resets it is unconfirmed. The station already handles both cases by asking with `?`.
- The module's listing has no schematic and doesn't state its SD pull-up or pin labels. One user report found LRC and
  BCLK labels swapped on another maker's board. If there is no sound, check those first, and measure SD to see whether
  it sits high with nothing connected. A module with no SD pull-up needs SD tied high through a resistor.
- The module's listing is unreliable on electrical figures. It gives 5.5 V as both the minimum and maximum supply, and
  2 channels for a mono chip. This design uses 5 V, which is inside the range in a copy of the chip's datasheet.
- The sources found confirm the 8 kHz lower sample rate, the five gain steps and that no master clock is needed. They
  don't confirm the amplifier's power rating, so the power figures above come from the 5 V supply and 8 Ω load.
- The speaker's listing contradicts itself or is unclear in places, and is the only source for these points:
  - It gives "maximum power 5W" and "rated power: 3 W". This design uses the 3 W figure.
  - It lists both 10 cm and about 6 inches for the wire length. Measure this before laying out the enclosure.
  - It gives a frequency response of 0-20 kHz, which isn't a usable figure. The voicing filter is set by ear instead.

## Documentation

Layout of this repository:

```
README.md                            what this repository is and a device index
standard.md                          the standard, taken from this design once it is approved
devices/<device>/guide.md            build guide, wiring, parts, bench checklist and bench results
devices/<device>/catalogue.xml       the checked data
devices/<device>/images/             wiring diagrams
enclosures/<device>/                 STEP and printable files
specs/                               designs such as this one
tools/                               the owner-data scan and the paper check
```

The devices are `intake-panel`, `bench-reader`, `station-nfc`, `scale` and `webcam`.

Moves out of `filament-kit`, done as kit changes:

- `station/PANEL.md` keeps the panel's serial protocol, speech format and firmware update notes, which the kit's code
  and tests depend on. Its wiring, parts, speaker stage and build steps move to `devices/intake-panel/guide.md`.
- `station/panel/wiring.svg` and `wiring.png` are redrawn for the C3 and move to `devices/intake-panel/images/`.
- The kit's user guide keeps its supported-device list, corrects the old Hold and Discard wording to the yellow and
  red flow, and adds the one link line to this repository.
- `reader/README.md` keeps the API and firmware build. Its hardware table moves to `devices/bench-reader/guide.md`.
- `THIRD-PARTY.md` changes the panel firmware's line from the ESP8266 core to the ESP32 core.

`standard.md` replaces the standard's section of this design once both are approved.

## KiCad

The owner decided on 2026-11-09 to keep the hardware designs in KiCad 10.

### What lives where

- A shared library at `kicad/` holds the parts the stock KiCad libraries don't have:
  - **Symbols:** ESP32-C3 Super Mini, the MAX98357 module, the BME280 and AHT20 boards, the SSD1306 module and the
    3-pin buzzer module.
  - **Footprints:** the same modules, plus `ElectroCookie_Full`.
- Each kit-built device has a project at `devices/<device>/kicad/`. The bought devices have none.
- `ElectroCookie_Full` is the board as an outline: 89 x 52 mm, the two M3 holes at (7.75, 26) and (81.25, 26), the four
  M2 holes on the 78.25 x 35.5 mm rectangle, and the 2.54 mm hole grid as reference marks. The breadboard strips aren't
  modelled as copper, so the layout table in the guide stays the reference for strip connections.

### The schematic is the source of truth

- The wiring is defined by the schematic.
- Each net on a C3 GPIO pin is named after its firmware constant without the `PIN_` prefix, for example `SDA` or
  `LAMP_HOLD`.
- Parts carry their datasheet limits as symbol properties: `Vmax`, `Imax`, `Imax_basis` and `Datasheet`.
- `catalogue.xml` keeps what a schematic can't hold: the link, firmware paths, mounting, measured power and bench
  results. Its `pins` and `parts` sections stay, and the paper check compares them with the netlist.
- `images/schematic.svg` and `schematic.pdf` are exports made with `kicad-cli`. They replace the hand-drawn
  `wiring.svg`.

### Checks

- **ERC** is a new validation level. `kicad-cli sch erc` must report 0 errors. Warnings are allowed only when the
  device's guide lists them.
- **Paper check:** it reads the netlist exported by `kicad-cli sch export netlist`. It checks:
  - every GPIO net against the firmware constant;
  - that no strapping or USB pin is used;
  - that every active part has `Vmax`, `Imax` and `Datasheet`;
  - that the catalogue agrees with the netlist: pin GPIOs, `vmax`, `imax` and `datasheet` per part, and part kind
    (a part is active when its ref prefix is an active one or it carries `Vmax`);
  - that every active schematic part has a catalogue part of the same ref (exact, so a range or a case variant does
    not count), and every active catalogue part has a schematic counterpart and ratings;
  - that no catalogue ref is duplicated (case ignored), every `kind` is exactly `active` or `passive`, and a passive
    part carries no `vmax`, `imax` or `datasheet`;
  - that no net joins two GPIOs and no GPIO is wired to two nets;
  - that a `usb-serial` device with firmware declares a HELLO on its `<link>`;
  - that the guide's pin table matches.
- **CI:** both checks run in a `kicad/kicad:10.0` container next to the existing jobs.
- **Fit:** dropped on 2026-11-09 by the owner: no proto-board layout, so no STEP export of a placed board.
- **Owner data:** KiCad files are plain text, so the owner-data scan covers them. Leave the title block's company and
  author fields empty.

### Order

1. Library and the `ElectroCookie_Full` footprint.
2. Intake panel schematic, with ERC clean and its exports.
3. Paper check reading the netlist, and the KiCad CI job.
4. Intake panel placement on the board, with the STEP export. (Dropped on 2026-11-09 by the owner: no proto-board layout.)
5. Bench reader schematic, folded into its guide task.

## Follow-up: reader setup

The reader's Wi-Fi password, server URL and token are compiled into its image today, so anyone using the public repo
has to build their own firmware. The next design moves them to on-device setup stored in flash. An image with no
secrets could then ship in a release and be served without a token. This needs its own design because it changes the
reader's first-run flow and how its update images are signed.

## Follow-up: enclosures

The reader's case is four STEP files, copied into `enclosures/bench-reader/` from an older project. Their headers hold
no personal data, and their fit against the current reader build is unchecked. The design for this piece checks that
fit and adds printable files. Every enclosure is designed around the ElectroCookie prototype board the standard names,
mounted on its M3 holes, using hole positions measured from a real board. The panel has no enclosure files today. Its enclosure is designed once the rebuilt panel's
parts are final. The speaker's body is already sealed, so the enclosure needs only a mount using its two holes and an
opening in front of the speaker, with no baffle.

## Done means

- The rebuilt panel passes its bench checklist, with the result recorded in its catalogue file.
- All five peripherals have a catalogue file and a guide under `devices/` in this repository.
- This repository's CI runs the paper check, and the kit's CI runs the build and station checks.
- The follow-up designs for reader setup and enclosures are ready for the owner's review.
