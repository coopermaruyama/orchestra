"""
Plancheck Extension for Orchestra

Monitors ExitPlanMode tool usage and handles plan detection and review blocking.
All checkpoint creation is handled by TimeMachine extension via session state communication.
"""

from .plancheck_monitor import PlancheckMonitor

__all__ = ["PlancheckMonitor"]