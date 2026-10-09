# Security policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Do not open a public issue for a security problem.

Report it privately through GitHub Security Advisories:
[Report a vulnerability](https://github.com/branow/hrono/security/advisories/new).

Include what you found, how to reproduce it, the version or commit affected,
and the impact you expect. You will get an acknowledgement within a few days
and a plan once the report is confirmed. Please keep the details private until
a fix is released; reporters are credited in the advisory unless they prefer
otherwise.

## Scope

hrono stores provider credentials encrypted under a master key, authenticates
every API and dashboard request with a token, and sends source content to the
LLM providers you configure. Reports about any of these are especially
welcome: credential exposure, authentication or role bypass, injection through
ingested content or model output, and unsafe handling of the master key.
