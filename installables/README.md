# Included Python wheel

This is a Python package, not a standalone Windows executable. Install its declared dependencies in an isolated environment. The full pinned dependency installation was blocked in the build host; see artifacts/pass-08/environment.json.

The wheel core and embedded authority snapshot passed isolated no-dependency checks. The actual API was exercised from the installed wheel using separately available host API dependencies. No Windows or MSIX qualification is claimed.
