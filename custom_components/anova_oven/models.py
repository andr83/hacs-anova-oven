"""Dataclass models for the Anova integration."""
from dataclasses import dataclass

from .precision_oven import AnovaPrecisionOven

# from .coordinator import AnovaCoordinator


@dataclass
class AnovaOvenData:
    """Data for the Anova integration."""

    access_token: str
    # coordinator: AnovaCoordinator
