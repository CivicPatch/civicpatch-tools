import pathlib
import sys

# importlib import mode adds nothing to sys.path, and the eval modules import each other by bare name.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "prompts" / "tests" / "evals"))
