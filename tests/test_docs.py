"""Every number printed in the README must be real.

Documentation drifts silently: a tuning change moves a score, the README keeps the old
value, and the first person to try the example gets a different answer than advertised.
These tests parse the README and re-run every claim in it.
"""

from __future__ import annotations

import os
import re

import pytest

from indic_namematch import NameMatcher
from indic_namematch.matchers import REGISTRY

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()

TABLE_CLAIMS = re.findall(r"\|\s*`([^`]+)`\s*/\s*`([^`]+)`\s*\|\s*([01]\.\d+)\s*\|", README)
CODE_CLAIMS = re.findall(r'm\.score\("([^"]+)",\s*"([^"]+)"\)\s*#\s*([01]\.\d+)', README)
REGISTRY_CLAIMS = re.findall(
    r'REGISTRY\["(\w+)"\]\("([^"]+)",\s*"([^"]+)"\)\s*#\s*([01]\.\d+)', README
)


def test_the_readme_actually_contains_claims():
    """Guard against the regexes silently matching nothing after a README rewrite."""
    assert len(TABLE_CLAIMS) >= 10
    assert len(CODE_CLAIMS) >= 4
    assert len(REGISTRY_CLAIMS) >= 1


@pytest.mark.parametrize("a,b,claimed", TABLE_CLAIMS,
                         ids=[f"{a}|{b}" for a, b, _ in TABLE_CLAIMS])
def test_readme_table_scores(a, b, claimed):
    assert NameMatcher().score(a, b) == pytest.approx(float(claimed), abs=0.0005)


@pytest.mark.parametrize("a,b,claimed", CODE_CLAIMS,
                         ids=[f"{a}|{b}" for a, b, _ in CODE_CLAIMS])
def test_readme_code_examples(a, b, claimed):
    assert NameMatcher().score(a, b) == pytest.approx(float(claimed), abs=0.0005)


@pytest.mark.parametrize("name,a,b,claimed", REGISTRY_CLAIMS,
                         ids=[n for n, _, _, _ in REGISTRY_CLAIMS])
def test_readme_registry_example(name, a, b, claimed):
    assert REGISTRY[name](a, b) == pytest.approx(float(claimed), abs=0.0005)


def test_readme_explain_output_is_verbatim():
    """The printed explain() block is copied from real output, not written by hand."""
    block = re.search(r"```\n('Rajesh Kumar Sharma'.*?REVIEW)\n```", README, re.S)
    assert block, "the explain() sample block is missing from the README"
    actual = str(NameMatcher().explain("Rajesh Kumar Sharma", "Ramesh Kumar Sharma"))
    assert block.group(1).strip() == actual.strip()


def test_readme_documents_every_matcher():
    for name in REGISTRY:
        assert f"`{name}`" in README, f"{name} is registered but undocumented in the README"


def test_changelog_mentions_the_current_version():
    from indic_namematch import __version__

    changelog = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    assert f"[{__version__}]" in changelog
