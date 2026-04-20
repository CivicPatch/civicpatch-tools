from io import StringIO

from ruamel.yaml import YAML


def yaml_load(raw: str):
    ryaml = YAML()
    ryaml.preserve_quotes = True
    return ryaml.load(raw)


def yaml_dump(data) -> str:
    ryaml = YAML()
    ryaml.preserve_quotes = True
    stream = StringIO()
    ryaml.dump(data, stream)
    return stream.getvalue()
