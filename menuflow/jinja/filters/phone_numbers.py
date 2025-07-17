import phonenumbers
from phonenumbers import carrier, geocoder, timezone


class PhoneNumbers:
    def __init__(self, *args, **kwargs) -> None:
        try:
            self._parsed = phonenumbers.parse(*args, **kwargs)
        except Exception:
            self._parsed = None

    def __str__(self) -> str:
        return str(self._parsed)

    def __getattr__(self, attr) -> str:
        if self._parsed:
            return getattr(self._parsed, attr)
        raise AttributeError(f"'PhoneNumbers' has no attribute '{attr}'")

    @property
    def time_zones_for_number(self) -> list[str]:
        """Returns a list of time zones for the phone number.

        Returns:
            list[str]: A list of time zones for the phone number
        """
        return list(timezone.time_zones_for_number(self._parsed)) if self._parsed else []

    @property
    def is_valid_number(self) -> bool:
        """Returns True if the phone number is valid, False otherwise.

        Returns:
            bool: True if the phone number is valid, False otherwise
        """
        return phonenumbers.is_valid_number(self._parsed) if self._parsed else False

    @property
    def format_for_number_e164(self) -> str:
        """Returns the formatted phone number.

        Returns:
            str: The formatted phone number
        """
        return (
            phonenumbers.format_number(self._parsed, phonenumbers.PhoneNumberFormat.E164)
            if self._parsed
            else None
        )

    def name_for_number(self, *args, **kwargs) -> str:
        """Returns the carrier name for the phone number.

        Returns:
            str: The carrier name for the phone number
        """
        return carrier.name_for_number(self._parsed, *args, **kwargs) if self._parsed else None

    def description_for_number(self, *args, **kwargs) -> str:
        """Returns the location for the phone number.

        Returns:
            str: The location for the phone number
        """
        return (
            geocoder.description_for_number(self._parsed, *args, **kwargs)
            if self._parsed
            else None
        )
