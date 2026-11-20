# RigCalc solver roadmap

The product goal is calculation coverage for every in-scope geometry.  This
table describes current implementation status; it is not a permanent scope
exclusion.  Every diagnostic or unsupported result remains visible and is
writeback-blocked unless a validated physical model explicitly proves it
eligible.

| Geometry or topology | Current result | Required implementation path | Tracking |
| --- | --- | --- | --- |
| Level, collinear, open chain | Linear signed beam result plus exhaustive tension-only contact-state search (released hoist must rise; hoist/chain mass always in the top hook, never on the truss). Writeback eligible when the contact state, equilibrium and numerics validate. | Scalable active-set solve beyond 8 hoists (currently `tension_only_active_set_limit_exceeded`); Vectorworks validation (#8). | #7 |
| All other geometry: inclined, vertical, curved (Circle), corners, branched (T/X), closed (rings, grids), true 3D | General 3D frame model (`general_frame.py`): members discretised at every end, support, load and support-span midpoint; arcs as short chords on the resolved centreline; corner blocks as a node at the member-axis intersection. Hoists are tension-only vertical supports solved by an active set with exact complementarity; sway/roll stabilisers (chain pendulum stiffness, weak rotational springs) must carry negligible force or writeback is blocked (a rig on two hoists that would rotate is reported, not calculated). Writeback and load transfer eligible when contact state, equilibrium, numerics and stabiliser checks pass. | Vectorworks validation of each geometry class on the test drawing (#8); bridle legs (#1); horizontal loads/torsion inputs. | #6 |
| Straight inclined open chain, nonlinear | Corotational tension-only cable model (diagnostic cross-check in `rigcalc_nonlinear_calculation`). | Compare against the general frame on the test drawing. | #7 |

## Common acceptance gate

Before any row becomes writeback eligible it must preserve the signed
unconstrained diagnostic, solve the physically admissible support/contact
state, report numerical and equilibrium evidence, and pass independent
benchmarks.  The final Vectorworks integration evidence is tracked in #8.
