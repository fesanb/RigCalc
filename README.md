# LoadCalc

LoadCalc currently converts Vectorworks rigging geometry into a standalone,
inspectable construction model. Mechanical reaction calculations are
intentionally not implemented yet.

## Vectorworks loader

Create a short Resource Manager Python script containing the contents of
`loader.py`, or point the existing development script at that file. The loader
adds this directory to `sys.path`, clears cached `loadcalc` modules, runs the
latest saved code, and writes full exceptions to `%TEMP%\VWDEV`.

Successful runs write directly into the repository:

* `output\loadcalc_geometry.txt`
* `output\loadcalc_geometry.json`

Top-level loader failures are still written to
`%TEMP%\VWDEV\loadcalc_error.txt`, so diagnostics remain available if writing
to the repository itself fails.

Only `loadcalc/vw/` accesses the Vectorworks API. The model, topology and report
formatting modules can be imported and tested in ordinary Python.

## Tests

Using the Python runtime bundled with Vectorworks 2026:

```powershell
& 'C:\Program Files\Vectorworks 2026\Python39\python.exe' -m unittest discover -s tests -v
```
