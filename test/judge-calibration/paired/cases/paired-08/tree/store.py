class Store:
    def __init__(self):
        self.rows = {}

    def upsert(self, key, value):
        created = key not in self.rows
        self.rows[key] = value
        return created
