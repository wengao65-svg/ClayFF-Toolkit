# Contributing to ClayFF-Toolkit

Thank you for helping improve ClayFF-Toolkit. Bug reports, documentation,
tests, and code contributions are welcome through GitHub issues and pull
requests.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[gui]' pytest
python -m pytest
```

The GUI dependencies are optional. Core-only changes may use
`python -m pip install -e . pytest`.

## Pull requests

- Keep changes focused and add tests for changed behavior.
- Run the relevant test suite before submitting.
- Document user-visible behavior and parameter provenance.
- Do not commit proprietary Materials Studio force-field files or structures
  that cannot legally be redistributed.
- Record the source, exact version or commit, license, and any modifications
  for new third-party data.

## Developer Certificate of Origin

This project uses the Developer Certificate of Origin 1.1 instead of a
separate contributor license agreement. Sign off each commit with:

```bash
git commit -s
```

The sign-off certifies that you have the right to submit the contribution
under the project's license. The full DCO is available at
https://developercertificate.org/.

## License

Unless a file clearly says otherwise, contributions are accepted under the
Apache License 2.0. Third-party material keeps its original license and must
not be presented as a project contribution.
