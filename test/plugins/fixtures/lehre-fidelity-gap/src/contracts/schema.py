class RowSchema:
    fields = ("vendor", "sku", "qty", "price")


class VendorAdapter:
    def rows(self, path):
        raise NotImplementedError
