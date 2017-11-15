# Venter
Fusion 360 Addin to create vents quickly and easily

![Venter Cover](./resources/ventMaker_cover.png)


# Installation
[Click here to download the Add-in](https://github.com/tapnair/ventMaker/archive/master.zip)


After downloading the zip file follow the [installation instructions here](https://tapnair.github.io/installation.html) for your particular OS version of Fusion 360 


# Usage

Documentation to come later. For now:
 - Select a sketch point to use as the center of the vent.
 - The sketch point must lie on a planar face (not a reference plane)
 - The face of the sketch will determine the component for the feature
 - The vent will be cut normal to the face up to the next face it encounters.

# TODO / Enhancements:
- Add ability to rotate vent
- Add suppoprt for Blind and Through All end conditions
- Significantly better error handling
- Display Flow Area in proper units and calculate for circular
- Defer preview checkbox to handle slow updates
- Add more vent types and patterns

## License
Samples are licensed under the terms of the [MIT License](http://opensource.org/licenses/MIT). Please see the [LICENSE](LICENSE) file for full details.

## Written by

Written by [Patrick Rainsberry](https://twitter.com/prrainsberry) <br /> (Autodesk Fusion 360 Business Development)

See more useful [Fusion 360 Utilities](https://tapnair.github.io/index.html)

[![Analytics](https://ga-beacon.appspot.com/UA-41076924-3/ventMaker)](https://github.com/igrigorik/ga-beacon)
