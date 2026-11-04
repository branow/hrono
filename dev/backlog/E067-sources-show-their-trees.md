# E067 The sources page says which tree reads each source

The Sources page lists every source of the server in one table, with no tree.
With two trees the user cannot tell which source belongs to which, and two
sources over the same repository look like a duplicate (seen on a real
install: a test tree's source beside the real one, same location).

- Each source row shows the trees that read it; a source no tree reads says so.
- The page can be filtered to one tree (the tree picker's tree by default),
  with a way to see all.
- Two sources over the same location are marked as such.
