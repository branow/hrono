"""The first run, as a path a person can follow without a terminal.

A fresh install has nothing registered. What it needs to reach a built tree is
a connection, models, a source and a build; this package holds what that path
knows that the registry does not — the default models per provider, what a
source's filter would keep, and what a build would cost — and `server/ui/setup`
draws it. Every write goes through the registry engine, the same one Settings
and the API use.
"""
