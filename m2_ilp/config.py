"""Shared constants and the frozen model configuration (Lead, req 2.7).

Standard library only, so every M2 module can import it without cycles.
Derive variants with dataclasses.replace(config, stage=2, t_cap=t).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


TEAM_ID = "CO2011-261-A01-2551896"
DEFAULT_AVAILABILITY = "seeded"
AVAILABILITY_MODES = ("shift", "day", "seeded")
M2_DIR = Path(__file__).resolve().parent
SOFT_NAMES = ("location", "fatigue", "travel")


@dataclass(frozen=True)
class ModelConfig:
    stage: int = 1
    t_cap: int | None = None
    use_soft: bool = True
    relax_integrality: bool = False
    drop_overlap: bool = False
    elastic: bool = False
    elastic_penalty: float = 1000.0
    fatigue_k: int = 3
    weight_scale: tuple = (1.0, 1.0, 1.0)
    l1_chord: bool = True
    time_limit: int = 120
    gap_rel: float = 0.0
    threads: int = 1
    msg: bool = False

    def __post_init__(self):
        if self.stage not in (1, 2):
            raise ValueError("stage must be 1 or 2")
        if self.t_cap is not None and (isinstance(self.t_cap, bool) or self.t_cap < 0):
            raise ValueError("t_cap must be a non-negative number or None")
        for name in ("use_soft", "relax_integrality", "drop_overlap", "elastic", "l1_chord", "msg"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be True or False")
        if type(self.fatigue_k) is not int or self.fatigue_k < 0:
            raise ValueError("fatigue_k must be a non-negative integer")
        if len(self.weight_scale) != 3 or any(s < 0 for s in self.weight_scale):
            raise ValueError("weight_scale needs three non-negative factors")
        object.__setattr__(self, "weight_scale", tuple(float(s) for s in self.weight_scale))
        if self.elastic_penalty <= 0 or self.time_limit <= 0 or self.threads < 1:
            raise ValueError("elastic_penalty, time_limit and threads must be positive")

    def lambdas(self, inst) -> tuple[float, float, float]:
        """(lambda_LOC, lambda_FAT, lambda_TRV) = inst.soft_weights * weight_scale."""
        return tuple(w * s for w, s in zip(inst.soft_weights, self.weight_scale))
