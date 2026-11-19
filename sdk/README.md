# RigCalc Vectorworks SDK plug-in

This directory is intentionally separate from `rigcalc/`.

`rigcalc/` is the Python calculation product: it scans Vectorworks via the
loader, builds the model, solves it, and writes auditable reports. `sdk/` is
the C++ Vectorworks host. It owns the `Tools > RigCalc > Open RigCalc` menu
command, the dockable web palette, selection/zoom, and palette lifetime. It
must never implement structural calculations.

## Layout

| Path | Status |
| --- | --- |
| `vw2027/RigCalcPalette/RigCalcPalette.sln` | Visual Studio solution (Windows, Release x64). |
| `vw2027/RigCalcPalette/Source/ModuleMain.cpp` | Registers the menu command and palette with Vectorworks. |
| `vw2027/RigCalcPalette/Source/RigCalc/` | Menu command, web palette and `PaletteSnapshotProvider` (all JavaScript-callable commands). |
| `vw2027/RigCalcPalette/Source/Prefix/` | Precompiled header that includes the Vectorworks SDK. |
| `vw2027/RigCalcPalette/RigCalcPalette.vwr/` | Resources packed into `RigCalcPalette.vwr`: palette UI (`html/index.html`) and menu strings (`Strings/RigCalc.vwstrings`, UTF-16). |

The plug-in is Windows-only. It also needs the separate Python `RigCalc` menu
command; see "Installing in Vectorworks" in the main README.

## Boundary to Python

All file locations are described in
[`../docs/data-locations.md`](../docs/data-locations.md). In short:

- Python writes the result to `<drawing>.rigcalc/latest/rigcalc_palette.json`
  next to the saved drawing. The palette reads that file and has no result for
  an unsaved drawing.
- The palette writes `pending_settings.json` and `run_request.json` in
  `%APPDATA%\Nemetschek\Vectorworks\2027\RigCalc\`; Python reads them on the
  next run.

Commands that `PaletteSnapshotProvider` exposes to the web UI:

| Command | Effect |
| --- | --- |
| `GetSnapshot` | Read `rigcalc_palette.json` for the active saved drawing and report whether the drawing is newer than the result. |
| `Calculate` | Write `run_request.json` and run the `RigCalc` script menu command. |
| `SaveSettings` | Validate and store cable load and safety factor for the next run. |
| `ShowObject` | Select and show a hoist by UUID. |
| `RenameHoist` | Change a hoist's `HoistID` after checking for duplicates in its truss system, then mark the result as stale. |

Live Vectorworks handles stay inside the open document process. They are never
written to the snapshot or passed into the web UI.

## Building

The installed SDK root is:

```text
C:\VectorworksSDK\2027\2027-NNA-eng-win-SDK\SDK\SDKVW(882699)
```

The bundled sample defaults to an old Windows SDK (`10.0.16299.0`) and C++
toolset lock (`v141` / `14.16.27023`). On this machine the working build uses
Visual Studio 2022 Build Tools, Windows SDK `10.0.26100.0`, and MSVC `v143` /
`14.44.35207`:

```powershell
& 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe' `
  'sdk\vw2027\RigCalcPalette\RigCalcPalette.sln' `
  /t:Build /p:Configuration=Release /p:Platform=x64 `
  /p:WindowsTargetPlatformVersion=10.0.26100.0 `
  /p:PlatformToolset=v143 /p:VCToolsVersion=14.44.35207 /m
```

Build output goes to `%LOCALAPPDATA%\RigCalc\SdkBuild\` (`Plug-Ins\Release`
holds the `.vlb` and `.vwr` to deploy). The project overrides the SDK default,
which would otherwise write about 850 MB into the shared Dropbox `Library`
folder above the repository.

Do not modify the installed SDK sample merely to make it build. Vendor files
and local Visual Studio folders (`vendor/`, `build/`, `.vs/`, `x64/`) are
ignored by Git.

## Deployment

Follow the deployment rules in [`../AGENTS.md`](../AGENTS.md): deploy only the
`Release|x64` build, only after the user has closed Vectorworks, and verify the
result in the running palette.

## Safety rules

- The palette shows a result only after a completed Python run.
- Object commands resolve UUIDs only in the active document.
- Direct/manual results and exempt motors are presentation-only; the SDK must
  not write their Vectorworks High Hook fields.
- Association choices made in the palette must be stored as explicit,
  auditable drawing data before the next calculation.
