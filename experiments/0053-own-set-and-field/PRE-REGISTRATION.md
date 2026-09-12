# 0053 — Our own set, and the field our own team creates

**Written before the measurement was run.** Registered 2026-09-13.

## The defects

Two gaps in `matchup()`, which scores Team Preview and every switch decision:

1. **It never read our ability or item.** Ours are never hidden, yet every
   score treated our Pokemon as holding nothing and having no ability, and
   compared Speed on the raw stat — so an item's Speed multiplier and an
   ability that doubles Speed in its weather never counted.
2. **Team Preview modelled no field for its own side.** Only the opponent's
   predicted field existed (0048, off by default). A four containing a Pokemon
   that sets weather or terrain on arrival — including a Mega whose forme does
   — was scored on bare ground.

## Two changes, measured separately

| | change | flag |
| --- | --- | --- |
| **C** | our ability and item reach our attacks, their attacks on us, and our effective Speed; the battle's current values in switch scoring, the sheet's at Team Preview | `matchup_reads_our_set`, on |
| **D** | each candidate four at Team Preview is scored in the field its own setters create, the evolving holder's forme included | `own_field`, on |

Both are facts about our own team, so both ship unless they clear their
interval **downward** — the rule 0052's own-Mega change shipped under.

D's simplifications, stated so the result is not over-read:

- the field is treated as up for the whole matchup — no duration, no opposing
  setter taking it back;
- with two setters of the same kind in one four, the first in team order wins;
- where our setter decides a kind of field, the opponent's predicted effect of
  that kind is not applied.

## Instrument checks

| | C | D |
| --- | --- | --- |
| Team Preview picks differ, 380 previews | reported | reported |
| precondition | — (almost every set has an ability) | our team has an arrival setter |
| picks differ without the precondition | — | **must be 0** |
| in-battle decisions differ, 20 battles | reported | — (D is Team Preview only) |

## Predictions

| | C | D |
| --- | --- | --- |
| precondition holds | — | 50–85% of previews |
| picks differ | 20–60% | 10–40% |
| in-battle decisions differ | 1–8% | — |
| A/B, 400 battles | neutral to positive | neutral to positive |

## The canary

C changes in-battle switch scores, so unlike 0052 it may move the calibration
canary's scale for real. If it does, that is recorded and `experiments/0041`
re-run — not the canary's ranges widened.

## Hygiene

Pool teams and synthetic fixtures only.
