ENDPOINT_TOLERANCE_MM = 100.0
COLLINEAR_LONGITUDINAL_TOLERANCE_MM = 300.0
COLLINEAR_LATERAL_TOLERANCE_MM = 50.0
COLLINEAR_ANGLE_TOLERANCE_DEG = 5.0
CORNER_TOLERANCE_MM = 100.0
ATTACHMENT_WARNING_DISTANCE_MM = 500.0
# Maximum 3D distance from a semantic hanging point to a carrier axis. An
# object outside this sphere remains unresolved; it is never attached merely
# because it is the nearest object in the drawing.
ATTACHMENT_SEARCH_RADIUS_MM = 500.0
ATTACHMENT_EXACT_DISTANCE_MM = 50.0

REPORT_BASENAME = "rigcalc_geometry"

# Development output lives beside the package so reports can be inspected
# directly from the shared repository after a Vectorworks run.
OUTPUT_DIRECTORY_NAME = "output"

# Full PIO records/nested diagnostics are expensive and are not required by
# calculation. Enable temporarily when investigating scanner/normalization data.
WRITE_DEVELOPMENT_INVENTORY = False
