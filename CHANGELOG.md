# Changelog

All notable changes to RigCalc are documented in this file.

## Unreleased

### Added

- Dockable Vectorworks 2027 palette (C++ SDK plug-in, `sdk/`) with motor
  list, warnings, run history, calculation settings, motor ID editing and
  show-in-drawing.
- Per-drawing project store, `<drawing>.rigcalc/`, with `latest/` reports and
  an immutable copy of every completed run in `runs/`.
- Tension-only hoist cable modelling.
- `AGENTS.md` project rules shared by all AI coding assistants, and
  `docs/data-locations.md` listing every file RigCalc reads or writes.
- Linear continuous-beam analysis and corotational 3D frame analysis.
- Solver-result comparison and selection of a validated primary calculation.
- Mechanical cross sections from Vectorworks XML, including capacity data.
- Support for Hanging Positions, dead hangs, Truss Cross objects, and layer
  filtering.
- Automatic Hoist IDs, High Hook writeback, and Truss Cross writeback.
- Load, deflection, and internal-force notifications in dedicated Vectorworks
  classes.
- Progress reporting, cancelable execution, and a consolidated run summary.
- A diagnostic inventory and normalized data contract for development.
- Tests for geometry, normalization, solvers, writeback, and notifications.

### Changed

- Truss self-weight is now a distributed load over its station interval;
  result validation and load transfer fail closed for uplift, diagnostic
  nonlinear solutions, and cyclic construction graphs.
- The documented solver scope is a planar vertical open-chain beam model;
  the nonlinear corotational result is diagnostic-only.
- Connections, stationing, and distance checks now use 3D geometry.
- Ambiguous or geometrically impossible connections remain visible as explicit
  issues.
- Generated reports now include calculations, solver comparison, and
  writeback results.

- Reports for a saved drawing go to its project store; the repository's
  `output/` folder is only a fallback for unsaved drawings.
- SDK build output moved out of the shared Dropbox folder to
  `%LOCALAPPDATA%\RigCalc\SdkBuild`.

### Removed

- Unused run-summary dialog (the palette shows the run summary).
- Unused palette snapshot copy in `%APPDATA%`, the SDK protocol prototype, and
  leftover files from the Vectorworks SDK sample project, including the
  non-building Xcode project.
- Cursor-specific rule files, replaced by `AGENTS.md`.

### Security

- Calculations remain experimental and must be reviewed by qualified personnel
  before they are used for rigging or lifting decisions.
