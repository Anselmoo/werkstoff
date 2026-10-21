class Inventory:
    def __init__(self, stock):
        self.stock = dict(stock)
        self.done = set()

    def reserve(self, order_id, sku, qty):
        if order_id in self.done:
            return True
        self.stock[sku] = self.stock.get(sku, 0) - qty
        if self.stock[sku] < 0:
            return False
        self.done.add(order_id)
        return True
