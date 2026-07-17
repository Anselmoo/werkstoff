"""Caller of `service.get_user_email`, deliberately violating its declared contract."""

from service import get_user_email


def notify_user(user_id: int) -> None:
    # get_user_email's declared contract is `user_id: int`, but every real
    # call site here passes a str — the exact drift quality-contract-drift
    # exists to catch.
    email = get_user_email(user_id=str(user_id))
    print(f"Notifying {email}")


def notify_all(user_ids: list[int]) -> None:
    for uid in user_ids:
        notify_user(uid)
