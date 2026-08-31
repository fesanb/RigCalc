# RigCalc solver roadmap

The product goal is calculation coverage for every in-scope geometry.  This
table describes current implementation status; it is not a permanent scope
exclusion.  Every diagnostic or unsupported result remains visible and is
writeback-blocked unless a validated physical model explicitly proves it
eligible.

| Geometry or topology | Current result | Required implementation path | Tracking |
| --- | --- | --- | --- |
| Level, collinear, open chain | Linear signed beam diagnostic with exhaustive bounded fixed-point contact-state search. | Implement physical unilateral contact: slack, re-engagement, contact mass and scalable active-set solve. | #7 |
| Straight inclined planar open chain | Fixed-global-gravity frame diagnostic; signed reactions, active-set diagnostics and numerical evidence are reported. | Nonlinear planar contact equilibrium with the same physical cable model. | #7 |
| Vertical truss chain | Explicit `unsupported_vertical_truss_geometry` diagnostic. | Axial/gravity load-path model and support semantics. | #6 |
| Curved or inverted chain | Explicit diagnostic through topology/geometry validation. | Curved-beam or segmented geometric-nonlinear model. | #6 |
| Branched construction | Explicit `requires_branched_or_loop_solver` diagnostic. | Graph/frame assembly with branch support conditions. | #6 |
| Closed construction | Explicit `requires_branched_or_loop_solver` diagnostic. | Closed-frame compatibility and redundant-reaction model. | #6 |
| Non-collinear planar turns | Explicit non-planar/turn diagnostic. | Planar frame topology and corner-block connection model. | #6 |
| True 3D load path, torsion or lateral load | Explicit diagnostic; no beam writeback. | Validated 3D frame/contact model with load-direction semantics. | #6 |

## Common acceptance gate

Before any row becomes writeback eligible it must preserve the signed
unconstrained diagnostic, solve the physically admissible support/contact
state, report numerical and equilibrium evidence, and pass independent
benchmarks.  The final Vectorworks integration evidence is tracked in #8.
