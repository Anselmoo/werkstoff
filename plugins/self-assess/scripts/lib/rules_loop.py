"""Bound self-assess-extract-rules' round loop."""

MAX_ROUNDS_HARD_CAP = 4


class RuleLoopController:
    def __init__(self, max_rounds):
        self.max_rounds = min(max_rounds, MAX_ROUNDS_HARD_CAP) if max_rounds else MAX_ROUNDS_HARD_CAP
        self.round_number = 0
        self.consecutive_dry_rounds = 0
        self.stopped_reason = None

    def should_continue(self):
        if self.consecutive_dry_rounds >= 2:
            self.stopped_reason = "converged"
            return False
        if self.round_number >= self.max_rounds:
            self.stopped_reason = "max_rounds_reached"
            return False
        self.stopped_reason = None
        return True
