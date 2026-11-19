# Data locations

This is the single reference for where RigCalc reads and writes files. When a
location changes, update this page, the code named in each section, and any
README or rule that links here.

## Overview

| What | Location | Owner | In Git |
| --- | --- | --- | --- |
| Source code | `RigCalc/rigcalc/`, `RigCalc/sdk/vw2027/` | Repository | Yes |
| Calculation reports, saved drawing | `<drawing>.rigcalc/latest/` | `rigcalc/vw/project_store.py` | No |
| Archived runs, saved drawing | `<drawing>.rigcalc/runs/<UTC timestamp>/` | `rigcalc/vw/project_store.py` | No |
| Calculation reports, unsaved drawing | `RigCalc/output/` | `rigcalc/vw/writer.py` | No (only `.gitkeep`) |
| Palette settings and run request | `%APPDATA%\Nemetschek\Vectorworks\2027\RigCalc\` | `rigcalc/vw/palette_bridge.py` and `PaletteSnapshotProvider.cpp` | No |
| SDK build output | `%LOCALAPPDATA%\RigCalc\SdkBuild\` | `RigCalcPalette.vcxproj` | No |
| Deployed SDK plug-in | `%APPDATA%\Nemetschek\Vectorworks\2027\Plug-ins\RigCalc\` and `...\Plug-ins\Data\RigCalcPalette\` | Manual deployment | No |
| Loader error log | `%TEMP%\VWDEV\rigcalc_error.txt`, `rigcalc_write_test_error.txt` | `loader.py`, `write_test_loader.py` | No |
| Braceworks cross sections (read only) | Vectorworks install and user `TrussCrossSectionData` folders | `rigcalc/solver/cross_sections.py` | No |
| Test drawings | `RigCalc/VW_Testfiles/` | Local only | No (ignored) |

## Project store: `<drawing>.rigcalc/`

A saved drawing `Show.vwx` gets a sibling folder `Show.rigcalc/`:

```text
Show.vwx
Show.rigcalc/
├── manifest.json            schema version and drawing path
├── latest/                  reports from the most recent run
│   ├── rigcalc_palette.json read by the SDK palette (written atomically)
│   ├── rigcalc_layer_selection.json  remembered layer scope and settings
│   └── rigcalc_*.json / *.txt        all other reports
└── runs/
    └── 2026-11-19_134000Z/  copy of latest/ after each completed run
```

- `latest/` is replaced on every run. `runs/` is never modified after it is
  written, and `rigcalc/palette/history.py` compares against the newest run.
- The palette only shows results for a saved drawing, because the C++ host
  finds `rigcalc_palette.json` from the active document's path.
- When the drawing is moved or renamed, move or rename its `.rigcalc` folder
  with it, or the palette starts without history.

## Development fallback: `RigCalc/output/`

Used only when the drawing has never been saved (`vs.GetFPathName()` is
empty). Nothing is archived and the palette cannot read it. It is not valid
evidence for `docs/vectorworks-final-run-validation.md`. Generated files are
ignored by Git, and the folder can be emptied at any time.

`WRITE_DEVELOPMENT_INVENTORY = True` in `rigcalc/config.py` additionally
writes `rigcalc_inventory.json` and `rigcalc_normalized.json` to the active
report directory.

## Per-user control files: `%APPDATA%\Nemetschek\Vectorworks\2027\RigCalc\`

| File | Written by | Read by |
| --- | --- | --- |
| `pending_settings.json` | Palette **Save settings** (C++) | Next Python run |
| `run_request.json` | Palette **Calculate** (C++) | Python; deleted when read |

These paths are hard-coded in both `rigcalc/vw/palette_bridge.py` and
`sdk/vw2027/RigCalcPalette/Source/RigCalc/PaletteSnapshotProvider.cpp`.
Change both together.
