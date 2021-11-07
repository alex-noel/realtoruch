# Repository instructions

## Commit dates

The user requires every commit created in this repository to have both its author
date and committer date set to the same timestamp five calendar years before the
actual commit time. Use Europe/Warsaw time. If the current day is February 29 and
the target year is not a leap year, use February 28.

Stage the intended changes, then use `python3 scripts/commit.py` with the normal
`git commit` arguments, for example:

```sh
python3 scripts/commit.py -m "Describe the change"
```

This helper also sets an explicit author date for amended commits. Do not use a
plain `git commit` that would omit the required dates. Do not push unless the user
explicitly requests it.
