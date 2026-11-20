"""Complete DFA over the roster alphabet {M, A, N, -} (M3, req 3.1).

M = (Q, Sigma, delta, q0, F). Every state has a transition for every symbol, so a
violating run ends in an explicit trap state instead of an undefined move.

JSON format (fixed by the brief, one file per rule in m3_automata/):
    {"states": [...], "alphabet": [...], "start": q0, "accepting": [...],
     "transitions": {state: {symbol: state}}}
The format lives only in `to_dict` / `from_dict`, so it can change in one place.
"""

from __future__ import annotations

import json
from pathlib import Path

ALPHABET = ("M", "A", "N", "-")


class DFA:
    def __init__(self, states, alphabet, start, accepting, transitions):
        self.states = list(states)
        self.alphabet = list(alphabet)
        self.start = start
        self.accepting = set(accepting)
        self.transitions = {q: dict(row) for q, row in transitions.items()}
        self.validate()

    def validate(self):
        """Raise ValueError unless this is a well-formed, complete DFA."""
        if not self.states or len(set(self.states)) != len(self.states):
            raise ValueError("states must be non-empty and unique")
        if not self.alphabet or len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError("alphabet must be non-empty and unique")
        if any(not isinstance(a, str) or len(a) != 1 for a in self.alphabet):
            raise ValueError("every alphabet symbol must be a single character")
        known = set(self.states)
        if self.start not in known:
            raise ValueError(f"start state {self.start!r} is not a state")
        if not self.accepting <= known:
            raise ValueError(f"accepting states not in Q: {sorted(self.accepting - known)}")
        if set(self.transitions) != known:
            raise ValueError("transitions must have exactly one row per state")
        for q, row in self.transitions.items():
            if set(row) != set(self.alphabet):
                raise ValueError(f"state {q!r} must define exactly the symbols {self.alphabet}")
            for a, target in row.items():
                if target not in known:
                    raise ValueError(f"delta({q!r}, {a!r}) = {target!r} is not a state")

    def run(self, word):
        """delta*(q0, word); a symbol outside the alphabet raises ValueError."""
        q = self.start
        for a in word:
            if a not in self.alphabet:
                raise ValueError(f"symbol {a!r} is not in the alphabet {self.alphabet}")
            q = self.transitions[q][a]
        return q

    def accepts(self, word):
        """True iff word is in L(M); the empty word is read as the empty schedule."""
        return self.run(word) in self.accepting

    def reachable_states(self):
        """States reachable from the start, in breadth-first order."""
        seen, queue = [self.start], [self.start]
        while queue:
            q = queue.pop(0)
            for a in self.alphabet:
                t = self.transitions[q][a]
                if t not in seen:
                    seen.append(t)
                    queue.append(t)
        return seen

    def trap_states(self):
        """Non-accepting states whose every symbol loops back to themselves."""
        return [q for q in self.states
                if q not in self.accepting and all(t == q for t in self.transitions[q].values())]

    def to_dict(self):
        return {
            "states": list(self.states),
            "alphabet": list(self.alphabet),
            "start": self.start,
            "accepting": [q for q in self.states if q in self.accepting],
            "transitions": {q: {a: self.transitions[q][a] for a in self.alphabet}
                            for q in self.states},
        }

    @classmethod
    def from_dict(cls, data):
        try:
            return cls(data["states"], data["alphabet"], data["start"],
                       data["accepting"], data["transitions"])
        except KeyError as error:
            raise ValueError(f"DFA JSON is missing the key {error}") from error

    def to_json(self):
        """Stable text: fixed key order, indent 2, LF, trailing newline."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    def save(self, path):
        Path(path).write_text(self.to_json(), encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def __repr__(self):
        return f"DFA({len(self.states)} states, start={self.start!r}, accepting={len(self.accepting)})"
