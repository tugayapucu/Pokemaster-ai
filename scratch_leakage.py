"""Does the same team appear on both sides of the train/test split?

The split is hashed by replay id, which stops the *same battle* being scored
twice but says nothing about the same **team** appearing in both halves. If a
player brought one team to twenty games and those games land on both sides,
then "test" is not measuring generalisation to unseen teams -- it is measuring
memorisation of seen ones, and the reported test rate is optimistic.

This is a claim that can be settled rather than argued, so: settle it.
"""
from collections import Counter, defaultdict
from pathlib import Path

from champions_ai.data import load_all
from champions_ai.data.split import split_replays
from champions_ai.simulator import to_id

corpus = load_all(Path("data/replays"))
split = split_replays(corpus.replays)
print(f"{len(corpus.replays)} replays: {len(split.train)} train, {len(split.test)} test")


def rosters(replay):
    """Each side's brought-Pokemon set, as seen in the log."""
    seen = defaultdict(set)
    for line in replay.log:
        if line.startswith(("|poke|", "|switch|", "|drag|")):
            parts = line.split("|")
            if line.startswith("|poke|") and len(parts) > 3:
                seen[parts[2]].add(to_id(parts[3].split(",")[0]))
            elif len(parts) > 3:
                side = parts[2].split(":")[0][:2]
                seen[side].add(to_id(parts[3].split(",")[0]))
    return {side: frozenset(mons) for side, mons in seen.items() if len(mons) >= 4}


def players(replay):
    found = []
    for line in replay.log:
        if line.startswith("|player|"):
            parts = line.split("|")
            if len(parts) > 3 and parts[3]:
                found.append(parts[3])
    return found


for label, key in (("team roster", rosters), ("player name", players)):
    train_keys, test_keys = Counter(), Counter()
    for replay in split.train:
        got = key(replay)
        for k in (got.values() if isinstance(got, dict) else got):
            train_keys[k] += 1
    for replay in split.test:
        got = key(replay)
        for k in (got.values() if isinstance(got, dict) else got):
            test_keys[k] += 1

    shared = set(train_keys) & set(test_keys)
    test_total = sum(test_keys.values())
    leaked = sum(n for k, n in test_keys.items() if k in shared)
    print(f"\n--- {label} ---")
    print(f"  distinct in train {len(train_keys)}, in test {len(test_keys)}")
    print(f"  appearing in BOTH halves: {len(shared)}")
    if test_total:
        print(f"  test-side appearances that also occur in train: "
              f"{leaked}/{test_total} = {leaked / test_total:.1%}")
    for k, n in sorted(((k, test_keys[k]) for k in shared), key=lambda kv: -kv[1])[:5]:
        print(f"    {str(k)[:70]:<70} train {train_keys[k]:>3}  test {n:>3}")
