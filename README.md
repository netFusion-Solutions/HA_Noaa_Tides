# NOAA Tides Integration for Home Assistant

> [!NOTE]
> **This is netFusion Solutions' fork** of [Flight-Lab/HA_Noaa_Tides](https://github.com/Flight-Lab/HA_Noaa_Tides). It is a drop-in replacement — same `noaa_tides` domain, same entity IDs, same config entries — so it is meant to *replace* the upstream install, not run alongside it. See [What's different from upstream](#whats-different-from-upstream) below, and [NOTICE](NOTICE) for the required Apache-2.0 change log.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A custom component for Home Assistant that provides real-time tidal, current, and environmental data from NOAA's Center for Operational Oceanographic Products and Services (CO-OPS) API and the National Data Buoy Center (NDBC) API. This component enhances and extends the functionality of the [legacy NOAA Tides core component](https://www.home-assistant.io/integrations/noaa_tides/), offering UI configurability, automatic sensor detection, and enhanced data handling.

## What's different from upstream

This fork carries two bug fixes (also submitted upstream as PRs) and one fork-only feature:

- **Fix: tide predictions no longer die overnight.** The upstream prediction window started at midnight, so between midnight and the day's first tide there was no "past" tide to anchor to and the sensor dropped every attribute and went `unavailable`. The window now starts a day earlier and is widened to 72 hours, verified clean across a full day at 15-minute resolution.
- **Fix: barometric pressure reads correctly.** NOAA's `air_pressure` product returns millibars regardless of the requested unit system, but the imperial sensor was labelled inHg, inflating displayed pressure by ~33.86x (e.g. 1018.7 mb showing as 34500 hPa). It now reports natively in hPa/mb and lets Home Assistant convert for imperial display.
- **Feature (opt-in, off by default): datum correction.** NOAA tide predictions are astronomical, referenced to the 1983-2001 tidal epoch, and can run persistently below observed water level due to sea-level rise and seasonal mean-sea-level variation. When enabled in the integration options, this fork corrects predicted tide levels using NOAA's own published monthly-mean-sea-level offset (refreshed monthly, computed live — never hardcoded per station) and exposes the raw predictions and the applied offset alongside the corrected values. This is a fork-only feature and is not part of the upstream pull requests.

> [!IMPORTANT]  
> **Pre-1.0 Notice**: Sensor entity names and some attributes may change before v1.0.0. 
> This could affect your automations and dashboards.

## Features

- **Dual Data Sources**: 
  - NOAA CO-OPS stations for coastal and environmental data
  - NDBC buoys for offshore marine and weather observations
- **Automatic Sensor Discovery**: Available sensors are automatically detected based on your station/buoy selection
- **Real-time Data**: Regular updates from NOAA/NDBC APIs
- **Configurable Units**: Support for both metric and imperial measurements
- **Multiple Time Zone Options**: GMT, Local Standard Time, or Local Standard/Daylight Time
- **Customizable Update Intervals**: Adjust data refresh frequency to your needs

## Available Sensors

### NOAA Station Sensors
- Water Level
- Tide Predictions (with tide state, timing, factor, and percentage)
- Current Speed and Direction
- Current Predictions (expiremental)
- Water Temperature
- Air Temperature
- Wind Speed and Direction
- Air Pressure
- Humidity
- Conductivity

### NDBC Buoy Sensors
- Meteorological Data
  - Wind Speed, Direction, and Gusts
  - Wave Height, Period, and Direction
  - Air Temperature
  - Water Temperature
  - Barometric Pressure
- Spectral Wave Data
- Ocean Current Data

## Installation

### Using HACS (Recommended)

1. Ensure you have [HACS](https://hacs.xyz/) installed
2. Add this repository as a custom repository in HACS:
   - Go to HACS > Integrations
   - Click the three dots in the top right
   - Select "Custom repositories"
   - Add `https://github.com/netFusion-Solutions/HA_Noaa_Tides` with Category "Integration"
3. Click "Install"
4. Restart Home Assistant

> [!IMPORTANT]
> This fork uses the same `noaa_tides` domain as upstream. If you have the Flight-Lab version installed, remove it first (HACS will refuse to install a domain clash) — your config entry and entity IDs carry over unchanged.

### Manual Installation

1. Download the latest release from the releases page
2. Extract the `noaa_tides` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to Settings > Devices & Services
2. Click "Add Integration" and search for "NOAA Tides"
3. Select your preferred data source:
   - NOAA Station: For coastal stations with tidal data
   - NDBC Buoy: For offshore marine observations
4. Enter your station/buoy ID
5. Configure additional options:
   - Name: Custom name for the station
   - Time Zone: Select preferred time zone display
   - Unit System: Choose metric or imperial units
   - Update Interval: Set data refresh frequency
   - For NDBC buoys: Select desired data sections
6. Choose available sensors from the discovered list

## Finding Your Station/Buoy ID

### NOAA Stations
Visit the [NOAA Tides and Currents Map](https://tidesandcurrents.noaa.gov/map/) to find your station. NOAA operates nearly 500 stations with real-time data in the U.S., Caribbean, and Pacific territories. Alongside these physical stations, NOAA provides thousands of virtual stations that offer localized tide and current predictions, providing comprehensive coverage of coastal areas. Different stations support various data types:
- [Tide Predictions](https://tidesandcurrents.noaa.gov/map/index.html?type=tidepredictions)
- [Current Predictions](https://tidesandcurrents.noaa.gov/map/index.html?type=currentpredictions) (experimental)
- [Meteorological Observations](https://tidesandcurrents.noaa.gov/map/index.html?type=meteorological)
- [Real Time Currents](https://tidesandcurrents.noaa.gov/map/index.html?type=currents)
- [Conductivity](https://tidesandcurrents.noaa.gov/map/index.html?type=conductivity)

### NDBC Buoys
Use the [NDBC Station Map and Buoy Finder](https://www.ndbc.noaa.gov/obs.shtml?type=oceans&status=r&pgm=IOOS%20Partners|International%20Partners|Marine%20METAR|NDBC%20Meteorological%2FOcean|NERRS|NOS%2FCO-OPS&op=&ls=n) to locate your buoy.
The NDBC and it's partners operate nearly 1000 active buoys and coastal stations worldwide, with particularly extensive coverage in U.S. coastal waters, the Great Lakes, and Alaska.
<!-- narrow map parameters with further testing -->

## Data Interpretation

### Tide Predictions
- **Tide State**: Indicates if tide is rising or falling and the time
- **Tide Factor**: Sinusoidal representation of tide level (0-100%) that follows the natural curve of tidal change, with slower changes near high/low tides and faster changes at mid-tide levels.
- **Tide Percentage**: Linear representation of tide progress (0-100%) that moves at a constant rate between tides, making it perfect for tide clocks and calculating exact timing of tidal events.

### Current Predictions
- **Current State**: Shows ebb, flood, or slack water
- **Direction**: Compass bearing of water movement
- **Speed**: Current velocity

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Support

For bugs and feature requests, please [open an issue](https://github.com/netFusion-Solutions/HA_Noaa_Tides/issues) on GitHub.

<!--

## Sample configuration

![Configuration step 1](/images/config1.png)
![Configuration step 2](/images/config2.png)
![Configuration step 3](/images/config3.png)

## Usage

Once configured, the NOAA Tides integration will create a device/hub for the station and sensor entities that provide tide data, and other station data. You can use these sensors in your automations, scripts, and dashboards.

Tide factor is used to create a sinusoidal wave graph to represent the tide level when a station doesn't offer a water level sensor.

Tide percentage creates a linear graph and is useful for making something like a tide clock.


![Device page](/images/device_page.png)
![Tide state](/images/tide_state.png)
-->
