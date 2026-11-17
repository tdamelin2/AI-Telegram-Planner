"""The four planners. Order here is the default speaking order."""
from .axiom import AXIOM
from .base import Persona
from .forge import FORGE
from .muse import MUSE
from .warden import WARDEN

ROSTER: tuple[Persona, ...] = (MUSE, WARDEN, FORGE, AXIOM)
BY_KEY: dict[str, Persona] = {p.key: p for p in ROSTER}
BY_NAME: dict[str, Persona] = {p.name.lower(): p for p in ROSTER}

__all__ = ["ROSTER", "BY_KEY", "BY_NAME", "Persona", "MUSE", "WARDEN", "FORGE", "AXIOM"]
