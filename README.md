# HA Hidratespark — Home Assistant integration

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat-square)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/tag/bditter/HA-Hidratespark?label=version&style=flat-square)](https://github.com/bditter/HA-Hidratespark/releases)
[![License](https://img.shields.io/github/license/bditter/HA-Hidratespark?style=flat-square)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/bditter/HA-Hidratespark?style=flat-square)](https://github.com/bditter/HA-Hidratespark/commits)
[![Stars](https://img.shields.io/github/stars/bditter/HA-Hidratespark?style=flat-square)](https://github.com/bditter/HA-Hidratespark/stargazers)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bditter&repository=HA-Hidratespark&category=integration)

A native Home Assistant integration for HidrateSpark smart water bottles.
Connects via Bluetooth — local adapter **or an ESPHome Bluetooth proxy** — and
exposes the bottle as a Home Assistant device. No MQTT broker, no Docker
container, no Linux box near the bottle.

This is a port of [HidrateSpark-MQTT-bridge][bridge] re-architected onto Home
Assistant's own Bluetooth stack.

[bridge]: https://github.com/loryanstrant/HidrateSpark-MQTT-bridge

## Why this exists

The MQTT bridge needs a Linux host with a working Bluetooth adapter near the
bottle. That's fine for a Raspberry Pi on the kitchen counter, less fine if
your Home Assistant install is in a closet on the other side of the house.

This integration uses HA's `bluetooth` integration for transport, which means
**any ESPHome Bluetooth proxy** in range of the bottle is enough — the proxy
relays GATT operations back to HA, and this integration runs the same
HydroSync handshake and frame parser end-to-end. The same code path also
works with a directly-attached USB or onboard adapter.

## Features

- 🔋 Battery percentage
- 💧 Per-sip events with timestamps and dedup (within ±2 s / same volume)
- 📊 Daily total (rolls at local midnight) and lifetime total
- 🚰 Auto-refill detection (cap-open/close + weight delta ≥ 25 mL)
- ⚖️ Live fill level from the on-bottle weight sensor
- 🎯 Full/empty calibration buttons for per-bottle fill scaling
- 🛟 Sip-exceeds-fill fallback when no weight anchor exists yet
- 🔁 State persists across HA restarts via the Store API
- 📥 Buffered sips replay on reconnect with their original timestamps

**NOTE:** This has only been tested on a HidrateSpark PRO (v1) 21oz / 621ml with chug lid.

## Requirements

- Home Assistant 2024.4 or later
- The `bluetooth` integration set up (it's the default on HAOS)
- Either a local Bluetooth adapter on the HA host **or** an ESPHome
  Bluetooth proxy within range of the bottle
- The bottle paired once with the official HidrateSpark phone app — this puts
  it into "remembered" mode and registers its MAC

## Install

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/bditter/HA-Hidratespark` as an
   **Integration**
3. Install **HA Hidratespark**, restart HA
4. **Settings → Devices & Services → Add Integration → HA Hidratespark**

### Manual

Copy `custom_components/ha_hidratespark/` into your HA `config/custom_components/`
folder, restart HA, then add the integration from **Devices & Services**.

## Setup

If your bottle is already advertising in range of HA (or a proxy), it appears
as a Bluetooth discovery and you only need to confirm the capacity. Otherwise
**+ Add Integration → HA Hidratespark** lets you pick the bottle from a list of
discovered devices, or type its advertised name and current Bluetooth address.

You can change the bottle's capacity later via the integration's **Configure**
button.

## Coexisting with the phone app

The bottle accepts only one BLE central at a time. If the official app is
actively connected, this integration won't be able to read the bottle until
the app disconnects. Recommended setups:

- **Best:** uninstall the phone app once you're set up
- **Acceptable:** force-quit it, or revoke its Bluetooth permission, when
  you're at home
- **Occasional firmware updates:** open the phone app briefly, then close it

## Entities

| Entity | Type |
|---|---|
| Battery | sensor (%, `battery`) |
| Water today | sensor (fl oz, `total_increasing`) |
| Water lifetime | sensor (fl oz, `total_increasing`) |
| Current fill | sensor (fl oz) |
| Current fill percent | sensor (%) |
| Last sip volume | sensor (fl oz) |
| Last sip percent (raw) | diagnostic, disabled by default |
| Last reported total (raw) | diagnostic, disabled by default |
| Last sip time | sensor (timestamp) |
| Last update time | sensor (timestamp) |
| Serial number | sensor |
| Sips today | sensor (`total_increasing`) |
| Refills today | sensor (`total_increasing`) |
| Bottle weight (raw) | diagnostic, disabled by default |
| Empty weight anchor (raw) | diagnostic, disabled by default |
| Full weight anchor (raw) | diagnostic, disabled by default |
| Weight scale | diagnostic, disabled by default |
| Connected | binary_sensor (connectivity) |
| Refill detector armed | diagnostic binary_sensor, disabled by default |
| Calibrate full | button |
| Calibrate empty | button |
| Reset totals | button |

## What survives a disconnect

| Data | Buffered on bottle? | Recovered on reconnect? |
|---|---|---|
| Sips (volume + timestamp) | ✅ Yes | ✅ Replayed with original timestamps |
| Daily / lifetime totals | derived | ✅ Recomputed from replayed sips |
| Battery | ✅ | ✅ Re-read on connect |
| Current fill | ✅ | ✅ Snaps to true value within ~2 s |
| Cap open/close events | ❌ notify-only | ❌ Lost while away |
| Refill events while away | ❌ notify-only | ❌ Resulting fill level recovered, the event itself is not |

## Acknowledgements

- This project is based on
  [HA-HidrateSpark-Bluetooth-Proxy](https://github.com/loryanstrant/HA-HidrateSpark-Bluetooth-Proxy)
  by [Loryan Strant](https://github.com/loryanstrant).
- BLE handshake sequence and frame layout originally from
  [HydroSync](https://github.com/maxperron/HydroSync) (GPL-3.0).
- Cap-state and weight-sensor characteristics reverse-engineered against
  HidrateSpark Steel/PRO firmware 80.18 on the nRF52832, documented in the
  upstream MQTT bridge.

## License

MIT
