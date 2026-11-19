# Vectorworks palette integration

## User entry point

The installed Vectorworks plug-in provides `Tools > RigCalc > Open RigCalc`.
It opens one dockable RigCalc palette.  The palette owns the layer scope and
calculation controls, and has an explicit **Calculate** / **Recalculate**
action.  It never changes the drawing merely by opening.

## Boundary to the calculation core

`rigcalc.palette.build_palette_run` is the UI boundary after a completed
calculation.  It produces a serializable `snapshot` for the palette plus a
live `object_refs` index that remains only in Vectorworks' Python process.
The snapshot has a row for every discovered hoist, including uncalculated
hoists with `0.00 kN` and an explicit reason.

`rigcalc.vw.palette_session` stores only the most recently completed run.
The Vectorworks SDK bridge must use `PaletteRun.source_ref(object_id)` for
selection and zoom.  It must not attempt to reconstruct handles from JSON,
and must clear the session when its document or palette closes.

## Palette commands

Implemented in `PaletteSnapshotProvider` (see [`sdk/README.md`](../sdk/README.md)):
`GetSnapshot`, `Calculate`, `SaveSettings`, `ShowObject`, `RenameHoist`.

Planned, not yet implemented:

- `select_load`: select an input load identified by `source_id` in a hoist
  row.
- `open_warning`: select the warning's support, or locate the warning station
  on its construction.

Where the palette's files are stored is described in
[`data-locations.md`](data-locations.md).

## Association overrides

Resolving an ambiguous carrier is a drawing change.  A future bridge must
persist the chosen carrier as a named, auditable Vectorworks record or
connection—not merely a browser-side preference—and force a full recalculation
after the change.  Until then, ambiguous geometry remains a fail-closed,
visible zero calculation outcome.
