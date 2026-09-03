import csv

from src.adapters.base import REGISTRY
from src.contracts.schema import VendorAdapter


class VendorA(VendorAdapter):
    def rows(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))


REGISTRY["vendor_a"] = VendorA()
