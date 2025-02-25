import uuid


class Util:
    """Class with utility functions."""

    @staticmethod
    def generate_uuid() -> str:
        """Generate a UUID for use in transactions.
        Returns:
            str: The UUID generated.
        """
        return uuid.uuid4().hex
