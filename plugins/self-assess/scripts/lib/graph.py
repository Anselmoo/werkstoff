"""Cycle and god-module detection over the stage/wire dependency graph."""


def find_cycles(stages, wires):
    """Tarjan SCC; only components of size >= 2 are real cycles."""
    adjacency = {s: [] for s in stages}
    for a, b in wires:
        adjacency.setdefault(a, []).append(b)

    index_counter = [0]
    index, lowlink, on_stack, stack, result = {}, {}, {}, [], []

    def strongconnect(node):
        index[node] = lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True
        for successor in adjacency.get(node, []):
            if successor not in index:
                strongconnect(successor)
                lowlink[node] = min(lowlink[node], lowlink[successor])
            elif on_stack.get(successor):
                lowlink[node] = min(lowlink[node], index[successor])
        if lowlink[node] == index[node]:
            component = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == node:
                    break
            if len(component) >= 2:
                result.append(component)

    for stage in stages:
        if stage not in index:
            strongconnect(stage)
    return result


GOD_MODULE_MIN_FANIN = 3
GOD_MODULE_FANIN_RATIO = 0.5


def find_god_modules(stages, wires):
    fan_in = {s: 0 for s in stages}
    for _, target in wires:
        if target in fan_in:
            fan_in[target] += 1
    other_stage_count = max(0, len(stages) - 1)
    threshold = max(GOD_MODULE_MIN_FANIN, GOD_MODULE_FANIN_RATIO * other_stage_count)
    return [(stage, count) for stage, count in fan_in.items() if count >= threshold]
