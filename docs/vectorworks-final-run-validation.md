# Vectorworks final-run validation

This is the manual evidence protocol for GitHub issue #8. It supplements the
automated test suite; it does not make a calculation result fit for use without
engineering review.

## Before running

- Use a copy of a representative Vectorworks 2027 document, never the working
  production drawing.
- Record the Vectorworks version, document name and version, RigCalc commit,
  date, operator, selected calculation layers, cable load and safety factor.
- Preserve the generated `<document-name>.rigcalc/latest` directory after the
  run. Each completed run is also copied to `<document-name>.rigcalc/runs/`.
  An unsaved document instead uses the repository's development `output`
  directory and is not suitable as final validation evidence.
- Capture before/after screenshots and the following output files:
  `rigcalc_run_summary.json`, `rigcalc_hoist_outcomes.json`,
  `rigcalc_primary_calculation.json`, `rigcalc_notifications.json`,
  `rigcalc_notification_writeback.json`, `rigcalc_writeback.json`, and
  `rigcalc_truss_cross_writeback.json`.

## Test record

Mark each item **Pass**, **Fail**, or **Not applicable**. A failure requires a
reproducible follow-up issue; do not close the implementation issue it affects.

| Check | Evidence required | Result |
| --- | --- | --- |
| Setup dialog | Screenshot shows document name (or unsaved state), candidate layer/object counts, previous scope visibly presented as a suggestion, mutation warning, engineering-review warning, and usable long-name/many-layer layout. Cancel and verify no detailed scan, report replacement or drawing mutation occurred. | |
| Notification markers | On a representative and a dense drawing, inspect hierarchy, units, identity and severity at normal drawing scale. Verify deterministic separation of collocated markers, preserved existing By Class styling, and that only RigCalc-owned markers are reconciled. | |
| Hoist outcomes | Reconcile every discovered hoist to `rigcalc_hoist_outcomes.json`. Each must be calculated, diagnostic-only, exempt, or show `0.00 kN` with a concrete association/model reason. Verify zero and diagnostic-only values are not written as approved loads. | |
| Association evidence | Exercise explicit ID, missing ID, and stale ID cases. Preserve and inspect association method, distance, confidence, ambiguity and nearest-carrier evidence in the reports. | |
| Eligible writeback | For one eligible level open chain, check High Hook and Truss Cross values, displayed units, undo behavior and readback report. Confirm diagnostic, uplift, invalid, cyclic and unresolved results remain read-only. | |
| Solver safety | Compare level-chain reactions and deflections with an approved independent reference. Confirm inclined diagnostics retain signed results and visibly block writeback. | |
| Bridle inventory | Capture Vectorworks 2027 Bridle/Bridle-part records, exact force field names and raw units. Do not implement or write Bridle-part forces from assumptions. | |

## Sign-off and closure

Attach the test record, output directory, screenshots, reference calculation
and any failure issues to GitHub issue #8. Include the commit hash and clearly
state which scenarios were not applicable. Close #2 or #3 only after their
respective manual checks pass. Keep #1, #6 and #7 open until their substantive
acceptance criteria are implemented and independently validated.
