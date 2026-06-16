"""
Unit tests for the deep-link registry (utils/deep_links.py).

Offline/pure: validates the registry's integrity so a malformed or duplicated
raiz:// constant is caught before it wastes an on-device run. The navigation
suite trusts these constants point at distinct, well-formed screens.
"""
import re

import pytest

from utils.deep_links import DeepLinks, SCHEME

# raiz:// paths are lowercase words, digits, underscores and slashes (e.g.
# raiz_super/account_info, accounts/round_ups). Anything else is a typo.
_PATH_RE = re.compile(r"^[a-z0-9_/]+$")


def _link_constants():
    """All declared deep-link constants as (name, uri) pairs."""
    return [(name, value) for name, value in vars(DeepLinks).items()
            if name.isupper() and isinstance(value, str)]


@pytest.mark.unit
class TestDeepLinkRegistry:
    def test_scheme_is_raiz(self):
        assert SCHEME == "raiz://"

    def test_registry_is_not_empty(self):
        assert len(_link_constants()) >= 30, "Expected the full set of registered deep links"

    @pytest.mark.parametrize("name,uri", _link_constants(), ids=[n for n, _ in _link_constants()])
    def test_each_link_is_well_formed(self, name, uri):
        assert uri.startswith(SCHEME), f"{name} must start with {SCHEME!r}: {uri!r}"
        # raiz://<path> with no whitespace or trailing slash sloppiness
        path = uri[len(SCHEME):]
        assert path, f"{name} has an empty path: {uri!r}"
        assert uri == uri.strip(), f"{name} has surrounding whitespace: {uri!r}"
        assert " " not in uri, f"{name} contains a space: {uri!r}"
        assert _PATH_RE.match(path), f"{name} has an unexpected character in its path: {uri!r}"
        assert not path.startswith("/") and not path.endswith("/"), \
            f"{name} has a leading/trailing slash: {uri!r}"

    def test_no_duplicate_uris(self):
        """Each constant should map to a distinct screen — a duplicate is almost
        always a copy-paste bug in the registry."""
        uris = [uri for _, uri in _link_constants()]
        dupes = {u for u in uris if uris.count(u) > 1}
        assert not dupes, f"Duplicate deep-link URIs in the registry: {dupes}"

    def test_open_helper_is_callable(self):
        assert callable(DeepLinks.open)
