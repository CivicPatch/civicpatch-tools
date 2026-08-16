from runners.people_collector.schemas import LLMPersonRecord
from shared.utils import email_utils, phone_utils, url_utils
from utils.log_utils import PipelineRunLogger
from shared.utils.taxonomy import Taxonomy, normalize_designations, normalize_roles


def normalize_record(
    logger: PipelineRunLogger, taxonomy: Taxonomy, record: LLMPersonRecord
) -> LLMPersonRecord:
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

    return LLMPersonRecord(
        name=record.name,
        roles=normalize_roles(record.roles, taxonomy),
        designations=normalize_designations(record.designations, taxonomy),
        phone=normalized_phone,
        email=normalized_email,
        url=record.url,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source_url=record.source_url,
    )
