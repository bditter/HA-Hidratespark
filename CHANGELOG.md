# Changelog

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
