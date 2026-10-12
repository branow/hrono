"""The Demo page's harness: an agent answering from a tree, step by step.

In real use the agent runs in the user's project. The plugin's hook attaches
recall to each prompt, and the agent reads the exported map and the source
files from its own checkout with its own file tools. None of that is visible
from outside. This package runs the same steps on the server, where each can
be shown as it happens: the recall that was attached, every page and file the
agent opened, and its answer.

- ``tools``: the two stand-in tools, ``open_topic`` and ``open_source``.
- ``prompts``: what the agent is told, and the recall attachment.
- ``steps``: what a turn is shown as, and where its steps are kept.
- ``agents``: one loop per provider kind, each emitting steps.
- ``session``: a conversation, and the turn that ties them together.
"""
