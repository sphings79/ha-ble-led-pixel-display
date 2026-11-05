# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private
vulnerability reporting instead: **Security → Report a vulnerability** on this
repository.

Include the affected version, how to reproduce the problem and what an attacker
could do with it. You will get a first answer within a few days, and the fix is
published before the details are.

## What counts

This integration talks to Bluetooth LE LED panels over the local radio. It
holds no cloud account and stores no credentials except the optional panel
password in the config entry options. Relevant reports are, for example,
actions that let a non-administrator do something only an administrator
should, or a way to read the stored panel password.

Problems in the panels' own firmware belong with the manufacturer; if you find
one, report it to them first.
