# Releasing

## Before tagging

```bash
python3 -m pytest -q                                  # all tests
python3 -m ruff check src tests benchmark             # lint
python3 -m mypy src                                   # types
python3 -m pytest --cov=indic_namematch --cov-fail-under=100 -q
python3 benchmark/evaluate.py               # benchmark reproduces published numbers
```

Then check the mutation sweep still bites, because coverage alone does not prove the tests
would notice a change:

```bash
cp src/indic_namematch/matchers.py /tmp/mb.py
sed -i '' 's/^PHONETIC = 0.95$/PHONETIC = 0.93/' src/indic_namematch/matchers.py
python3 -m pytest -q          # MUST fail
cp /tmp/mb.py src/indic_namematch/matchers.py
```

## Cutting the release

1. Bump `version` in `pyproject.toml` and `__version__` in `src/indic_namematch/__init__.py`.
   They are asserted to agree by the test suite via the changelog check.
2. Move the `Unreleased` heading in `CHANGELOG.md` to the new version with today's date.
3. Commit, tag, push:
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push && git push --tags
   ```

## Building and publishing

```bash
rm -rf dist build
python3 -m build
python3 -m twine check dist/*
```

Verify the wheel in a throwaway environment before uploading. Installing the package you
just built, in an environment that has nothing else in it, is the only way to catch a
missing module or a broken entry point:

```bash
python3 -m venv /tmp/verify && /tmp/verify/bin/pip install dist/*.whl
/tmp/verify/bin/indic-namematch "S. Kumar" "Suresh Kumar"
/tmp/verify/bin/python3 -c "from indic_namematch import NameMatcher; print(NameMatcher().score('Kumar Suresh','Suresh Kumar'))"
```

Upload to TestPyPI first, install from there, then release:

```bash
python3 -m twine upload --repository testpypi dist/*
python3 -m twine upload dist/*
```

## Versioning

Semantic versioning, with one project-specific rule: **any change that moves a published
score is at minimum a minor bump**, even when the public API is untouched. Downstream users
calibrate thresholds against these numbers, so a score change is a breaking change to them
whatever the type signatures say.
