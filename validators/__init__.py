"""
Namespace package shim so imports like `validators.core` work both locally and in containers.

We keep source under vb_validators_dev/{core,energyplus,fmi} and extend __path__
to include that root so submodules can be resolved without moving files.
"""

from __future__ import annotations

import pathlib

# Allow `validators.<module>` to resolve to sibling directories under vb_validators_dev
__path__.append(str(pathlib.Path(__file__).resolve().parent.parent))  # type: ignore[name-defined]
