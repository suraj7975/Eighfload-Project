"""Identity resolution: group RawRecords from different sources into the
same candidate, then merge field-by-field with a conflict policy.

Match policy (deterministic, in priority order):
  1. Exact normalized email match -> same candidate.
  2. Else exact normalized phone match -> same candidate.
  3. Else exact lowercased full_name match -> same candidate (weakest;
     names collide, but it's better than silently splitting one person
     into two profiles when no stronger signal exists).
A union-find groups records that share *any* of these keys transitively
(e.g. CSV has email+name, resume has name+phone-> all three are one person).
"""
from collections import defaultdict


def _keys_for(rec):
    keys = set()
    for ev in rec.emails:
        keys.add(("email", ev.value))
    for pv in rec.phones:
        keys.add(("phone", pv.value))
    if rec.full_name and rec.full_name.value:
        keys.add(("name", rec.full_name.value.strip().lower()))
    if not keys:
        keys.add(("anon", rec.candidate_key))
    return keys


def group_records(all_records):
    """Union-find over shared keys. Returns list[list[RawRecord]]."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    key_owner = {}
    for idx, rec in enumerate(all_records):
        rec_node = ("rec", idx)
        find(rec_node)
        for k in _keys_for(rec):
            if k in key_owner:
                union(rec_node, key_owner[k])
            else:
                key_owner[k] = rec_node
                find(key_owner[k])
            union(rec_node, key_owner[k])

    groups = defaultdict(list)
    for idx, rec in enumerate(all_records):
        root = find(("rec", idx))
        groups[root].append(rec)

    return list(groups.values())
