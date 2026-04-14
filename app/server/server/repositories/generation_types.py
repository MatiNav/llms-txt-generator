from dataclasses import dataclass

from shared.constants.render_mode import RenderModeValue
from shared.models.run import Run


@dataclass(frozen=True)
class InflightRunSnapshot:
    run: Run
    root_render_mode: RenderModeValue | None
