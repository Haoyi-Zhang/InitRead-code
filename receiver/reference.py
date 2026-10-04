"""Independent dense oracle for the data section (no production imports).

This oracle deliberately does NOT validate certificates. It states the desired
final value property directly, and independently checks every input domain.
"""

def decide(words):
    if type(words) is not list or not 5 <= len(words) <= 24576:
        return {'status': 'INVALID_DATA', 'reason': 'word-container'}
    if any(type(w) is not int or not -(1 << 31) <= w < (1 << 31) for w in words):
        return {'status': 'INVALID_DATA', 'reason': 'word-type'}
    if words[:2] != [0x52434331, 1]:
        return {'status': 'INVALID_DATA', 'reason': 'schema'}
    n, m = words[2:4]
    if not 1 <= n <= 128 or not 0 <= m <= 128 or len(words) < 5 + 2*n + m:
        return {'status': 'INVALID_DATA', 'reason': 'dimensions'}
    values, links, roots = words[4:4+n], words[4+n:4+2*n], words[4+2*n:4+2*n+m]
    if any(v not in (0, 1) for v in values):
        return {'status': 'INVALID_DATA', 'reason': 'value'}
    if any(x < -1 or x >= n for x in links) or any(x < 0 or x >= n for x in roots):
        return {'status': 'INVALID_DATA', 'reason': 'identity'}
    # Warshall closure, unlike producer traversal and receiver queue expansion.
    reach = [[i == j or links[i] == j for j in range(n)] for i in range(n)]
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                reach[i] = [a or b for a, b in zip(reach[i], reach[k])]
    live = [j for j in range(n) if any(reach[r][j] for r in roots)]
    safe = all(links[i] == -1 or values[i] <= values[links[i]] for i in live)
    return {'status': 'ALLOW' if safe else 'DENY_UNSAFE', 'reachable': live,
            'values': values, 'links': links, 'roots': roots}
