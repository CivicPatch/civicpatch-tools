from io import StringIO

from ruamel.yaml import YAML

# Render None as explicit `null` — YAML's canonical, unambiguous null — rather than ruamel's
# default blank scalar (`key:`), which reads like a forgotten value. It also matches what the
# data files already contain, so routing them through this manager doesn't churn `: null` lines.
_YAML_NULL_TAG = "tag:yaml.org,2002:null"


def _represent_none(representer, _value):
    return representer.represent_scalar(_YAML_NULL_TAG, "null")


def yaml_load(raw: str):
    ryaml = YAML()
    ryaml.preserve_quotes = True
    return ryaml.load(raw)


def yaml_dump(data) -> str:
    ryaml = YAML()
    ryaml.preserve_quotes = True
    ryaml.width = 2**16
    ryaml.representer.add_representer(type(None), _represent_none)
    stream = StringIO()
    ryaml.dump(data, stream)
    return stream.getvalue()
