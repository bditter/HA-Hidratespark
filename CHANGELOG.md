# Changelog

## What's new in v1.2.6-beta.6

### Added
- Added disabled-by-default diagnostics for calibrated empty raw weight, full
  raw weight, active raw-units-per-mL scale, and refill detector armed state.

## What's new in v1.2.6-beta.5

### Fixed
- Refill counting now re-arms as soon as calibrated weight falls to the low
  threshold and counts a refill when the mug returns to the fill line, avoiding
  missed refills after empty-to-fill-line cycles.

## What's new in v1.2.6-beta.4

### Fixed
- Current fill now snaps to zero when a calibrated raw weight is within 5 mL of
  the empty anchor, preventing tiny near-empty residuals like 0.07 fl oz.

## What's new in v1.2.6-beta.3

### Fixed
- Reset totals now re-baselines current fill from the latest calibrated raw
  weight, preventing an immediate partial fill from being counted as consumed.
- Weight-based refill counting now requires a low-to-near-full transition, so a
  fill that climbs in multiple stable weight steps counts as one refill.

## What's new in v1.2.6-beta.2

### Changed
- When explicit full/empty calibration exists, water totals are now counted from
  calibrated weight drops instead of raw sip-percent volume.
- Partial fills now continue to use their raw position in the calibrated
  full/empty span, so near-full readings can show 99% instead of snapping to
  100%.

## What's new in v1.2.6-beta.1

### Added
- Added disabled-by-default diagnostic sensors for the raw sip percent and raw
  reported total fields sent by the bottle.

### Changed
- Sip totals are back to using the bottle's raw percent-derived sip volume while
  the reported-total field is investigated.

## What's new in v1.2.5

### Fixed
- Current fill now ignores tiny weight-derived changes under 5 mL so raw sensor
  jitter does not show up as constant 0.03-0.08 fl oz movement.
- Volume sensors now publish native two-decimal fluid ounces so the default
  Home Assistant state is 0.00 rather than 0.000.

## What's new in v1.2.4

### Fixed
- Sip totals now use the bottle's cumulative reported mL delta when available,
  reducing undercount caused by integer percent-based sip volume frames.
- Volume sensors now suggest two decimal places in Home Assistant so fill values
  like 887 mL display as 29.99 fl oz instead of rounding to 30.0 fl oz.

## What's new in v1.2.3

### Added
- Added a **Last update time** sensor that records when bottle data was most
  recently received by the integration.

## What's new in v1.2.2

### Added
- Read the standard BLE serial number characteristic when available, expose it
  as a regular sensor, and use it as the Home Assistant device display name.
- Added a **Reset totals** button to clear accumulated water, sip, refill, and
  lifetime totals without clearing calibration or current fill.

## What's new in v1.2.1

### Fixed
- Refills can now be inferred from stable weight increases after explicit
  full/empty calibration, so travel mugs without cap events can still update
  `refills_today` when they go from significantly lower fill back toward full.

## What's new in v1.2.0

### Added
- Added **Calibrate full** and **Calibrate empty** buttons. Fill the bottle and
  press Calibrate full, then empty it and press Calibrate empty to set a
  per-bottle raw-weight scale.

### Fixed
- When both calibration anchors are available, current fill is calculated from
  the bottle's own full/empty raw span instead of the previous hardcoded
  raw-units-per-mL estimate.
- Reconnect recovery now refreshes the latest advertised MAC before each BLE
  lookup and caps retry backoff at 15 seconds if an advertisement wakeup is
  missed.

## What's new in v1.1.0

### Fixed
- Use the bottle's advertised name as the stable integration identity, and treat
  the Bluetooth MAC address as a mutable connection detail. When Home Assistant
  sees the same bottle name advertising with a new MAC, the integration updates
  the stored address and reconnects without requiring the bottle to be deleted
  and re-added.

## What's new in v0.2.0
Legacy-firmware (e.g. 32oz) bottles now report weight/fill, plus several sip-accuracy
and resilience fixes. Big thanks to **[Huw Davies (@hadavies)](https://github.com/hadavies)**,
who contributed all of the changes in this release and verified them on real HidrateSpark
hardware.

### Added
- **Weight & fill on legacy-firmware bottles (e.g. 32oz)** — the weight characteristic is
  now decoded as a full 16-bit value with stability-based "settled" detection, instead of
  relying on a fixed orientation byte that legacy firmware doesn't send. Fill is measured up
  from the bottle's learned empty weight, and the full-weight anchor auto-calibrates from the
  first settled reading (no cap open/close needed). _(contributed by @hadavies)_

### Fixed
- **No more double-counting after a Home Assistant restart** — the recent-sip dedup window is
  now persisted, so buffered sips replayed when the bottle reconnects are recognised as
  duplicates instead of re-added to your totals. _(contributed by @hadavies)_
- **'Today' counters no longer reset to zero on reconnect** — daily rollover is keyed on the
  current local time rather than a replayed sip's old timestamp. _(contributed by @hadavies)_
- **'Last sip' time no longer jumps backwards** when old buffered frames are replayed — it
  only ever advances forward. _(contributed by @hadavies)_
- **Corrupt sip frames are dropped** (bogus >10-year-old timestamps) rather than being
  recorded as a sip "now", and the re-drain loop is bounded so a stuck record can't cause an
  unbounded write loop. _(contributed by @hadavies)_

### Upgrade notes
- On first run after upgrading, weight-equipped bottles re-establish their full-weight
  calibration automatically from the next settled reading; the previous weight anchor is not
  carried over. No action needed.
