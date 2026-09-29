# EPGAgeRating

**Enigma2 plugin that adds DVB age rating (parental rating) to the OpenWebif `/api/epgservice` JSON API.**

Built for OpenATV 7.x. No OpenWebif files are modified.

![Platform](https://img.shields.io/badge/platform-Enigma2-blue)
![Image](https://img.shields.io/badge/image-OpenATV%207.x-green)
![Python](https://img.shields.io/badge/python-3-yellow)
![License](https://img.shields.io/badge/license-GPLv2-lightgrey)

---

## Why?

DVB broadcasters transmit a parental rating for many programmes inside the EIT (Event Information Table). Enigma2 stores this value in its EPG cache, but OpenWebif never exposes it: the `/api/epgservice` response contains title, times and descriptions, but no age rating.

This plugin fills that gap, so apps, home automation setups, dashboards and parental-control scripts can read the age rating directly from the OpenWebif JSON API.

## Features

- Adds an `age_rating` field to every event returned by:
  - `/api/epgservice`
  - `/api/epgservicenow`
  - `/api/epgservicenext`
- Converts the raw DVB value to a real minimum age (DVB value + 3, per ETSI EN 300 468)
- Patches OpenWebif **in memory** at startup, so nothing on disk is changed and OpenWebif updates don't break it
- Starts automatically with enigma2 and waits for OpenWebif to load, so start order doesn't matter
- Fails safely: if a lookup fails, the event is returned with `age_rating: 0` instead of breaking the API

## Requirements

- An Enigma2 receiver running **OpenATV 7.x** (Python 3)
- **OpenWebif** installed and enabled
- EPG data received over **DVB EIT** (see [Limitations](#limitations))

Other Python 3 based images (OpenPLi 9+, OpenViX, etc.) will likely work too, but are untested.

## Usage

Call the OpenWebif API as usual:

```
http://RECEIVER_IP/api/epgservice?sRef=1:0:19:283D:3FB:1:C00000:0:0:0:
```

Each event now includes `age_rating`:

```json
{
  "result": true,
  "events": [
    {
      "id": 12345,
      "begin_timestamp": 1790000000,
      "duration_sec": 5400,
      "title": "Example Movie",
      "shortdesc": "Thriller",
      "longdesc": "...",
      "sref": "1:0:19:283D:3FB:1:C00000:0:0:0:",
      "sname": "Example Channel",
      "age_rating": 16
    }
  ]
}
```

### Field reference

| Field        | Type | Description                                                      |
|--------------|------|------------------------------------------------------------------|
| `age_rating` | int  | Minimum age in years. `0` means unrated or no data broadcast.    |

Value mapping (ETSI EN 300 468):

| DVB raw value | `age_rating`                          |
|---------------|---------------------------------------|
| `0x00`        | `0` (undefined / not rated)           |
| `0x01`–`0x0F` | raw + 3 (e.g. `0x09` → `12`, `0x0F` → `18`) |
| `0x10`–`0xFF` | raw value passed through (broadcaster-defined) |

### Checking that the plugin is active

Open **Menu → Plugins → EPGAgeRating**. A message confirms whether the patch was applied to OpenWebif.

You can also check the enigma2 debug log for lines starting with `[EPGAgeRating]`:

```sh
grep EPGAgeRating /home/root/logs/*.log
```

## Optional fields

Two additional fields are available but disabled by default:

| Field                | Type   | Description                                         |
|----------------------|--------|-----------------------------------------------------|
| `age_rating_raw`     | int    | Raw DVB rating value as broadcast                   |
| `age_rating_country` | string | Country code from the EIT parental rating descriptor |

To enable them, edit the plugin on the receiver:

```sh
vi /usr/lib/enigma2/python/Plugins/Extensions/EPGAgeRating/plugin.py
```

In the `_lookup_parental()` function, uncomment these four lines:

```python
# out["age_rating_raw"] = 0
# out["age_rating_country"] = ""
...
# out["age_rating_raw"] = raw
# out["age_rating_country"] = country
```

Then restart the GUI.

## Limitations

- **Only DVB EIT data is supported.** Ratings exist only if the broadcaster transmits them. EPG imported from XMLTV sources (e.g. EPGImport / Rytec) usually contains no parental data, so those channels return `age_rating: 0`.
- **The +3 conversion follows the DVB standard**, but some providers deviate from it. If ratings look off by 3 years, enable `age_rating_raw` and apply your own mapping.
- **JSON API only.** The XML endpoints (`/web/epgservice`) are rendered from precompiled templates and are not changed.
- **Bouquet-wide endpoints** (`/api/epgbouquet`, `/api/epgmulti`) are not enriched, to avoid slowing down large EPG requests.

## How it works

At enigma2 startup, the plugin imports OpenWebif's `controllers.models.services` module and wraps the `getChannelEpg()` and `getNowNextEpg()` functions. The references held by `controllers.web` and `controllers.ajax` are rebound as well.

After the original function returns its event list, the wrapper looks up each event in `eEPGCache` by service reference and event ID, reads `getParentalData()`, and adds the rating to the event dictionary.

Because the patch lives only in memory, removing the plugin or updating OpenWebif leaves no leftovers on disk.

## Troubleshooting

#### `age_rating` is missing from the JSON
The patch wasn't applied. Open the plugin from the plugin menu to see the status, and make sure OpenWebif is installed and running. Check the log for `[EPGAgeRating]` messages.

#### `age_rating` is always 0
The channel most likely doesn't broadcast parental data, or the EPG comes from an XMLTV import. Try a channel whose EPG comes directly from the satellite/cable/terrestrial stream.

#### Values are 3 years off
Your provider doesn't follow the DVB standard for this field. Enable `age_rating_raw` (see [Optional fields](#optional-fields)) and use the raw value instead.

## Related links

- [OpenWebif](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif)
- [OpenATV](https://github.com/openatv)