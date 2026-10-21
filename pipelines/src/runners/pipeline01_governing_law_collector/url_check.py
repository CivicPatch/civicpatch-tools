"""Every url a state's config names for its law, fetched and converted as a run would: does it
fetch, and is it more than a shell? Needs the network, so a task to run by hand, never CI.

    mise run check-law-urls -- /home/witch/open-data/data_source
"""

import asyncio
import sys
from enum import StrEnum
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel

from shared.utils.layered_config import ConfigFile
from . import converters
from .fetchers import RefusedByHost, plain

STATE_FILES = "*/*/config.yml"


class ConfigUrl(BaseModel):
    config_path: str
    url: str


class UrlStatus(StrEnum):
    OK = "ok"
    NEARLY_EMPTY = "nearly_empty"
    REFUSED = "refused"
    FAILED = "failed"


class UrlCheck(BaseModel):
    config_url: ConfigUrl
    status: UrlStatus
    detail: str


def config_urls(config_path: str, config: ConfigFile) -> list[ConfigUrl]:
    """The charter index and each classification's general law, in file order, each url once."""
    governing_law = config.governing_law
    if governing_law is None:
        return []
    index = [governing_law.charter_link_list.url] if governing_law.charter_link_list else []
    general_law = [url for classification in governing_law.classifications.values() for url in classification.general_law]
    return [ConfigUrl(config_path=config_path, url=url) for url in dict.fromkeys([*index, *general_law])]


async def check(config_url: ConfigUrl) -> UrlCheck:
    try:
        page = await plain.fetch(config_url.url)
        markdown = converters.to_markdown(page)
    except RefusedByHost as error:
        return UrlCheck(config_url=config_url, status=UrlStatus.REFUSED, detail=str(error.status_code))
    except (httpx.HTTPError, converters.UnsupportedContentType) as error:
        return UrlCheck(config_url=config_url, status=UrlStatus.FAILED, detail=f"{type(error).__name__}: {error}")
    status = UrlStatus.NEARLY_EMPTY if converters.is_nearly_empty(markdown) else UrlStatus.OK
    return UrlCheck(config_url=config_url, status=status, detail=f"{len(markdown.strip())} chars")


def read_config_urls(data_source: Path) -> list[ConfigUrl]:
    urls = []
    for path in sorted(data_source.glob(STATE_FILES)):
        config = ConfigFile.model_validate(yaml.safe_load(path.read_text()) or {})
        urls = [*urls, *config_urls(str(path.relative_to(data_source)), config)]
    return urls


async def main(data_source: Path) -> int:
    # One at a time: most urls share a host, and a run would not hit it in parallel either.
    checks = [await check(config_url) for config_url in read_config_urls(data_source)]
    for result in checks:
        print(f"{result.status:8} {result.config_url.config_path}  {result.config_url.url}  ({result.detail})")
    return 0 if all(result.status == UrlStatus.OK for result in checks) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
