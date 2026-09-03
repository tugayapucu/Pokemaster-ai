# Experiment 0030 — The richer evaluator does not help, and 0029 over-claimed

**Date:** 2026-09-01
> **Refined by 0034.** Swept rather than sampled, the scale curve peaks at
> roughly the setting this document used, so the conclusion was not the result
> of testing the wrong point. But the gain there is not reliably zero either:
> two cross-validation runs over the same data give +0.2pp (here) and +1.00pp
> (0034). "Small, and not stably estimated" is closer than "null". Nothing
> ships either way -- `evaluate_position` still has no production caller.
**Result: adding status, boosts, screens, Tailwind and Trick Room to `evaluate_position` is worth +0.2 points of winner prediction, with a standard deviation of 1.4 and a positive sign in four of eight splits.** A null. Experiment 0029 reported +3.0 held out and +4.4 against the shipped evaluator; both came from a **single split** of 307 replays. Cross-validated over 19,035 positions from 1,610 replays, the effect disappears. Backlog item 2 is closed, and by the stopping rule agreed before the work began, search is not re-opened on this basis.

## What 0029 got right and what it got wrong

**Right, and still standing:** self-play cannot measure these features. Screens are non-zero in **0.0%** of self-play positions and 7.8% of real ones; status 4.2% against 14.9%; Trick Room 3.8% against 13.8%. The agent does not use them, the self-play opponent is the agent, so a fit on self-play is reading a column of zeros. Human positions are the right instrument for this class of question, and that finding is unaffected.

**Wrong:** the conclusion drawn from that instrument. 0029 fitted one split and reported the gain as established.

```
0029, one split of 307 replays        +3.0pp held out, +4.4pp vs shipped
0030, eight splits of 307 replays     +1.2pp  sd 3.0pp   positive 6/8
0030, eight splits of 1,610 replays   +0.2pp  sd 1.4pp   positive 4/8
```

The first number was noise, and the tell was visible at the time: the gain was *larger* out of sample than in it, and the plain evaluator scored 53.5% on that holdout against 62.0% on the fit half — the two halves were simply not alike.

## This is the failure experiment 0004 documented

0004 recorded that its own first version published a false positive from a 600-battle run, and quoted 0003 warning about the same thing before it:

> *"The 200-battle run suggested 55.5%; at 800 it regressed to 51.6%. **The first number was noise**, and is recorded here because stopping at 200 would have produced a false claim."*

0004 then added: *"Writing down the lesson did not prevent repeating it; only re-running did."* That is now true three times. The lesson is not "be careful" — it is **cross-validate before writing the number down**, which costs one extra loop.

## The measurement

Fitted as `z = a * advantage + sum(w_k * new_k)`, so each `w_k / a` is that feature's worth in advantage units directly. Split by replay, refitted per split so the spread covers the weights too.

```
  plain  mean 63.9%   sd 1.4pp
  rich   mean 64.2%   sd 1.1pp
  gain   mean +0.2pp  sd 1.4pp   positive in 4/8 splits

  fitted weight (advantage units)      mean      sd/mean
    status                            128.5        0.20
    screens                            68.1        0.20
    defence                            28.6        0.10
    speed_stage                        24.3        0.23
    tailwind                           18.7        0.63
    offence                            11.6        0.29
    trickroom                          -1.9        2.08
```

**The weights are well determined and still do not help.** On 307 replays most of them were unstable (status 0.58, offence 0.95, speed_stage 0.89); with the full corpus they settle, and the accuracy does not move. So this is not "we could not fit them" — it is that the information is already carried by HP and living count, or is too small to change a sign.

The magnitudes are not absurd, which is worth noting: a slept Pokemon at 128.5 × 0.60 ≈ 77 advantage, against POKEMON_WEIGHT of 100, is roughly "three quarters of a Pokemon". The terms are sensible. They are simply redundant for predicting who wins.

## What this closes

- **Item 2 is a null.** The evaluator cannot be usefully improved by these features.
- **The stopping rule fires.** It was agreed before the work: improve the evaluator to a measured target first, re-test search second, stop if the first does not move. It did not move.
- **The plain evaluator is 63.9% on human positions**, against 74.6% on self-play (0028) and the 79.7% originally claimed (0021, on the wrong pool). Each re-measurement on a better instrument has lowered it.

## Not established

- Whether a *non-linear* model would find something these linear terms cannot. Nothing here rules that out; it rules out the hand-written terms item 2 specified.
- Whether an evaluator good at predicting *human* game outcomes is the right target at all. The agent's win rate is measured in self-play, and 0029's caveat stands: weights fitted on human positions come from a policy that is not ours.
- Whether the remaining gap to a perfect evaluator is reducible at all, or whether evenly-matched play is simply not that predictable from a position.
