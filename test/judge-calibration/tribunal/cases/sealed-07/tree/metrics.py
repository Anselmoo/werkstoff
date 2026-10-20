class Counters:
    def __init__(self):
        self.c = {}

    def incr(self, name, n=1):
        self.c[name] = self.c.get(name, 0) + n

    def render(self):
        return "".join(f"{k} {v}\n" for k, v in sorted(self.c.items()))
