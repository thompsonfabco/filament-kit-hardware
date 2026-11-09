# Station scale guide (DYMO USB postal scale)

The station weighs a spool on a DYMO USB postal scale. The scale is a bought part with no kit firmware. The station
reads it as a USB HID device. The checked data is in [catalogue.xml](catalogue.xml).

## Parts

| Ref | Part | Qty | Use |
|---|---|---|---|
| SC1 | DYMO USB postal scale, M10, M25 or an S-series model | 1 | Spool weight |

Its electrical limits are UNCONFIRMED in [catalogue.xml](catalogue.xml): no source was read for them. It is
bus-powered from the station PC's USB.

## Tested models

| Model | Status |
|---|---|
| M10 | Listed as tested in the catalogue |
| M25 | Listed as tested in the catalogue |
| Other S-series | Not tested: the owner tries one and records it in the bench results |

## How the station reads it

The station finds the scale by USB vendor `0922` (DYMO) among the `hidraw` devices and reads its data reports. A
report carries a status (zero, moving, stable, negative, overload and so on), a unit (grams, ounces or pounds) and
the weight. The station converts every unit to grams, and treats a reading as final only when the status is
`stable`. Reading `hidraw` needs a udev rule, which the station installer adds.

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
- [ ] Model tested, and any model beyond M10 and M25 noted below.

## Bench results

| Date | Model | Result | Notes |
|---|---|---|---|
| | | | |
