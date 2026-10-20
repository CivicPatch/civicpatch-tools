from enum import StrEnum


class HeuristicsFailure(StrEnum):
    # The model named someone the page does not; the others are usually our matcher missing.
    NAME_NOT_IN_TEXT = "name_not_in_text"
    EMAIL_NOT_IN_TEXT = "email_not_in_text"
    PHONE_NOT_IN_TEXT = "phone_not_in_text"
    PHONE_NOT_NORMALIZABLE = "phone_not_normalizable"
    URL_NOT_IN_TEXT = "url_not_in_text"
