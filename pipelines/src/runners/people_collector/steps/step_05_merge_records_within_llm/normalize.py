from runners.people_collector.schemas import PersonRecord
from shared.utils import email_utils, phone_utils, url_utils
from utils.log_utils import PipelineRunLogger


def normalize_record(
    logger: PipelineRunLogger, record: PersonRecord
) -> PersonRecord:
    normalized_phone = (
        phone_utils.normalize_first_phone(record.phone) if record.phone else None
    )
    if record.phone and normalized_phone is None:
        logger.warning(f"Failed to parse phone number: {record.phone}")

    normalized_email = email_utils.normalize_email(record.email)
    if normalized_email and not email_utils.is_valid_email(normalized_email):
        logger.warning(f"Invalid email address found: {record.email}")
        if not record.url and url_utils.is_valid_url(normalized_email):
            record.url = url_utils.format_url(normalized_email)
        normalized_email = None

    return PersonRecord(
        name=record.name,
        # Verbatim: normalizing here is what 2.2 removed — cp.org parses.
        label=record.label,
        phone=normalized_phone,
        email=normalized_email,
        url=record.url,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source_url=record.source_url,
    )
