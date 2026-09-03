from src.contracts.schema import VendorAdapter

REGISTRY = {}


def get_adapter(name):
    return REGISTRY.get(name)
