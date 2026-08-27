# Contributing to RigCalc

RigCalc is in an early experimental phase. Small, focused issues and pull
requests are welcome.

## Before submitting a change

1. Open an issue for substantial behavioral or architectural changes.
2. Keep Vectorworks API access inside `rigcalc/vw/`.
3. Add or update tests for behavior that can run outside Vectorworks.
4. Run the test suite with Python 3.9:

   ```powershell
   python -B -m unittest discover -s tests -v
   ```

5. Keep generated reports out of commits.

By contributing, you agree that your contribution is licensed under the MIT
License included in this repository.
