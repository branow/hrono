# A maintain for a tree name nobody registered builds it anyway

Found by qa while gating E013. `POST /trees/{name}/maintain` and
`POST /ui/setup/build` with `tree=nope` both queue a maintain and it succeeds,
building topics and briefs (and paying for them) under a tree that is not in
the registry. Refuse with 404 when the tree is not registered.
