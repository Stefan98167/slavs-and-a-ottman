"""Starter kit for the Tacto Negotiation Arena."""

from importlib import import_module

__all__ = [
    "ArenaClient",
    "ArenaError",
    "RemoteTable",
    "complete_offer",
    "must_haves_ok",
    "play",
    "play_all",
    "total_cost",
]


def __getattr__(name):
    """Load hosted components only when requested; local tools need no HTTP SDK."""
    modules = {
        "ArenaClient": "client", "ArenaError": "client",
        "RemoteTable": "play", "play": "play", "play_all": "play",
        "complete_offer": "cost", "must_haves_ok": "cost", "total_cost": "cost",
    }
    if name not in modules:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    # Importing play sets package.play to the submodule. Cache all its public
    # exports together so the historical `from arena_kit import play` stays a function.
    module = import_module(f".{modules[name]}", __name__)
    for export, owner in modules.items():
        if owner == modules[name]:
            globals()[export] = getattr(module, export)
    return globals()[name]
