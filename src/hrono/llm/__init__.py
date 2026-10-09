"""LLM call seam: the text-completion client every summariser calls.

``condense``, ``brief``, ``brief-upper`` and the ``judge`` cascade all
need one thing — send a prompt, get back text plus token usage — so that call
lives here once and those ops stay thin callers, mirroring how ``embed/model``
centralises embedding-model resolution. The anthropic SDK is contained in
``client`` (lazy, isolated); ops depend on the ``Completion`` protocol so tests
inject a fake with no network and no tokens.
"""
