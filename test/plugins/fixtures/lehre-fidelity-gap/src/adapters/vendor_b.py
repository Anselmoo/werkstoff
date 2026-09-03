import csv

from src.adapters.base import REGISTRY
from src.contracts.schema import VendorAdapter


class VendorB(VendorAdapter):
    def rows(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            return list(csv.reader(fh, delimiter=";"))


REGISTRY["vendor_b"] = VendorB()
