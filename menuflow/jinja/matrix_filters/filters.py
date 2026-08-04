from re import match


def user_bridge_info(user_id: str) -> tuple[str, str]:
    from menuflow.web.base import get_config

    config = get_config()
    pattern = config.get("menuflow.customer_pattern", "") or ""
    user_bridge_match = match(pattern, user_id)

    if not user_bridge_match:
        return "", ""

    groups = user_bridge_match.groupdict()
    prefix = groups.get("user_prefix") or ""
    account_id = groups.get("customer_phone") or ""

    return prefix, account_id


def user_bridge_prefix(user_id: str) -> str:
    prefix, _ = user_bridge_info(user_id=user_id)
    return prefix


def user_bridge_account_id(user_id: str) -> str:
    _, account_id = user_bridge_info(user_id=user_id)
    return account_id


def user_homeserver(user_id: str) -> str:
    _, homeserver = user_id.split(":")
    return homeserver
