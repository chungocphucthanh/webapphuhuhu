"""Vinh's three temporal DFA rules (M3, requirement 3.1)."""

from itertools import product
from pathlib import Path

from m3_automata.dfa import ALPHABET, DFA

# One JSON per rule in m3_automata/ (the grader reads the DFA files there); R4 and the ILP
# results are not graded rules and live in extra/.
RULE_FILES = {"R1": "dfa_max2_consecutive.json", "R2": "dfa_night_then_rest.json",
              "R3": "dfa_max4_in_7days.json", "R4": "extra/dfa_R4.json"}


def r1():
    """Allow at most two consecutive working days; M, A, and N all count."""
    transitions = {
        "run0": {"M": "run1", "A": "run1", "N": "run1", "-": "run0"},
        "run1": {"M": "run2", "A": "run2", "N": "run2", "-": "run0"},
        "run2": {"M": "dead", "A": "dead", "N": "dead", "-": "run0"},
        "dead": {symbol: "dead" for symbol in ALPHABET},
    }
    return DFA(["run0", "run1", "run2", "dead"], ALPHABET, "run0",
               ["run0", "run1", "run2"], transitions)


def r2():
    """Require rest after N when a following day exists in the input word."""
    transitions = {
        "free": {"M": "free", "A": "free", "N": "after_night", "-": "free"},
        "after_night": {"M": "dead", "A": "dead", "N": "dead", "-": "free"},
        "dead": {symbol: "dead" for symbol in ALPHABET},
    }
    return DFA(["free", "after_night", "dead"], ALPHABET, "free",
               ["free", "after_night"], transitions)


def r3():
    """Allow at most four working days in seven; history before day one is rest."""
    histories = ["w" + "".join(bits) for bits in product("01", repeat=6) if bits.count("1") <= 4]
    transitions = {}
    for history in histories:
        transitions[history] = {}
        for symbol in ALPHABET:
            worked = 0 if symbol == "-" else 1
            if history.count("1") + worked > 4:
                target = "dead"
            else:
                target = "w" + history[2:] + str(worked)
            transitions[history][symbol] = target
    transitions["dead"] = {symbol: "dead" for symbol in ALPHABET}
    return DFA(histories + ["dead"], ALPHABET, "w000000", histories, transitions)

def r4(c=3):
    """Keep |#M - #A| <= c at every prefix; states -c..c count M minus A, plus a trap."""
    if c < 0:
        raise ValueError("c must be non-negative")
    live = [str(d) for d in range(-c, c + 1)]
    transitions = {}
    for d in range(-c, c + 1):
        transitions[str(d)] = {
            "M": str(d + 1) if d < c else "dead",
            "A": str(d - 1) if d > -c else "dead",
            "N": str(d),
            "-": str(d),
        }
    transitions["dead"] = {symbol: "dead" for symbol in ALPHABET}
    return DFA(live + ["dead"], ALPHABET, "0", live, transitions)


def r4_counts(strings, c=3):
    """Strings rejected by r4(c) at some prefix, and by the end-of-term count |#M - #A| > c."""
    machine = r4(c)
    prefix = sum(not machine.accepts(w) for w in strings.values())
    end = sum(abs(w.count("M") - w.count("A")) > c for w in strings.values())
    return {"total": len(strings), "c": c, "prefix_rejected": prefix, "end_rejected": end}


def main():
    """Regenerate the four submission JSON files next to this module."""
    for name, machine in (("R1", r1()), ("R2", r2()), ("R3", r3()), ("R4", r4())):
        path = Path(__file__).parent / RULE_FILES[name]
        path.parent.mkdir(exist_ok=True)
        machine.save(path)
        print(f"{RULE_FILES[name]}: {len(machine.states)} states")


if __name__ == "__main__":
    main()
