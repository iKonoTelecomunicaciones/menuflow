from re import match


def user_bridge_info(user_id: str) -> str:
    user_bridge_match = match("^@(?P<user_prefix>.+)_(?P<account_id>[0-9]{8,}):.+$", user_id)

    if not user_bridge_match:
        return ","

    return f"{user_bridge_match.group('user_prefix')},{user_bridge_match.group('account_id')}"


def user_bridge_prefix(user_id: str) -> str:
    prefix, _ = user_bridge_info(user_id=user_id).split(",")
    return prefix


def user_bridge_account_id(user_id: str) -> str:
    _, account_id = user_bridge_info(user_id=user_id).split(",")
    return account_id


def user_homeserver(user_id: str) -> str:
    _, homeserver = user_id.split(":")
    return homeserver
