# RigCalc agent rules

These are the project rules for every AI coding assistant and human
contributor. This file is the single source; `CLAUDE.md` and `GEMINI.md` only
import it. Change rules here, never in a tool-specific copy.

RigCalc reads rigging geometry from Vectorworks Spotlight, calculates truss
loads in Python, writes results back to the drawing, and shows them in a C++
SDK palette. Results feed safety-critical rigging decisions: when unsure,
fail closed and report the uncertainty instead of guessing.

## Structural calculation policy

- The product goal is to calculate every construction geometry found in scope:
  level, inclined, vertical, curved, inverted, branched, closed, and true 3D.
  Unsupported geometry is a temporary implementation gap, never an accepted
  product scope boundary. Record the gap explicitly and create or maintain its
  GitHub issue (see `docs/solver-roadmap.md`).
- Geometry is the authoritative basis for associating trusses, hoists, dead
  hangs, and loads. Vectorworks system links are strong positive evidence and
  may accelerate association, but their absence must not exclude an object.
  Preserve the association method, distances, confidence, and ambiguity in
  the model and report.
- Always calculate and report the unconstrained/signed structural result,
  including uplift, underload, negative reactions, and signed deflection.
  A unilateral/tension-only physical solution must additionally model slack
  and re-engagement; it must not discard the diagnostic result merely because
  a support is infeasible.
- Hoist and chain mass (`WeightWithChain`) always ends in the top hook,
  whatever the hoist orientation (`Hoist Up` or `Hoist Down`). It is never a
  truss load: High Hook = truss reaction + `WeightWithChain`, and the truss
  reaction alone decides whether a chain is taut or slack.
- Every discovered hoist receives an explicit outcome. If no load can be
  calculated, emit `0.00 kN` and a precise drawing/report reason (for example
  no viable carrier, too far from geometry, ambiguity, or insufficient
  supports). Never leave an unhandled hoist silent.
- Automatic writeback remains fail-closed: only a validated physical model is
  writeback eligible. Diagnostic forces and zero-force failure outcomes must
  be clearly distinguished from approved loads.

## Architecture

- `rigcalc/` is the Python calculation product. Only `rigcalc/vw/` may import
  the Vectorworks API (`vs`); model, topology, solver, palette and report code
  must run and be tested without Vectorworks.
- `sdk/vw2027/RigCalcPalette/` is the C++ host: menu command, web palette,
  selection/zoom. It must never implement structural calculations. The
  palette's **Calculate** runs the Python menu command named exactly
  `RigCalc`; never rename it on one side only.
- Vectorworks handles never leave the running process: not in JSON, reports,
  or the web UI. Identify objects by UUID or RigCalc `object_id`.
- Every file location RigCalc reads or writes is listed in
  `docs/data-locations.md`. Do not add a new location without updating it.
  Paths shared by Python and C++ must be changed in both places together.

## Code and text conventions

- All user-facing text (dialogs, palette, reports, native bridge errors) is
  English. Keep code identifiers, file names and JSON formats stable.
- Python must stay compatible with 3.9 (CI) and run on Vectorworks' bundled
  Python. The project has no third-party runtime dependencies; do not add any
  without asking.
- Never commit generated reports, Vectorworks drawings, `.rigcalc` project
  stores, build output, credentials, or project-specific customer data.

## Tests

- Tests use `unittest` only. Pytest is not installed and bare `test_*`
  functions are never collected; write `unittest.TestCase` classes.
- Run from the repository root:

  ```powershell
  .venv\Scripts\python.exe -B -m unittest discover -s tests
  ```

- Add or update tests for any behavior that can run outside Vectorworks, and
  run `git diff --check` before handing work over.

## Vectorworks and palette deployment

- Never start, close, or restart Vectorworks automatically. Ask the user to
  save and close the drawing first, because it may contain unsaved work.
- A successful SDK build alone does not update the palette Vectorworks uses.
  After changing `sdk/vw2027/RigCalcPalette`, build it (command in
  `sdk/README.md`), then deploy only after the user confirms Vectorworks is
  closed.
- Deploy only the successful `Release|x64` build from
  `%LOCALAPPDATA%\RigCalc\SdkBuild\Plug-Ins\Release`. Never deploy a Debug
  `.vlb`: the regular installation is a Release host and a Debug module can
  crash Vectorworks while plug-ins load.
- Deployment targets for Vectorworks 2027:
  - `RigCalcPalette.vlb` to
    `%APPDATA%\Nemetschek\Vectorworks\2027\Plug-ins\RigCalc\`
  - palette resources to
    `%APPDATA%\Nemetschek\Vectorworks\2027\Plug-ins\Data\RigCalcPalette\`
- `%APPDATA%\Nemetschek\Vectorworks\2027\RigCalc\` holds runtime control
  files, not plug-in files. Never deploy into or clean that folder.
- Verify deployment in the running palette, not merely by build success or
  source inspection: the expected new control or tab is visible and its native
  bridge command responds.
- Automatic writeback changes the open drawing. Validate new behavior on a
  copy of a drawing, following `docs/vectorworks-final-run-validation.md`.
