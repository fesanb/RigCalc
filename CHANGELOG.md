# Changelog

All notable changes to RigCalc are documented in this file.

## Unreleased

### Added

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

### Security

- Calculations remain experimental and must be reviewed by qualified personnel
  before they are used for rigging or lifting decisions.
