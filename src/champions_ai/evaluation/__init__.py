from champions_ai.evaluation.agreement import (
    AgreementResult,
    SlotComparison,
    action_signature,
    compare_agents,
    human_signature,
    measure_agreement,
)
from champions_ai.evaluation.differential import (
    DamageSample,
    DifferentialReport,
    active_by_ident,
    collect_samples,
    compare,
)
from champions_ai.evaluation.margin import (
    BattleMargin,
    MarginSummary,
    margin_from_sides,
    measure_side,
    relative_power,
    summarise,
)
from champions_ai.evaluation.runner import (
    BattleOutcome,
    MatchResult,
    evaluate,
    play_battle,
    wilson_interval,
)

__all__ = [
    "AgreementResult",
    "BattleMargin",
    "BattleOutcome",
    "DamageSample",
    "DifferentialReport",
    "MarginSummary",
    "MatchResult",
    "SlotComparison",
    "action_signature",
    "active_by_ident",
    "collect_samples",
    "compare",
    "compare_agents",
    "evaluate",
    "human_signature",
    "margin_from_sides",
    "measure_agreement",
    "measure_side",
    "play_battle",
    "relative_power",
    "summarise",
    "wilson_interval",
]
