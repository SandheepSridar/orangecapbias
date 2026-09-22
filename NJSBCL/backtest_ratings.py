"""Backtest team-rating methods against completed matches.

Answers one question: does anything beat the Elo the dashboard currently ships?

Every method is scored walk-forward — it predicts each match using only matches played
before it, then is shown the result. So the numbers here are out-of-sample, which is the
only kind worth comparing. Scoring is Brier score and log loss against two baselines: a
flat 50%, and the empirical bat-first win rate (the format's own bias, which any useful
method has to beat).

Chronological order comes from matchId, which increases monotonically — the same proxy
build_data.py uses everywhere.

Run:  cd NJSBCL && source .venv/bin/activate && python3 backtest_ratings.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "dashboard"))
from build_data import ELO_K, ELO_START, win_probability  # same constants the site ships

DATA = Path(__file__).parent / "data"
SERIES = {"division1": "division1", "weekenders": "weekenderscup"}
MIN_PRIOR_MATCHES = 3   # don't score a tie until both sides have some history
REFIT_EVERY = 25        # batch methods refit this often, not every match


def load_matches(tag):
    """One row per decided match: who batted first, both totals, both balls faced.

    A match needs a scorecard (for the batting order and balls) and a non-zero entry in
    true_totals (the official scores). Washed-out matches are all-zero there and drop out,
    as do the handful whose scorecard doesn't have exactly two teams.
    """
    bat = pd.read_csv(DATA / f"{tag}_scorecards_batting.csv")
    tot = pd.read_csv(DATA / f"{tag}_true_totals.csv").set_index("matchId")
    rows = []
    for mid, g in bat.groupby("matchId"):
        g = g.assign(team=g.team.str.strip())
        teams = list(dict.fromkeys(g.team))
        if len(teams) != 2 or mid not in tot.index:
            continue
        r = tot.loc[mid]
        if r.score1 + r.score2 == 0 or r.score1 == r.score2:
            continue                                    # washed out, or tied -> no label
        balls = g.groupby("team").B.sum()
        rows.append({
            "matchId": mid, "first": teams[0], "second": teams[1],
            "s1": int(r.score1), "s2": int(r.score2),
            "b1": int(balls.get(teams[0], 0)), "b2": int(balls.get(teams[1], 0)),
            "firstWon": int(r.score1 > r.score2),
        })
    return pd.DataFrame(rows).sort_values("matchId").reset_index(drop=True)


# ── Methods ───────────────────────────────────────────────────────────
# Each exposes predict(a, b) -> P(a beats b) and observe(match). Online methods update
# state in observe; batch methods bank the match and refit every REFIT_EVERY.

class Flat:
    name = "Baseline: always 50%"
    def predict(self, a, b): return 0.5
    def observe(self, m): pass


class BatFirst:
    name = "Baseline: bat-first rate"
    def __init__(self): self.w = self.n = 0
    def predict(self, a, b): return (self.w + 1) / (self.n + 2)   # a == team batting first
    def observe(self, m): self.w += m["firstWon"]; self.n += 1


class Elo:
    """The dashboard's current model, reusing its own constants and probability curve."""
    name = "Elo (plain — previous)"
    def __init__(self, k=ELO_K): self.k, self.r = k, {}
    def _get(self, t): return self.r.setdefault(t, ELO_START)
    def predict(self, a, b): return win_probability(self._get(a), self._get(b)) / 100
    def observe(self, m):
        a, b = m["first"], m["second"]
        ra, rb = self._get(a), self._get(b)
        exp = 1 / (1 + 10 ** ((rb - ra) / 400))
        delta = self.k * (m["firstWon"] - exp)
        self.r[a], self.r[b] = ra + delta, rb - delta


class EloMOVRuns(Elo):
    """The obvious first attempt: weight by the run difference. Kept because it is the
    version most people reach for, and because it does NOT clear significance on either
    series — a chase is recorded in runs only as the few it won by, so a nine-wicket
    stroll and a last-ball squeaker look almost identical here."""
    name = "Elo + MOV (runs only)"
    def observe(self, m):
        a, b = m["first"], m["second"]
        ra, rb = self._get(a), self._get(b)
        exp = 1 / (1 + 10 ** ((rb - ra) / 400))
        mult = np.log1p(abs(m["s1"] - m["s2"]) / 10.0)
        d = self.k * mult * (m["firstWon"] - exp)
        self.r[a], self.r[b] = ra + d, rb - d


class EloMOV(Elo):
    """What build_data.py now ships: runs when the total was defended, balls to spare when
    it was chased, with the first innings as the allotment so rain-reduced games need no
    assumption about the format's length. Mirror of elo_margin_multiplier() there — if one
    changes, change both, or this stops testing what is deployed."""
    name = "Elo + MOV (as shipped)"
    def observe(self, m):
        a, b = m["first"], m["second"]
        ra, rb = self._get(a), self._get(b)
        exp = 1 / (1 + 10 ** ((rb - ra) / 400))
        if m["firstWon"]:
            mult = np.log1p(abs(m["s1"] - m["s2"]) / 10.0)
        else:
            mult = np.log1p(max(m["b1"] - m["b2"], 0) / 10.0 + 1.0)
        d = self.k * mult * (m["firstWon"] - exp)
        self.r[a], self.r[b] = ra + d, rb - d


class BradleyTerry:
    """The principled version of Elo: one logistic strength per team, fitted to every result
    at once by penalised MLE rather than sequentially. No path dependence, and an L2 prior
    keeps unbeaten teams from running off to infinity."""
    name = "Bradley-Terry (L2)"
    def __init__(self, lam=1.0, iters=300, lr=0.5):
        self.lam, self.iters, self.lr = lam, iters, lr
        self.hist, self.s, self.since = [], {}, 10 ** 9

    def predict(self, a, b):
        return 1 / (1 + np.exp(-(self.s.get(a, 0.0) - self.s.get(b, 0.0))))

    def observe(self, m):
        self.hist.append(m); self.since += 1
        if self.since >= REFIT_EVERY and len(self.hist) >= 20:
            self._fit(); self.since = 0

    def _fit(self):
        teams = sorted({t for m in self.hist for t in (m["first"], m["second"])})
        idx = {t: i for i, t in enumerate(teams)}
        ia = np.array([idx[m["first"]] for m in self.hist])
        ib = np.array([idx[m["second"]] for m in self.hist])
        y = np.array([m["firstWon"] for m in self.hist], dtype=float)
        s = np.zeros(len(teams))
        for _ in range(self.iters):
            p = 1 / (1 + np.exp(-(s[ia] - s[ib])))
            g = np.zeros(len(teams))
            np.add.at(g, ia, y - p)
            np.add.at(g, ib, p - y)
            s += self.lr * (g - self.lam * s) / max(len(self.hist), 1)
        self.s = dict(zip(teams, s))


class Pythagorean:
    """Runs for and against, the Bill James way — a team's expected win rate from its scoring
    ratio, then Log5 to turn two win rates into a head-to-head probability. Uses margin, which
    Elo throws away, and needs nothing but the totals."""
    name = "Pythagorean + Log5"
    def __init__(self, k=2.0): self.k, self.f, self.a = k, {}, {}
    def _wr(self, t):
        f, a = self.f.get(t, 0), self.a.get(t, 0)
        if f + a == 0: return 0.5
        return f ** self.k / (f ** self.k + a ** self.k)
    def predict(self, a, b):
        pa, pb = self._wr(a), self._wr(b)
        den = pa * (1 - pb) + (1 - pa) * pb
        return 0.5 if den == 0 else pa * (1 - pb) / den
    def observe(self, m):
        a, b = m["first"], m["second"]
        self.f[a] = self.f.get(a, 0) + m["s1"]; self.a[a] = self.a.get(a, 0) + m["s2"]
        self.f[b] = self.f.get(b, 0) + m["s2"]; self.a[b] = self.a.get(b, 0) + m["s1"]


class AdjustedRPO:
    """Opponent-adjusted runs per over: every innings is modelled as
    rpo = mu + attack[batting team] - defence[bowling team], solved as one ridge regression.
    The predicted run-rate margin is then mapped to a probability by a single fitted slope.

    This is the one that can in principle compare teams with no match chain between them,
    because runs are an absolute scale where win/loss is purely relative.
    """
    name = "Adjusted RPO (ridge)"
    def __init__(self, lam=3.0):
        self.lam, self.hist, self.since = lam, [], 10 ** 9
        self.att, self.dfn, self.beta = {}, {}, 0.35

    def _margin(self, a, b):
        return ((self.att.get(a, 0) - self.dfn.get(b, 0))
                - (self.att.get(b, 0) - self.dfn.get(a, 0)))

    def predict(self, a, b):
        return 1 / (1 + np.exp(-self.beta * self._margin(a, b)))

    def observe(self, m):
        self.hist.append(m); self.since += 1
        if self.since >= REFIT_EVERY and len(self.hist) >= 20:
            self._fit(); self.since = 0

    def _fit(self):
        teams = sorted({t for m in self.hist for t in (m["first"], m["second"])})
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)
        X, y = [], []
        for m in self.hist:
            for bat, bowl, runs, balls in ((m["first"], m["second"], m["s1"], m["b1"]),
                                           (m["second"], m["first"], m["s2"], m["b2"])):
                if balls < 12:                     # a handful of balls is not an innings
                    continue
                row = np.zeros(2 * n + 1)
                row[idx[bat]] = 1.0                # attack
                row[n + idx[bowl]] = -1.0          # defence
                row[-1] = 1.0                      # intercept
                X.append(row); y.append(runs / (balls / 6.0))
        if len(X) < 20:
            return
        X, y = np.array(X), np.array(y)
        # ridge on the team effects only, leaving the intercept unpenalised
        pen = np.sqrt(self.lam) * np.eye(2 * n + 1)
        pen[-1, -1] = 0.0
        sol, *_ = np.linalg.lstsq(np.vstack([X, pen]),
                                  np.concatenate([y, np.zeros(2 * n + 1)]), rcond=None)
        self.att = {t: sol[idx[t]] for t in teams}
        self.dfn = {t: sol[n + idx[t]] for t in teams}
        self._fit_beta()

    def _fit_beta(self):
        """One slope turning a run-rate margin into a probability, by log-loss grid search."""
        margins = np.array([self._margin(m["first"], m["second"]) for m in self.hist])
        y = np.array([m["firstWon"] for m in self.hist], dtype=float)
        best, bl = self.beta, np.inf
        for beta in np.linspace(0.05, 2.0, 40):
            p = np.clip(1 / (1 + np.exp(-beta * margins)), 1e-6, 1 - 1e-6)
            ll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
            if ll < bl:
                best, bl = beta, ll
        self.beta = best


METHODS = [Flat, BatFirst, Elo, EloMOVRuns, EloMOV, BradleyTerry, Pythagorean, AdjustedRPO]


# ── Harness ───────────────────────────────────────────────────────────
def backtest(matches):
    methods = [M() for M in METHODS]
    preds = {m.name: [] for m in methods}
    truth, seen = [], {}
    for _, row in matches.iterrows():
        m = row.to_dict()
        a, b = m["first"], m["second"]
        scored = seen.get(a, 0) >= MIN_PRIOR_MATCHES and seen.get(b, 0) >= MIN_PRIOR_MATCHES
        if scored:
            for meth in methods:
                preds[meth.name].append(float(np.clip(meth.predict(a, b), 1e-6, 1 - 1e-6)))
            truth.append(m["firstWon"])
        for meth in methods:
            meth.observe(m)
        seen[a] = seen.get(a, 0) + 1
        seen[b] = seen.get(b, 0) + 1
    return preds, np.array(truth, dtype=float), methods


def score(p, y):
    p = np.asarray(p)
    brier = float(np.mean((p - y) ** 2))
    logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    acc = float(np.mean((p >= 0.5) == (y == 1)))
    return brier, logloss, acc


def calibration(p, y, bins=5):
    p = np.asarray(p)
    out = []
    for lo, hi in zip(np.linspace(0, 1, bins + 1)[:-1], np.linspace(0, 1, bins + 1)[1:]):
        sel = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if sel.sum():
            out.append((f"{lo:.1f}-{hi:.1f}", int(sel.sum()), float(p[sel].mean()), float(y[sel].mean())))
    return out


def bootstrap_vs(p_new, p_ref, y, n=2000, seed=0):
    """Is the gap over the incumbent real, or resampling noise?

    Paired bootstrap on per-match squared error: resample matches (not methods), so the
    two models are always judged on the same games. Returns the mean Brier difference,
    a 95% interval, and how often the challenger wins outright.
    """
    rng = np.random.default_rng(seed)
    d = (np.asarray(p_ref) - y) ** 2 - (np.asarray(p_new) - y) ** 2   # >0 => new is better
    idx = rng.integers(0, len(d), size=(n, len(d)))
    means = d[idx].mean(axis=1)
    return d.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5), float((means > 0).mean())


def main():
    for key, tag in SERIES.items():
        matches = load_matches(tag)
        preds, y, methods = backtest(matches)
        print(f"\n{'=' * 78}\n{key}: {len(matches)} decided matches · {len(y)} scored "
              f"(both sides had {MIN_PRIOR_MATCHES}+ prior)\n{'=' * 78}")
        base = score(preds["Baseline: always 50%"], y)[0]
        print(f"{'method':<28}{'Brier':>9}{'LogLoss':>10}{'Acc':>8}{'skill vs 50%':>14}")
        rows = []
        for meth in methods:
            br, ll, acc = score(preds[meth.name], y)
            rows.append((meth.name, br, ll, acc, 1 - br / base))
        for name, br, ll, acc, sk in rows:
            print(f"{name:<28}{br:>9.4f}{ll:>10.4f}{acc:>8.1%}{sk:>13.1%}")
        ref = preds["Elo (plain — previous)"]
        print(f"\n  vs the previous plain Elo (paired bootstrap, 2000 resamples):")
        print(f"    {'method':<26}{'Brier gain':>12}{'95% interval':>22}{'P(better)':>11}")
        for meth in methods:
            if meth.name.startswith("Baseline") or meth.name == "Elo (plain — previous)":
                continue
            mean, lo, hi, pw = bootstrap_vs(preds[meth.name], ref, y)
            verdict = "" if lo > 0 else "   (interval crosses 0)"
            print(f"    {meth.name:<26}{mean:>+12.4f}   [{lo:>+.4f}, {hi:>+.4f}]{pw:>10.0%}{verdict}")

        best = min((r for r in rows if not r[0].startswith("Baseline")), key=lambda r: r[1])
        print(f"\n  best: {best[0]}  (Brier {best[1]:.4f})")
        print(f"  calibration for {best[0]} — bin, n, predicted, actual:")
        for b, n, pm, am in calibration(preds[best[0]], y):
            flag = "  <-- off" if abs(pm - am) > 0.10 else ""
            print(f"    {b}  n={n:<5} pred={pm:.3f}  actual={am:.3f}{flag}")


if __name__ == "__main__":
    main()
