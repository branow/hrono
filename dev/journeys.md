# User journeys

What must work end to end on the real app, as its users do it. The PO plans
from these, qa drives them, and the run is satisfied only when the ones in
its goal work. One line each; add every piece of user feedback as a journey
or a line under one, so it is checked on every later run.

- J1 An admin installs from source, creates a key, starts `hrono serve`, and
  sees the bootstrap token once and the resolved database path.
- J2 An admin, from an empty install, is walked by the dashboard's Set up page
  from a connection to a built tree without the CLI, seeing an estimate of
  calls, cost and time before the first build.
- J3 An admin registers a connection, models and a git source from the CLI,
  runs `hrono tree maintain`, follows it with `hrono jobs watch`, and gets a
  built tree.
- J4 After a source commit, a curator runs `hrono tree sync` and sees only the
  changed sections re-placed and only their briefs rewritten, with the calls
  it cost.
- J5 An agent or reader runs `hrono recall` (or Ask in the dashboard) and gets
  the passages that answer the question, with provenance.
- J6 A reader explores from the root brief down through topics to the files,
  on Map, Outline and Find, changing nothing and seeing no write controls.
- J7 A curator sees on Home whether the tree is up to date and what runs, and
  on Health what needs a person, and acts on it.
- J8 A curator corrects the tree by hand (edit a brief, move a section) and
  the edit survives the next sync.
- J9 An admin exports the tree as files an agent reads, and the export answers
  architecture questions on a large unknown corpus better than the raw code.
- J10 An admin sees on Usage what each run cost, per model and provider,
  under metered, subscription and mixed setups.
- J11 An admin manages users and tokens, and recovers a lost token with
  `hrono admin reset-token`.
