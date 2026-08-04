from re import match

_DEFAULT_CUSTOMER_PATTERN = r"^@(?P<user_prefix>.+)_(?P<customer_phone>[A-Z]*\.?[0-9]{8,}):.+$"


def user_bridge_info(user_id: str) -> tuple[str, str]:
    from menuflow.web.base import get_config

    config = get_config()
    pattern = _DEFAULT_CUSTOMER_PATTERN

    if config:
        pattern = config.get("menuflow.customer_pattern", pattern) or pattern

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
