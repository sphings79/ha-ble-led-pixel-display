"""Just enough of Home Assistant to import the entity and API modules.

Home Assistant itself is not installed for the tests. ``install()`` puts
stand-in modules in ``sys.modules``: every name a module asks for resolves to
a plain class, so the integration's entities can subclass them, except the
few helpers that must behave like functions.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
import types


def _identity(func):
    return func


FUNCTIONS = {
    "callback": _identity,
}


async def _noop(self, *args, **kwargs):
    return None


# Methods the integration's entities chain to with super().
BASE_METHODS = {"async_added_to_hass": _noop, "async_will_remove_from_hass": _noop}


def _stub_class(name: str) -> type:
    return _StubMeta(name, (), dict(BASE_METHODS))


class _StubMeta(type):
    """Any attribute of a stub class (an enum member, a constant) is a stub."""

    def __getattr__(cls, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        value = _stub_class(name)
        setattr(cls, name, value)
        return value


class _StubModule(types.ModuleType):
    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        value = FUNCTIONS.get(name) or _stub_class(name)
        setattr(self, name, value)
        return value


class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    PREFIXES = ("homeassistant", "bleak_retry_connector", "aiohttp", "resvg_py")

    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in self.PREFIXES:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        module = _StubModule(spec.name)
        module.__path__ = []
        return module

    def exec_module(self, module):
        pass


def install() -> None:
    if not any(isinstance(f, _Finder) for f in sys.meta_path):
        sys.meta_path.insert(0, _Finder())


class FakeHass:
    """Records background tasks instead of scheduling them."""

    def __init__(self) -> None:
        self.tasks = []

    def async_create_background_task(self, coro, name=None):
        self.tasks.append(coro)
        return coro
