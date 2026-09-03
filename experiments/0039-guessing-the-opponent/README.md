# 0039 — The search needed the opponent's move, and cannot have it

Write-up: `docs/experiments/0039-the-search-needed-the-opponents-move-and-cannot-have-it.md`

0038 measured a one-ply search at +1.4 points while handing it the opponent's
true simultaneous choice. This replaces that with a guess built from public
information only, and the effect goes to +0.2, p = 0.78.

| script | what it does |
|---|---|
| `opponent_guess.py` | The opponent model. Reads only the public view of their side. |
| `collect.py` | Forks each candidate against the *guessed* reply to rank, and grades the winner against the *true* one. |
| `report.py` | The pre-registered paired sign test. |
| `guess_accuracy.py` | How good the guesser is, against a floor and a repeat-last-move baseline. |

```bash
python experiments/0039-guessing-the-opponent/collect.py out.json 200 8 24
python experiments/0039-guessing-the-opponent/report.py out.json
python experiments/0039-guessing-the-opponent/guess_accuracy.py 150
```

## Two opponent actions, deliberately

The guess informs **the search's ranking only** — what a real search could
compute before submitting. The true move is used **only to grade** what the
search chose, because the win rate has to describe the real game. That split
also removes 0038's selection-bias problem for free: the ranking never touches
a rollout that grades it.

## Known weaknesses, left in place because they are what was measured

- **A slot with nothing revealed gets no opinion.** An earlier draft meant to
  fall back on `assumed_attacks` off their public typing and never did. 63% of
  decision points have at least one slot the guesser says nothing about, and the
  fixed default takes it. This is the largest known lever on the guesser and is
  *not* fixed here, because changing it would no longer be the thing 0039
  measured.
- **Ranking used 8 samples where 0038 used 12.** Guess quality and sample count
  both moved between the two experiments, so the comparison is not perfectly
  clean.
- **Candidates are the agent's pick plus 3 uniformly random of ~106 legal.**
  Random alternatives win 45.0% against the agent's 56.1%, so both experiments
  largely separate a good action from a poor one rather than the best from the
  second best.
