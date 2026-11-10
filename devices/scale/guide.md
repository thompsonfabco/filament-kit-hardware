# Station scale guide (DYMO M10)

The intake station weighs a spool on a DYMO M10, the DYMO Digital Postal Scale, 10-Pound (model 1772057). The scale is
a bought part with no kit firmware. The station reads it as a USB HID device. The checked data is in
[catalogue.xml](catalogue.xml), and the listing link is in [bom.md](bom.md).

## Parts

| Ref | Part | Qty | Use |
|---|---|---|---|
| SC1 | DYMO M10, Digital Postal Scale, 10-Pound (model 1772057) | 1 | Spool weight |

Its electrical limits are UNCONFIRMED in [catalogue.xml](catalogue.xml): no source was read for them. It is
bus-powered from the station PC's USB.

## Model

The station is standardized on the DYMO M10; no bench test is recorded for it yet. Other DYMO USB postal scales share
its USB vendor ID, `0922`, but are untested.

## How the station reads it

The station finds the scale by USB vendor `0922` (DYMO) among the `hidraw` devices and reads its data reports. A
report carries a status (zero, moving, stable, negative, overload and so on), a unit (grams, ounces or pounds) and
the weight. The station converts grams, ounces and pounds to grams (the unit table in the kit's `server/filament_kit/station/scale.py`, used by
`parse_report`); a report with any other unit is read as if it were grams, with no conversion. It treats a reading as
final only when the status is `stable`. Reading `hidraw` needs a udev rule, which the station installer adds.

## Auto power-off

A DYMO shows up on USB only while it is switched on, and it switches itself off after a few minutes. So:

- Switch the scale on before the station starts.
- If the scale has gone off, press its button. It comes back on USB and the station finds it again.
- Until the scale has sent something, the station status shows `station scale not seen`. That is information, not a
  failure.

## Bench checklist

- [ ] `lsusb` shows vendor `0922` with the scale on.
- [ ] The station log says "scale open".
- [ ] An empty scale reads zero, and a known weight reads within the scale's own tolerance, in grams.
- [ ] With the scale set to ounces or pounds, the station still gives grams.
- [ ] A scale that switched itself off comes back after its button is pressed, with no service restart.
- [ ] Result recorded below for the M10.

## Bench results

| Date | Model | Result | Notes |
|---|---|---|---|
| | M10 | | |
