# RigCalc

[![Tests](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml/badge.svg)](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RigCalc reads rigging geometry from Vectorworks Spotlight, builds an
inspectable Python model, and performs preliminary structural analysis of
truss constructions. It calculates reactions, deflections, and internal
forces with both a linear beam model and a corotational 3D model. Validated
results can be written back to Hoist and Truss Cross objects in Vectorworks.

> [!WARNING]
> RigCalc is experimental software. Its results must not be used as the sole
> basis for safety-critical rigging or lifting decisions. Calculations and
> assumptions must be reviewed by qualified personnel.

## Migration from LoadCalc

The product directory and Python package have been renamed:

```text
LoadCalc/          -> RigCalc/
loadcalc/          -> rigcalc/
loadcalc_geometry  -> rigcalc_geometry
```

An old Vectorworks loader will not work after this change. Copy the complete
new `RigCalc/loader.py` into the Vectorworks script and verify that
`RIGCALC_REPO_DIR` points to the new `RigCalc` directory. This is a one-time
update.

## Vectorworks loader

The complete loader is located at:

```text
RigCalc/loader.py
```

This is the only project file that should be copied into the Vectorworks
Resource Manager. The RigCalc source code remains external in the Git
repository.

### Installing the loader

1. Open `RigCalc/loader.py` in a text editor.
2. Copy the entire file.
3. Create or open a Python Script resource in the Vectorworks Resource Manager.
4. Replace the existing script contents with the loader and save it.
5. Change `RIGCALC_REPO_DIR` near the top of the loader if the repository is
   stored elsewhere on the machine.

Example:

```python
RIGCALC_REPO_DIR = (
    r"C:\Path\To\RigCalc"
)
```

The path must point to the directory containing `rigcalc/`, `loader.py`, and
this README:

```text
VWDEV/
└── RigCalc/                  <-- RIGCALC_REPO_DIR points here
    ├── loader.py
    ├── README.md
    ├── rigcalc/
    │   └── __init__.py
    ├── output/
    └── tests/
```

Do not point it at `VWDEV` alone or at `RigCalc/rigcalc`. The loader validates
the path and displays a clear error if `rigcalc/__init__.py` cannot be found.

## Development workflow

After installing the loader once:

1. Edit files under `RigCalc/rigcalc/` in VS Code.
2. Save the changes.
3. Run the RigCalc script from Vectorworks.
4. The loader clears the import cache and runs the latest saved code.

Vectorworks normally does not need to be restarted, and the loader does not
need to be copied again for ordinary code changes. Update it only when
`loader.py` itself or the repository path changes.

## Output

Before writing reports, RigCalc displays a dialog containing the
calculation-relevant design layers. Only selected layers are included in the
geometry model. Select layers containing suspended structures and equipment,
and leave floor, storage, venue, and presentation layers disabled. The last
selection is remembered as a suggestion for the next run, but the dialog is
always displayed.

A successful run writes the following files without opening Notepad:

```text
RigCalc/output/rigcalc_geometry.txt
RigCalc/output/rigcalc_geometry.json
RigCalc/output/rigcalc_cross_sections.json
RigCalc/output/rigcalc_calculation.txt
RigCalc/output/rigcalc_calculation.json
RigCalc/output/rigcalc_nonlinear_calculation.txt
RigCalc/output/rigcalc_nonlinear_calculation.json
RigCalc/output/rigcalc_solver_comparison.txt
RigCalc/output/rigcalc_solver_comparison.json
RigCalc/output/rigcalc_primary_calculation.txt
RigCalc/output/rigcalc_primary_calculation.json
RigCalc/output/rigcalc_hoist_ids.json
RigCalc/output/rigcalc_writeback.json
RigCalc/output/rigcalc_truss_cross_writeback.json
RigCalc/output/rigcalc_notifications.json
RigCalc/output/rigcalc_notification_writeback.json
RigCalc/output/rigcalc_run_summary.json
```

The TXT files are intended for quick human review. The JSON files contain the
detailed model for analysis and testing.

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

After the run, Vectorworks displays a summary with object counts, calculated
constructions, writeback results, released hoist supports, and objects that
could not be processed.

Generated TXT and JSON reports are ignored by Git. `output/.gitkeep` ensures
that the output directory exists after cloning.

## Troubleshooting

A loader or RigCalc failure writes the complete traceback to:

```text
%TEMP%\VWDEV\rigcalc_error.txt
```

Vectorworks displays only a short error message with the path to this file.
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

The linear and corotational analyses are compared before a primary result is
selected. Non-converged nonlinear results are rejected. Hoist supports that
would require a negative reaction are released and the system is solved
again. Approved hoist reactions are written to the High Hook fields, and
forces in structural Truss Cross connections are written back in newtons.

Writeback happens automatically during a normal run. Work in a copy or a
version-controlled Vectorworks document when validating new datasets.

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
Vectorworks 2026:

```powershell
& 'C:\Program Files\Vectorworks 2026\Python39\python.exe' -B -m unittest discover -s tests -v
```

`-B` prevents the tests from creating `__pycache__` files in the repository.

## Contributing and security

See [CHANGELOG.md](CHANGELOG.md) for notable changes and
[CONTRIBUTING.md](CONTRIBUTING.md) before proposing substantial work. Do not
publish vulnerabilities or sensitive project information in a public issue;
follow [SECURITY.md](SECURITY.md) instead.

## License

RigCalc is distributed under the [MIT License](LICENSE).
