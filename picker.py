"""Pick songs that fill the broadcast to the target length."""
import random


def pick_songs(songs, need, tolerance=30, seed=None, recent=()):
    """Choose songs whose total length is as close as possible to `need` seconds.

    songs: list of dicts with 'path', 'duration' (s) and 'seasonal' (bool).
    Seasonal songs come first, then general songs; songs in `recent` come last.
    Returns (chosen songs, total seconds). The total is never more than need + tolerance.
    """
    if need <= 0:
        return [], 0.0
    rng = random.Random(seed)
    recent = set(recent)

    def rank(s):
        return (s["path"] in recent, not s["seasonal"], rng.random())

    ordered = sorted((s for s in songs if s["duration"] > 0), key=rank)
    limit = int(need + tolerance)
    # best[t] = indices of the first combination found with total t seconds.
    # Songs earlier in the order are tried first, so they are preferred.
    best = {0: ()}
    for i, s in enumerate(ordered):
        d = int(round(s["duration"]))
        for t, combo in list(best.items()):
            n = t + d
            if n <= limit and n not in best:
                best[n] = combo + (i,)
        if any(abs(t - need) <= 1 for t in best):
            break
    total = min(best, key=lambda t: (abs(t - need), len(best[t])))
    chosen = [ordered[i] for i in best[total]]
    rng.shuffle(chosen)
    return chosen, sum(s["duration"] for s in chosen)
