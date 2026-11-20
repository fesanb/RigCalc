# RigCalc

[![Tests](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml/badge.svg)](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RigCalc reads rigging geometry from Vectorworks Spotlight, builds an
inspectable Python model, and performs preliminary structural analysis of
truss constructions. It calculates reactions, deflections, and internal
forces with a linear vertical continuous-beam model. A corotational 2D model
is also produced for diagnostic comparison, but is not an approved writeback
source. Validated linear results can be written back to Hoist and Truss Cross
objects in Vectorworks.

## Product calculation policy

RigCalc's product goal is to calculate every in-scope construction, regardless
of geometry: level, inclined, vertical, curved, inverted, branched, closed, or
true 3D. Current solver coverage is an implementation status, not a permanent
scope exclusion. A geometry that is not yet physically solved must still be
identified, diagnosed, and tracked to a concrete implementation issue.

Geometry is the authoritative source for associating trusses, hoists, dead
hangs, and loads. Vectorworks system links are useful evidence but are never a
requirement: missing or stale links must fall back to measured geometry with
recorded confidence and distance evidence.

Underload, uplift, negative reactions, and signed deflections are important
engineering diagnostics. RigCalc must preserve and report them, including the
amount and affected location. A physically admissible tension-only solution
must additionally account for chain slack and re-engagement; where it is not
available, writeback remains blocked but the diagnostic result is still
reported. Hoist and chain mass (`WeightWithChain`) always ends in the top hook,
whatever the hoist orientation: it is never a truss load, and High Hook = truss
reaction + `WeightWithChain`. Every discovered hoist must receive either a calculated result
or an explicit `0.00 kN` outcome with a clear drawing and report reason.

> [!WARNING]
> RigCalc is experimental software. Its results must not be used as the sole
> basis for safety-critical rigging or lifting decisions. Calculations and
> assumptions must be reviewed by qualified personnel.

## Installing in Vectorworks

RigCalc has two parts in Vectorworks. Both are needed on every machine.

### 1. The `RigCalc` menu command (Python)

The source code stays in this repository; Vectorworks only holds a small
loader, [`loader.py`](loader.py), as a menu command plug-in:

1. Open **Tools > Plug-ins > Plug-in Manager** and create a new
   **Menu Command** named exactly `RigCalc`, with Python as its language.
   The palette's **Calculate** button runs the command by that name, so it must
   not be renamed. It is saved as
   `%APPDATA%\Nemetschek\Vectorworks\2027\Plug-ins\RigCalc.vsm`.
2. Paste the complete contents of `loader.py` as its script.
3. Set `RIGCALC_REPO_DIR` near the top to this repository's folder, the one
   that contains `rigcalc/` and `loader.py`, not `rigcalc/` itself:

   ```python
   RIGCALC_REPO_DIR = (
       r"C:\Path\To\RigCalc"
   )
   ```

4. Add the command to the workspace if it should appear in a menu.

The loader validates the path and shows a clear error if
`rigcalc/__init__.py` cannot be found.

### 2. The RigCalc palette (C++ SDK plug-in)

Build and deploy `sdk/vw2027/RigCalcPalette` as described in
[`sdk/README.md`](sdk/README.md). It adds **Tools > RigCalc > Open RigCalc**.

## Development workflow

After installing the loader once:

1. Edit files under `RigCalc/rigcalc/` in VS Code.
2. Save the changes.
3. Run the `RigCalc` command, or **Calculate** in the palette.
4. The loader clears the import cache and runs the latest saved code.

Vectorworks normally does not need to be restarted, and the loader does not
need to be copied again for ordinary code changes. Update it only when
`loader.py` itself or the repository path changes.

## Output

Before writing reports, RigCalc displays a dialog containing the
calculation-relevant design layers. Only selected layers are included in the
geometry model. Select layers containing suspended structures and equipment,
and leave floor, storage, venue, and presentation layers disabled. The last
selection is remembered as a suggestion for the next run. A run started from
the palette's **Calculate** button reuses the remembered layers and skips the
dialog; if no layers have been chosen yet for the drawing, the dialog is shown.

A successful run writes its reports into the drawing's project store, a
`.rigcalc` folder next to the saved drawing:

```text
Show.vwx
Show.rigcalc/
├── manifest.json
├── latest/      reports from the most recent run
└── runs/        an immutable copy of latest/ for every completed run
```

An unsaved drawing writes to `RigCalc/output/` instead; that fallback is for
development only. [`docs/data-locations.md`](docs/data-locations.md) lists
every location RigCalc reads or writes.

Each run writes these files to `latest/`, without opening Notepad:

```text
rigcalc_geometry.txt / .json
rigcalc_cross_sections.json
rigcalc_calculation.txt / .json
rigcalc_nonlinear_calculation.txt / .json
rigcalc_solver_comparison.txt / .json
rigcalc_primary_calculation.txt / .json
rigcalc_hoist_ids.json
rigcalc_hoist_outcomes.txt / .json
rigcalc_layer_selection.json
rigcalc_palette.json
rigcalc_writeback.json
rigcalc_truss_cross_writeback.json
rigcalc_notifications.json
rigcalc_notification_writeback.json
rigcalc_run_summary.json
```

The TXT files are intended for quick human review. The JSON files contain the
detailed model for analysis and testing.

`rigcalc_palette.json` is the stable, user-interface-facing result snapshot.
It contains one row per discovered hoist, including High Hook and lower-hook
loads, contributing load evidence, result status, and visible warnings. It
never contains Vectorworks object handles. The SDK palette
(`Tools > RigCalc > Open RigCalc`, see
[`docs/vectorworks-palette.md`](docs/vectorworks-palette.md)) reads it from
`latest/` and resolves objects by UUID in the open drawing.

When development diagnostics are enabled, RigCalc also writes
`rigcalc_inventory.json` and `rigcalc_normalized.json`.
`rigcalc_inventory.json` is a read-only diagnostic inventory of every plug-in
object (`T=86`), including its plug-in type, layer, class, position, and all
associated records and fields. It is used to map Spotlight objects before
they enter the load model and does not modify the Vectorworks document.

`rigcalc_normalized.json` is the stable, calculation-facing data contract.
Every mass and connection retains its source field, original value, and any
data-quality warnings. Bare numbers without an explicit unit are not assumed
to be kilograms.

Full inventory and normalization diagnostics are disabled during normal runs
because they read every record and nested object and are not required for the
calculation. Set `WRITE_DEVELOPMENT_INVENTORY = True` in `rigcalc/config.py`
to regenerate these reports. A normal run uses a lightweight layer index and
reads detailed data only for selected calculation objects and Hanging
Positions.

During execution, Vectorworks displays progress for layer indexing, model
construction, linear analysis, and nonlinear analysis. The nonlinear phase
shows the construction, load percentage, and Newton iteration.

After the run, `rigcalc_run_summary.json` holds object counts, calculated
constructions, writeback results, released hoist supports, and objects that
could not be processed. The same summary is embedded in the palette snapshot.

Project stores live beside the drawings, outside the repository. Generated
files in `output/` are ignored by Git; `output/.gitkeep` keeps the folder
after cloning.

## Troubleshooting

A loader or RigCalc failure writes the complete traceback to:

```text
%TEMP%\VWDEV\rigcalc_error.txt
```

The isolated hoist write test (`write_test_loader.py`) uses
`%TEMP%\VWDEV\rigcalc_write_test_error.txt`. Vectorworks displays only a short
error message with the path to this file.
First verify that `RIGCALC_REPO_DIR` points to the correct `RigCalc` directory.

## Architecture

Only `rigcalc/vw/` may depend on the Vectorworks API. Model, topology, solver,
and report modules must remain importable and testable without Vectorworks.

The main data flow is:

```text
Vectorworks -> vw/scanner -> internal model -> topology -> solver -> report/writeback
```

The solvers and report modules are pure Python. `rigcalc/vw/` handles scanning,
dialogs, progress reporting, and all changes to the open Vectorworks document.

## Calculation and writeback

RigCalc groups connected truss into constructions and attaches hoists, dead
hangs, point loads, distributed loads, and Truss Cross objects. Mechanical
cross sections are read from Vectorworks data and converted to SI units.
Constructions without sufficient cross-section data or unambiguous geometry
are reported but do not receive writeback results.

The initial calculation-scope dialog also accepts a cable load in kg/m and a
global safety factor. Both values are remembered between runs. Cable load
defaults to zero and the safety factor defaults to 1.00. Cable load is applied as a
separate distributed load over the physical length of every selected line
truss. The safety factor is applied once to all scanned loads, including
cable, truss self-weight, equipment, hoist and chain, and bridle parts; a
transferred reaction is not factored again. Soft Goods use their total weight, distributed weight, length, and top
trim fields. Dead-hang rigging weight comes from the Bridle object's dynamic
`TotalWeight`, so changes made through Bridle Parts are reflected on the next
scan without a RigCalc-specific parts table.

The supported calculation scope is an open, collinear truss chain with vertical
gravity loads and vertical supports. Branched or looped topology, lateral
loads, torsion, corner blocks, and arbitrary 3D load paths are reported as
unsupported rather than analysed by the beam solver.

The implementation roadmap for every in-scope geometry is maintained in
[`docs/solver-roadmap.md`](docs/solver-roadmap.md). An unsupported result is a
tracked implementation gap, never an accepted product-scope exclusion.

The required Vectorworks evidence before closing policy-aligned implementation
work is captured in
[`docs/vectorworks-final-run-validation.md`](docs/vectorworks-final-run-validation.md).

The linear and corotational analyses are compared before a primary result is
selected. The corotational solver is diagnostic-only until it implements the
same tension-only hoist support model as the linear solver. Hoist supports that
would require a negative reaction are released and the system is solved again;
the original signed reaction remains in the report as uplift diagnostic data.
High Hook writeback requires a validated tension-only support state. For level
open chains the hoist contact states are enumerated exhaustively (up to eight
hoists): a released chain must be slack, meaning its pickup rises, and every
engaged chain must carry a non-negative reaction. High Hook is the truss
reaction plus `WeightWithChain`; a slack chain is written back as `0.00` and
marked with a SLACK CHAIN warning. All other geometry (inclined, vertical,
curved, cornered, branched, closed, 3D) uses the general 3D frame model with
the same tension-only rules. A rig on one or two hoists that would rotate
about its support line is written back from rigid-body statics with a ROTATES
warning. Forces in eligible structural Truss Cross connections are written
back in newtons.

The diagnostic corotational branch models distributed mass as a fixed global
vertical gravity load based on the undeformed station geometry; it is not a
follower load. Its assumptions and numerical status are written into the
calculation reports and it is never selected for automatic writeback.

Every discovered hoist also appears in `rigcalc_hoist_outcomes`. A supported,
validated result is marked `calculated`; a visible but writeback-blocked result
is `diagnostic_only`; and an unresolvable hoist is reported as `0.00 kN` with
its precise association or model reason. Zero outcomes are diagnostic markers,
not approved Vectorworks writeback values.

Writeback happens automatically during a normal run. Work in a copy or a
version-controlled Vectorworks document when validating new datasets.

## Bridles

Multi-leg bridles (`BridleObj`, two or three legs) are calculated from the
High Hook of the hoist hanging from the apex (`ConnectedHoistUUID`) plus the
bridle's own weight (`TotalWeight`, grams). Each leg is matched to the
`HouseRiggingPoint` whose plan position at the leg trim lies at the leg
length from the apex; leg tensions follow from equilibrium of the apex.
Results, with the Vectorworks leg forces for comparison, are written to
`rigcalc_bridles.json` and `rigcalc_bridles.txt`; leg overloads against
`ForceMaxLeg` and bridles that cannot be calculated get a marker. Four-leg
bridles are statically indeterminate and are reported, not calculated.
RigCalc replaces the Braceworks/Production Assist bridle result: for every
calculated bridle it writes `ForceLeg1..n` (N) to the `BridleObj` and the
summed leg forces `ForceX/Y/Z` (N) to each `HouseRiggingPoint`, under one undo
event, verifying every value by readback (`rigcalc_bridle_writeback.json`). A
house rigging point that also carries a leg of an uncalculated bridle is left
untouched.

## In-document notifications

After selecting the primary calculation, RigCalc checks the reaction at each
hoist against its rated capacity. A reaction above capacity creates a red
marker with white text near the hoist in the `RigCalc-Load` class. The marker
is a single text object without text wrapping or Tight Fill. Fill, fill
pattern, and pen color use By Class settings. New notification classes receive
default colors and a white pen when first created; RigCalc never modifies an
existing class.

The marker contains the warning type, hoist ID, and utilization on three
lines. Capacity is compared with the lower-hook reaction; hoist and chain mass
included in the High Hook value does not enter this capacity check.

RigCalc assigns an internal object name to generated markers. On the next run,
these markers are deleted and regenerated. User-created objects in
`RigCalc-Load` are preserved. Notification data and writeback results are
stored in `rigcalc_notifications.json` and
`rigcalc_notification_writeback.json`, respectively.

Calculation reports also contain vertical deflection at the midpoint of each
span between active supports, the maximum calculated deflection in each span,
and the maximum deflection for the entire construction. Each span receives an
informational orange marker in `RigCalc-Deflection`. No failure threshold is
currently applied because allowable deflection must be defined per project or
system.

Internal element forces are checked component by component against `MaxNx`,
`MaxVy`, `MaxVz`, `MaxMt`, `MaxMby`, and `MaxMbz` from the Braceworks
cross-section XML. A zero value is treated as a missing capacity. Exceedances
are grouped by section and displayed as blue markers in `RigCalc-Internal`.
The check does not assume an interaction equation between axial force and
moment.

## Running tests

From the `RigCalc` directory, using the Python runtime bundled with
Vectorworks 2027:

```powershell
& 'C:\Program Files\Vectorworks 2027\Python314\python.exe' -B -m unittest discover -s tests -v
```

`-B` prevents the tests from creating `__pycache__` files in the repository.

## Contributing and security

See [CHANGELOG.md](CHANGELOG.md) for notable changes and
[CONTRIBUTING.md](CONTRIBUTING.md) before proposing substantial work. Do not
publish vulnerabilities or sensitive project information in a public issue;
follow [SECURITY.md](SECURITY.md) instead.

## License

RigCalc is distributed under the [MIT License](LICENSE).
