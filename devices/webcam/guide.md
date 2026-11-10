# Station webcam guide (USB camera)

The station takes a picture of a new spool when yellow is pressed at the camera step. The server uses it to recognise
the spool. The webcam is a bought part with no kit firmware. The checked data is in [catalogue.xml](catalogue.xml).

## Parts

| Ref | Part | Qty | Use |
|---|---|---|---|
| CAM1 | USB webcam that gives 1080p MJPEG | 1 | Spool picture |

Its electrical limits are UNCONFIRMED in [catalogue.xml](catalogue.xml): no source was read for them. It is
bus-powered from the station PC's USB. Choose a camera that offers 1920x1080 in MJPEG.

## How the station finds it

With `STATION_CAMERA` at `auto`, the station uses the first `/dev/v4l/by-id/*-video-index0` device, which is the first
USB camera. Set `STATION_CAMERA` to a `/dev/video` path to pick one, or to `off` to turn the camera off. The
station's user must be in the `video` group, which the installer arranges.

## Picture

The station runs ffmpeg and first asks for 1080p MJPEG. If the camera can't give that, it takes whatever the camera
gives. It skips the first 15 frames so the camera can set its exposure, then keeps one JPEG.

## Mounting and lighting

These are builder choices, measured on the bench, not fixed by the kit:

| What | Value |
|---|---|
| Distance from lens to the spool | To be measured on the bench |
| Lighting | Even and diffuse, with no glare off the spool; to be chosen on the bench |
| Camera angle | To be chosen on the bench |

Set the camera so the whole spool, including its label, fills the picture and is in focus. Record the distance and
the lighting in the bench results.

## Bench checklist

- [ ] `ls /dev/v4l/by-id/` shows a `-video-index0` entry.
- [ ] `v4l2-ctl --list-formats-ext` shows MJPEG at 1920x1080.
- [ ] Yellow at the camera step gives a picture at `/photo`, at 1080p.
- [ ] The label is readable and there is no glare at the chosen distance and light.
- [ ] Unplugging and replugging the camera recovers without a service restart.
- [ ] Distance and lighting recorded below.

## Bench results

| Date | Distance (mm) | Lighting | Result | Notes |
|---|---|---|---|---|
| | | | | |
