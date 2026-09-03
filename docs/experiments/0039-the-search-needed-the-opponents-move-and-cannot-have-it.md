# Experiment 0039 — The search needed the opponent's move, and cannot have it

**Date:** 2026-09-03
**Result: 0038's +1.4 points came entirely from being handed the opponent's move. Replace that with a guess built from public information and the effect is +0.2 points, 27 ahead and 25 behind, p = 0.78.** The guesser is not the problem: at 39.0% per slot against a 30.5% floor it is a real model, and it still recovers none of the gain. The reason is structural — a one-ply search in doubles needs the opponent's *joint* action, and 39% per slot compounds to **8.4%** for the turn.

## The cheat 0038 carried

0038 forked the engine with `{our candidate, their move}` and scored the successor. Their move came from:

```python
opponent = probe[1].select_action(env.observation(1), env.legal_actions(1))
```

That is player 1's true simultaneous choice. It is not a leak of anything player 1 should keep secret — it is simply what they were about to do — but a search run by player 0 chooses *before* seeing it. 0038 recorded this as its largest uncontrolled factor. This measures it.

## What replaced it

`guess_opponent_action` reads only `observation(0).opponent_side`: species, HP%, boosts, status, and **revealed** moves. It reuses the machinery the agent already has for judging incoming danger — `_threat_from`'s damage loop and `assumed_attacks` — and predicts, per active slot, the revealed damaging move doing the most expected damage to our best target. It never sees their true stats, item, ability, PP or unrevealed moves.

Two opponent actions are then used for two different jobs, which also removes 0038's selection-bias problem for free:

```
  guessed   informs the search's ranking only -- what it would compute
  true      what actually happens, used only to grade the chosen action
```

The ranking never touches a rollout that grades it, so no odd/even split is needed this time.

One deliberate leak, stated rather than hidden: submitting a guess needs a legal choice string, so player 1's true option list is consulted to translate an already-made guess into something the engine accepts. It never uses their true damage numbers to *choose* the guess.

## The result

Pre-registered before the run: *on the true continuation, the guessed-opponent search beats the agent's own pick where the two differ, paired sign test, p < 0.05.*

```
  286 decision points, 192 battles

  search chose the agent's own action     210   (73%)
  search chose something different         76   (27%)

                                   all points   where they differ
  the agent's own pick (shipped)        48.1%              44.0%
  guessed-opponent search               48.2%              44.6%
  difference                            +0.2%              +0.6%

  ahead 27   behind 25   tied 24        p = 0.7815     NOT CONFIRMED

  noise floor, same action on disjoint seeds:  mean 5.7%, sd 8.8%
```

Both differences sit an order of magnitude inside the noise floor. And **the search stops disagreeing**: with the oracle it proposed something different often enough to matter; without it, it agrees with the agent 73% of the time and splits evenly on the rest.

## The guesser is not the excuse

The obvious objection is that the opponent model is simply bad. Measured directly, on 656 decision points, against two reference points:

```
  opponent model        whole turn right    per slot right
  fixed default                    2.4%             30.5%
  repeat last move                 3.0%             30.0%
  revealed-best (used here)        8.4%             39.0%
```

It beats a model that knows nothing by nearly nine points per slot and more than triples it on whole turns. It is a real model, and it buys nothing.

**The structure is the finding.** A one-ply search does not need to predict a move; it needs to predict the *turn* — both slots, with targets, simultaneously — because that is what the engine needs to step. Per-slot accuracy of 39% compounds to 8.4% jointly. Doubles makes opponent modelling exponentially harder in exactly the place a search consumes it.

By information available:

```
  moves seen    slots    right          turn    slots    right
  0               453    26.0%             1      297    23.6%
  1               452    50.4%             2      268    48.1%
  2               288    41.3%             3      289    39.4%
  3                37    40.5%             4      255    45.1%
```

Worth noting against my own case: accuracy does **not** keep climbing with more revealed moves. One seen move is the peak. That says the ceiling here is the model, not the information — a better opponent model has room. It also says the room is being left on a task whose joint form is the hard part.

## What this settles

- **Milestone 11 is closed on much stronger grounds than 0022's.** 0022 built a lookahead, found it inert, woke it and lost nine points, and the reason was left as a hypothesis. The reason is now measured: the only version that helps requires knowing the opponent's turn, and knowing the opponent's turn is 8.4% achievable.
- **It resolves the standing contradiction with 0005.** 0005 found perfect knowledge of the opponent's move *this turn* made the agent **worse**, and it was filed under "correct information, wrongly priced, hurts" — the information went into the heuristic's scorer, in the wrong currency. 0038 put the same information into an engine fork, where it cannot be mispriced, and it was worth +1.4. Both are right. The information is real, the pricing was the bug, and 0039 shows it is unobtainable anyway.
- **It prices Milestone 10 rather than killing it.** An opponent model is worth at most what perfect knowledge is worth in the place it is consumed, and for a one-ply search that ceiling is +1.4 points. That is the whole prize for going from 8.4% to 100% on a task where more information has so far not helped.

## Not established

- Whether a materially better opponent model exists. The plateau after one revealed move suggests the rule is the limit, not the data, and nothing here tries a better rule — a policy trained to imitate the opponent, or a distribution over their actions rather than a single guess.
- **Whether marginalising beats guessing.** This commits to one predicted action. A search that scored each candidate against a *distribution* of opponent replies is the standard answer to simultaneous moves and is not tested here; it is the one design that could work at 8.4% joint accuracy, because it never needs the single right answer.
- Whether any of it changes against an opponent that is not our own heuristic. 0026's blind spot, still open, and now doubly relevant: the guesser was predicting a policy identical to our own and still only managed 39%.
