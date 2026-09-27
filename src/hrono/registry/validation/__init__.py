"""Write-time validators: can we actually reach and authenticate this?

One folder because they share a shape, not a base class — each is a function a
`Descriptor` hangs on its `validate` hook, and each reaches OUT (a git remote,
a provider endpoint, a model load) where everything else in `registry/` only
touches the row. That is the boundary worth a folder: the modules here are the
ones that can be slow, can be offline, and need a seam in their tests.
"""
