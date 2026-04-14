from typing import Literal, TypeAlias


TRIGGER_REASON_ON_DEMAND = "on_demand"
TRIGGER_REASON_CRON = "cron"

TriggerReasonValue: TypeAlias = Literal[
    TRIGGER_REASON_ON_DEMAND,
    TRIGGER_REASON_CRON,
]
