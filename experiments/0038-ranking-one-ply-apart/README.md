# 0038 — Ranking is an easier task, and it is worth about a point

Write-up: `docs/experiments/0038-ranking-is-an-easier-task-and-it-is-worth-a-point.md`

Asks whether `evaluate_position` can *order* the actions at one decision point,
as a search would need, rather than predict the eventual winner, which 0035 and
0037 measured at ~63%. Ground truth comes from forking the engine at a decision
point, applying each candidate action, and rolling the rest out repeatedly.

| script | what it does |
|---|---|
| `collect.py` | **The confirmed run.** Saves rollouts individually so selection and scoring can be split. |
| `report.py` | Reads it. Odd rollouts choose the action, even ones score it, then the reverse. The pre-registered test. |
| `collect_first.py` | The first run, kept because the write-up cites it and because its bias is the point. |
| `report_first.py` | Its analysis, including the noise control. |
| `value.py` | Turns ranking accuracy into win rate. **Its numbers are the biased ones** — see below. |
| `stakes.py` | Whether anything cheap predicts which decisions are worth thinking about. |

```bash
python experiments/0038-ranking-one-ply-apart/collect.py ranking2.json 220 24
python experiments/0038-ranking-one-ply-apart/report.py ranking2.json
```

## The bias, and why the first run is kept

`collect_first.py` scores each candidate with the mean successor evaluation
taken from **the same rollouts** that then grade it, so a candidate that got
lucky is both likelier to be picked and likelier to look good. That put the
headline at +2.9 points. Splitting the rollouts put it at **+1.4**. Half the
effect was the bias — the same shape that produced 0029, published and
retracted. Both runs are kept because the difference between them is the
lesson.

## Known defect, left in place

`collect_first.py` originally appended to `evals` only on non-terminal rollouts
while counting wins on all of them, so `eval_one` could describe a different
branch than the one it was paired with. It affected 0.36% of rollouts and 1.2%
of decision points, and none of the figures the write-up quotes. Fixed here
(the terminal branch now appends `None`), which is safe because no published
number came from `eval_one` in that run.
