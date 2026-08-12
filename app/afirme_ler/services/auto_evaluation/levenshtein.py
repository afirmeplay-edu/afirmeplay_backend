# -*- coding: utf-8 -*-
from __future__ import annotations


def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(
                min(
                    prev[j] + 1,  # delete
                    curr[j - 1] + 1,  # insert
                    prev[j - 1] + cost,  # substitute
                )
            )
        prev = curr
    return prev[-1]


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    distance = levenshtein_distance(a, b)
    return 1.0 - (distance / max(len(a), len(b)))
