class Bucket:
    def __init__(self, capacity):
        self.capacity = capacity
        self.tokens = capacity

    def take(self):
        if self.tokens == 0:
            return False
        self.tokens -= 1
        return True

    def refill(self):
        self.tokens = self.capacity
