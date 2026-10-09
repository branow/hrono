# The setup page's models step dead-ends on a default install

Found by qa while gating E013. A default `uv sync` leaves out the `embed` extra,
and the models step then refuses with "embedder: in-process embedding backend is
not installed", which tells nobody what to do and cannot be fixed from the
browser. Either say in the refusal how to install it (`hrono[embed]`) or check
for the backend before offering the step.
