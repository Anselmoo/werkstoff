from src.db.session import get_session


def handler(order_id):
    return get_session().get(order_id)
