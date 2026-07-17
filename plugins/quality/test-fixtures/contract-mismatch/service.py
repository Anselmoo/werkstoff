"""Tiny lookup service used only by the contract-mismatch test fixture."""


def get_user_email(user_id: int) -> str:
    """Look up a user's email address.

    Args:
        user_id (int): The numeric ID of the user to look up.

    Returns:
        str: The user's email address.
    """
    directory = {1: "alice@example.com", 2: "bob@example.com"}
    return directory[user_id]
