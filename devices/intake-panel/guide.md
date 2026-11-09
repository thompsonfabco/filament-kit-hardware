# Intake panel build guide (ESP32-C3)

The intake panel is the intake station's front panel. It has a yellow (Hold) and a red (Discard) illuminated button,
a 128x64 OLED, a buzzer, a speaker on a MAX98357 amplifier, and a room-air sensor. It is built on an ESP32-C3 Super
Mini and plugs into the station PC's USB. This guide covers firmware 10 and later.

The panel's behaviour, its serial protocol, the speech format and the firmware update notes are in the kit's
[station/PANEL.md](https://github.com/thompsonfabco/filament-kit/blob/main/station/PANEL.md). This guide covers the parts, wiring, assembly, first flash and bench checks. The checked data
for this device is in [catalogue.xml](catalogue.xml), and the full circuit is in
[images/wiring.svg](images/wiring.svg).

![Intake panel wiring](images/wiring.svg)

## Parts

| Ref | Part | Qty | Use |
|---|---|---|---|
| BRD1 | ElectroCookie solderable breadboard prototype board, full size (Amazon ASIN B07ZYNWJ1S) | 1 | Main board |
| U1 | ESP32-C3 Super Mini | 1 | Controller, on the station PC's USB |
| Q1, Q2 | BS170 N-MOSFET (TO-92) | 2 | Yellow and red lamp switches |
| RG1, RG2 | 220 Ω | 2 | Gate resistors |
| RP1, RP2 | 100 kΩ | 2 | Gate pull-downs, so the lamps stay dark during reset |
| U2 | AITRIP MAX98357 I2S amplifier module, "No Welding" version (Amazon ASIN B0912CWB7Z, pack of 3) | 1 | Speaker amplifier |
| LS1 | Shutao double-cavity speaker, 8 Ω, 3 W, sealed body about 100 x 45 x 21 mm (Amazon ASIN B0DL9SFH49) | 1 | Speech |
| U3 | SSD1306 OLED module, 128x64, I2C address 0x3C | 1 | Display |
| U4, or U5 + U6 | BME280 board, or a BMP280 + AHT20 combination board | 1 | Room air |
| BZ1 | 3-wire passive buzzer module | 1 | Beeps |
| SW1, SW2 | Illuminated normally-open push buttons with 5 V lamps (resistor built in), yellow and red | 2 | Hold and Discard |
| RI1, RI2 | 4.7 kΩ | 0 or 2 | I2C pull-ups, only if neither I2C board has them |
| RSD | 10 kΩ | 0 or 1 | Amplifier SD pull-up to 3V3, only if the module has none (see "Amplifier") |
| C1 | 470 µF electrolytic, 10 V or more | 0 or 1 | Across the amplifier's VIN and GND, only if 5 V sags on speech peaks |
| XU1 | Female pin headers, 2.54 mm, 8-pin | 2 | Socket for U1, so its USB-C plug clears the M3 screw head (see "Board and layout") |
| J1-J5 | JST-XH 2.54 mm headers and plugs: four 5-pin, one 3-pin | 5 | Off-board connectors |
| F1, F2 | Wire ferrules to suit the speaker wire | 2 | Speaker leads into the screw terminal |

The datasheet limits for each active part, with their sources, are in [catalogue.xml](catalogue.xml).

## Pins

| Function | C3 GPIO | Constant |
|---|---|---|
| I2C SDA (OLED, air sensor) | 5 | `PIN_SDA` |
| I2C SCL (OLED, air sensor) | 6 | `PIN_SCL` |
| Buzzer signal | 0 | `PIN_BUZZER` |
| Yellow (Hold) switch, other side to G | 3 | `PIN_BTN_HOLD` |
| Red (Discard) switch, other side to G | 4 | `PIN_BTN_DISCARD` |
| Yellow lamp MOSFET gate | 1 | `PIN_LAMP_HOLD` |
| Red lamp MOSFET gate | 7 | `PIN_LAMP_DISCARD` |
| Amplifier BCLK | 10 | `PIN_I2S_BCLK` |
| Amplifier LRC | 20 | `PIN_I2S_LRC` |
| Amplifier DIN | 21 | `PIN_I2S_DIN` |

Never use GPIO 2, 8 or 9, which are strapping pins, or GPIO 18 and 19, which are the USB pair. GPIO 20 and 21 are
the C3's default UART. The firmware doesn't use it, because its serial link is native USB. The ROM's boot text on
GPIO 21 is harmless, because the amplifier stays silent with no I2S clock.

The buttons use the C3's internal pull-ups, so each switch goes between its pin and G with nothing else.

## Connectors

Every part off the main board plugs in through a keyed JST-XH 2.54 mm connector, so the board can come out of its
case without desoldering. The speaker is the one exception: it goes into the amplifier's screw terminal.

| Ref | Type | Pin order | To |
|---|---|---|---|
| J1 | JST-XH 5-pin, pin 5 removed | GND 3V3 SDA SCL (positions 1-4) | OLED (U3) |
| J2 | JST-XH 5-pin, pin 5 removed | GND 3V3 SDA SCL (positions 1-4) | Air sensor (U4, or U5 and U6) |
| J3 | JST-XH 5-pin, pin 1 removed | GND SW 5V LAMP- (positions 2-5) | Yellow button SW1: SW to GPIO 3, LAMP- to Q1's drain |
| J4 | JST-XH 5-pin, pin 1 removed | GND SW 5V LAMP- (positions 2-5) | Red button SW2: SW to GPIO 4, LAMP- to Q2's drain |
| J5 | JST-XH 3-pin | GND 3V3 S | Buzzer BZ1: S to GPIO 0 |
| J6 | Amplifier screw terminal | + - | Speaker LS1 |

J1 to J4 are all 5-pin and keyed by which header pin is missing, so an I2C plug and a button plug can never go into
each other's header. An OLED or sensor plug in a button header would put 5 V on a 3.3 V part, and a button plug in an
I2C header would short 3V3 to G when the button is pressed. Make the keying like this:

1. I2C headers J1 and J2: with pliers, pull header pin 5 (the one furthest from the pin 1 end) out of the housing.
   Solder pins 1 to 4 only.
2. Button headers J3 and J4: pull header pin 1 out of the housing. Solder pins 2 to 5 only.
3. I2C plugs (OLED, air sensor): fit contacts in cavities 1 to 4. Leave cavity 5 empty and push a cut-off crimp
   contact (the wire barrel snipped off) into it as a blocker.
4. Button plugs: fit contacts in cavities 2 to 5. Push a cut-off contact into cavity 1 as the blocker.

Warning: pull the pin out of the housing, don't just snip it flush, or the plug's blocker will still meet a stub and
the wrong plug may seat. Do not skip the blockers: without them the plug fits the header it shouldn't.

J3 and J4 are the same type, which is safe because both carry the same signals. If the buttons end up swapped, set
`panel_swap` as `PANEL.md` describes instead of rewiring.

## Board and layout

The main board is an ElectroCookie full-size solderable breadboard prototype board. Its strips follow a standard
breadboard: two halves of five-hole strips either side of a centre channel, with power rails along both long edges.
Prove the layout on a solderless breadboard first, then move it across hole for hole.

Measured on a board in hand:

| What | Value |
|---|---|
| Board size | 89 x 52 mm |
| M3 holes | 2, 73.5 mm apart center to center, on the board's long centerline (26 mm in from each long edge) |
| M2 holes | 4, a rectangle 78.25 x 35.5 mm center to center, equally inset from the board edges |

Hole positions, x along the 89 mm length and y across, both from the same corner:

| Hole | x (mm) | y (mm) |
|---|---|---|
| M3 | 7.75 | 26 |
| M3 | 81.25 | 26 |
| M2 | 5.375 | 8.25 |
| M2 | 83.625 | 8.25 |
| M2 | 5.375 | 43.75 |
| M2 | 83.625 | 43.75 |

The case mounts the board on the two M3 holes, with standoffs. The four M2 holes are free for anything else, such
as a cover or a cable clamp. Each M3 hole sits 7.75 mm in from a short edge. Keep parts and wires clear of the area
around each hole you use, where the standoff and screw head go.

Rails: use one long-edge rail pair for 5 V and G and the other for 3V3 and G, and join the two G rails at one end.

**U1 on female headers.** U1 straddles the centre channel, which runs along the board's long centerline, the same
line as the M3 holes. Its USB-C socket faces a short edge, so the plug and cable leave the board over the M3 hole at
that end. U1 can't turn to face a long edge while it straddles the channel, and at the other end it would sit over
the other M3 hole. So mount U1 in two 8-pin female headers soldered to the board, not directly. That lifts the plug
above the M3 screw head and standoff. The bench checklist checks that the cable plugs in fully with the board
screwed into the case.

The amplifier module, U2, sits on the main board with its pins soldered into the strips. It isn't an off-board part,
so it has no JST-XH connector. Only the speaker leaves it, through the screw terminal.

Suggested layout, from the USB end of the board to the far end:

| Region along the length | Half | What sits there |
|---|---|---|
| USB end, past the first mounting hole | Straddling the channel | U1, the C3 Super Mini, in female headers, its USB-C socket toward the board's short edge so the cable can reach it over the hole |
| Next to U1 | One half | U2, the MAX98357 module, its pin row in the strips and its screw terminal toward the board's long edge, so the speaker leads stay short |
| Next to U1 | Other half | J5 (buzzer), then J1 and J2 (I2C) |
| Middle | One half | The yellow lamp stage: Q1, RG1 and RP1 |
| Middle | Other half | J3, the yellow button |
| Far end, before the second mounting hole | One half | The red lamp stage: Q2, RG2 and RP2 |
| Far end, before the second mounting hole | Other half | J4, the red button |

Each header pin needs its own strip, and no two nets may share a strip. Check this on the breadboard before
soldering, then note the row numbers you used in the bench results.

## Enclosure

The case for the intake station is in `enclosures/intake-station/`. The controller case's speaker grille is
100 x 45 mm, the speaker's size. The simple controller variant has no grille.

## Power

Power comes from the station PC's USB 5 V. The panel's measured total must stay at or under 500 mA, the USB 2.0
limit, which the bench checklist measures. The C3's 5V pin feeds the 5 V rail: the amplifier and the lamps. The C3's
3V3 pin feeds the 3V3 rail: the OLED, the air sensor and the buzzer. An SSD1306 OLED module draws roughly 10 to 20 mA
from 3V3, an estimate (UNCONFIRMED) because the chip's datasheet gives no module figure. The Super Mini's 3V3 regulator rating and the
path from USB to its 5V pin are not in the sources found (UNCONFIRMED), so the current and rail check on the bench
covers both.

## Lamp MOSFET stages

Each lamp is the 5 V lamp built into its button, switched by a BS170 on the low side, because a GPIO pin can't drive
it directly.

- Lamp + to 5 V, lamp - to the BS170's drain (D), source (S) to G.
- Gate (G) to the lamp's GPIO through 220 Ω (RG1, RG2). 100 kΩ (RP1, RP2) from gate to G keeps the lamp dark while
  the C3 resets.
- BS170 legs, flat face toward you: D G S, left to right. The look-alike 2N7000 is S G D.

**Each lamp may draw at most 50 mA.** The C3 drives the gate at only 3.3 V, and the BS170 barely conducts there:

- Its gate threshold is 0.8 V min, 2.1 V typ and 3 V max, so 3.3 V can be only just above it.
- Its datasheet gives no RDS(on) below VGS = 10 V. At 10 V it is 1.2 Ω typ and 5 Ω max.
- Its output curve stops at VGS = 3.0 V, which carries about 0.05 A. Its transfer curve gives roughly 0.1 A or less at
  3.3 V. Both are estimates read from the curves (UNCONFIRMED as figures), not ratings.
- The 500 mA rating is for full gate drive and doesn't apply here.

The BS170 limits the current itself, so a lamp measured through it can read under 50 mA even when it would draw
more. Check each lamp in two steps:

1. **Before wiring it to Q1 or Q2,** measure the lamp alone: lamp + to 5 V, lamp - to G, with the meter in series. It
   must draw 50 mA or less. If it draws more, use a logic-level MOSFET for that lamp, as below.
2. **In circuit,** with the lamp lit by the station, measure the voltage from the MOSFET's drain to its source. At the
   flow's ready step both lamps are on. It should be under 0.3 V. A higher reading means the BS170 isn't fully on, so
   swap it. Use the station to light the lamps, not a manual `L 1 1` over serial: with no further `L` line, the panel's
   5 s watchdog turns the lamps off.

If a lamp fails either step, replace that BS170 with a logic-level N-MOSFET, for example an AO3400A on a SOT-23 adapter. Pick a part
whose datasheet gives RDS(on) at a gate voltage of 2.5 V or lower. Keep the same 220 Ω and 100 kΩ. Wire it by the
adapter's G, D and S labels, not the BS170's leg order, and add it to the catalogue with its datasheet limits.

## Amplifier (MAX98357 module)

- VIN to 5 V, GND to G.
- BCLK to GPIO 10, LRC to GPIO 20, DIN to GPIO 21.
- Leave GAIN unconnected. That gives 9 dB of gain.
- Leave SD unconnected at first, then check it as described below.

The module sits on the main board itself, next to U1 (see "Board and layout"), so it needs no JST-XH connector.

The module's listing has no schematic. It doesn't state its SD pull-up or its pin labels, and it is unreliable on
electrical figures. It gives 5.5 V as both the minimum and maximum supply. The chip's datasheet gives 2.5 to 5.5 V
operating and 6 V absolute maximum, and this panel uses 5 V.

**SD pull-up check (UNCONFIRMED on this module).** With the panel powered and SD unconnected, measure SD to G. The
chip pulls SD down internally through 100 kΩ, and with SD low the amplifier stays shut down and silent. The chip's
SD trip points, min / typ / max:

| SD voltage | Mode |
|---|---|
| Below 0.08 / 0.16 / 0.355 V | Shutdown: no sound |
| Up to 0.65 / 0.77 / 0.825 V | Left and right mixed |
| Up to 1.245 / 1.4 / 1.5 V | Right channel |
| Above that | Left channel |

The firmware writes every sample to both channels, so any mode except shutdown plays correctly. If SD measures near
0 V, the module has no pull-up, so tie SD to 3V3 through a 10 kΩ resistor (RSD) and measure again. With the chip's
100 kΩ pull-down, 10 kΩ puts SD near 3.0 V, in the left-channel range. Record the voltage you measured in the bench
results.

**LRC and BCLK labels (UNCONFIRMED on this module).** One user report found the LRC and BCLK labels swapped on
another maker's board. If there is no sound and SD is not in shutdown, swap the two wires on GPIO 10 and GPIO 20 at
the module and try again. If the swap fixes it, note it in the bench results.

## Speaker

The speaker goes only into the module's screw terminal. Neither output is a ground, so never connect either speaker
wire to G or to anything else.

1. Cut off the speaker's 2-pin plug.
2. Crimp a ferrule onto each bare wire, or leave the wires twisted and untinned. Don't tin them: solder creeps under
   a screw terminal and the joint loosens.
3. Red to +, black to -. Fit no capacitor.
4. Keep the leads short, because the outputs switch at high speed.

The listing gives both 10 cm and about 6 inches for the wire length (UNCONFIRMED). Measure it before you lay out the
board.

The speaker is rated 3 W. Its listing also says "maximum power 5W" (UNCONFIRMED), and this design uses the 3 W
figure. At 5 V into 8 Ω the amplifier can put out about 3.1 W in the worst case, a full-scale square wave, and about
1.6 W for a full-scale sine, so the speaker needs no protection from the volume setting. Current is the tighter
limit: 8 Ω at 5 V can peak at about 625 mA, which the bench check measures against the USB limit. The station's
default volume of 50 keeps peak speaker current near 310 mA.

## OLED, air sensor and buzzer

- **OLED (SSD1306 128x64, 0x3C) and air sensor:** both on the I2C bus through J1 and J2, VCC to 3V3 and GND to G,
  SDA to GPIO 5 and SCL to GPIO 6. The bus needs pull-ups: keep the sensor board's, or add 4.7 kΩ from SDA and SCL
  to 3V3 (RI1, RI2) if neither board has them. The air sensor is a BME280, or a BMP280 + AHT20 combination board, in
  which the AHT20 answers at 0x38.
- **Buzzer:** + to 3V3, - to G, S to GPIO 0. Use 3V3, not 5 V: some modules switch the buzzer with a PNP that a
  3.3 V signal can't turn off.

## First flash

A new C3 has no firmware, so it can't answer `HELLO`. Unplug any other ESP32-C3 device, such as a bench reader
plugged in for power, then plug the panel into the station PC and run:

```
sudo filament-kit station flash-panel
```

It stops the station service and lists the C3 ports that give no `HELLO`. It names each port and asks before
flashing it, then checks for `HELLO` and restarts the service. A board that already answers is left alone. After
that, the station keeps the panel's firmware current by itself.

## Bench checklist

Build checks, before the panel goes into service:

- [ ] SD on the amplifier measured with nothing connected, and tied to 3V3 through 10 kΩ (RSD) if it sat near 0 V.
- [ ] Each lamp measured alone, before wiring it to its MOSFET, from 5 V to G with the meter in series: 50 mA or
  less. If more, use a logic-level MOSFET for it (see "Lamp MOSFET stages").
- [ ] With both lamps lit by the station (the flow's ready step), drain to source on Q1 and on Q2 is under 0.3 V, and
  both lamps are fully bright. If higher, swap that BS170 for a logic-level MOSFET.
- [ ] With the board screwed into the case, the USB-C cable plugs into U1 fully without touching the M3 screw or
  standoff.
- [ ] Try each I2C plug in J3/J4 and each button plug in J1/J2; neither goes in.

Panel checklist:

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
  hold. If 5 V sags on speech peaks, fit C1, a 470 µF electrolytic rated 10 V or more, at the module: + to VIN and
  - to GND. Then measure again.

Record the result below, and the firmware version, date and measured current in `catalogue.xml` (`validated` and
`power`).

## Bench results

| Date | Firmware | Result | Measured mA | Notes |
|---|---|---|---|---|
| | | | | |
