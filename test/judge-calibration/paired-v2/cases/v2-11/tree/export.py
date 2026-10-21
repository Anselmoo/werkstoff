HEADER = ('id', 'customer', 'amount')


def to_csv(rows):
    lines = [','.join(HEADER)]
    for r in rows:
        lines.append(','.join(str(r[k]) for k in HEADER))
    return '\n'.join(lines) + '\n'
