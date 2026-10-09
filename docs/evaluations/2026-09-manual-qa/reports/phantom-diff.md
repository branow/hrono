# diff with the repos untouched, against each cache root

## driver cache (.hrono, cwd=.e2e)
- chalk: 0 changes
- itsdangerous: 1 changes
    new      src/itsdangerous/py.typed
- uuid: 0 changes

## server cache (run/.hrono, cwd=.e2e/run)
- chalk: 1 changes
    moved    source/utilities.js  (was source/util-helpers.js)
- itsdangerous: 3 changes
    changed  src/itsdangerous/signer.py
    new      docs/license.rst
    new      src/itsdangerous/py.typed
- uuid: 0 changes

## the perpetual one
- .hrono/cache/sources/itsdangerous/src/itsdangerous/py.typed: exists=True size=0 bytes
- stored sections for it: 0
