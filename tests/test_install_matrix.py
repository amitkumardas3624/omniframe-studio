"""Host-independent packaging checks for the OmniFrame install/test matrix.

Every assertion here reads build metadata that is committed to the repository
(``pyproject.toml``, the CI workflow, and the files under ``src/omniframe``).
No proprietary DCC host is launched or required, so this module is safe to run
on any machine: it is the packaging half of the release gate, while
``tests/test_compat.py`` covers the runtime half.

``tomllib`` is stdlib only from Python 3.11, therefore the ``dev`` extra
declares ``tomli`` for 3.10 and this module falls back to it. Installing the
``dev`` extra is the documented way to run the test suite.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PACKAGE = ROOT / "src" / "omniframe"

#: The Python floor the whole platform is written against.
MIN_PYTHON = (3, 10)

#: Heavyweight or optional imports that must never become install requirements.
OPTIONAL_ONLY = {
    "playwright",
    "fastapi",
    "uvicorn",
    "pybind11",
    "pytest",
    "ruff",
    "mypy",
}


def _load_toml() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def document() -> dict:
    return _load_toml()


@pytest.fixture(scope="module")
def project(document) -> dict:
    return document["project"]


@pytest.fixture(scope="module")
def setuptools_table(document) -> dict:
    return document["tool"]["setuptools"]


def _dependency_names(requirements: list[str]) -> set[str]:
    """Bare project names from PEP 621 requirement strings, lower-cased."""
    names: set[str] = set()
    for requirement in requirements:
        match = re.match(r"[A-Za-z0-9_.\-]+", requirement.strip())
        if match is not None:
            names.add(match.group(0).lower().replace("_", "-"))
    return names


def _script_target(value: str) -> tuple[str, str]:
    module, _, attribute = value.partition(":")
    assert module and attribute, f"console script {value!r} is not 'module:attribute'"
    return module, attribute


def _module_defines(module: str, attribute: str) -> bool:
    """Whether ``attribute`` is defined at ``module`` top level, no import."""
    spec = importlib.util.find_spec(module)
    assert spec is not None and spec.origin is not None, f"cannot locate {module!r}"
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == attribute:
                return True
        elif isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == attribute
                for target in node.targets
            ):
                return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == attribute:
                return True
    return False


def _workflow() -> dict:
    return yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))


def _steps(job: dict) -> list[dict]:
    return [step for step in job.get("steps") or [] if isinstance(step, dict)]


def _run_commands(workflow: dict) -> list[str]:
    commands: list[str] = []
    for job in (workflow.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in _steps(job):
            if isinstance(step.get("run"), str):
                commands.append(step["run"])
    return commands


def _job_with_matrix_key(workflow: dict, key: str) -> dict:
    for job in (workflow.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        if key in matrix:
            return job
    raise AssertionError(f"no CI job declares a matrix key {key!r}")


def _matrix_values(job: dict, key: str) -> list[str]:
    return [str(value) for value in job["strategy"]["matrix"][key]]


# -- build metadata -----------------------------------------------------------


def test_metadata_files_are_present() -> None:
    assert PYPROJECT.is_file()
    assert (ROOT / "README.md").is_file()
    assert (PACKAGE / "__init__.py").is_file()


def test_package_version_matches_metadata(project) -> None:
    import omniframe

    assert project["name"] == "omniframe-studio"
    assert re.fullmatch(r"\d+\.\d+\.\d+", project["version"]), project["version"]
    assert omniframe.__version__ == project["version"]


def test_requires_python_meets_platform_floor(project) -> None:
    spec = str(project["requires-python"]).strip()
    # An upper bound would silently drop interpreters our installers target.
    assert "<" not in spec, f"requires-python must not cap the interpreter: {spec!r}"
    match = re.fullmatch(r">=\s*(\d+)\.(\d+)", spec)
    assert match is not None, f"unexpected requires-python: {spec!r}"
    floor = (int(match.group(1)), int(match.group(2)))
    assert floor >= MIN_PYTHON, f"requires-python floor {floor} is below {MIN_PYTHON}"


def test_core_dependencies_stay_host_free(project) -> None:
    names = _dependency_names(project["dependencies"])
    # The agent surface needs these unconditionally.
    assert {"pydantic", "pyyaml", "typer", "pillow"} <= names
    # Optional engines must stay opt-in extras, never install requirements.
    assert not (names & OPTIONAL_ONLY), sorted(names & OPTIONAL_ONLY)


def test_optional_extras_are_declared(project) -> None:
    extras = project["optional-dependencies"]
    assert {"render", "ui", "native", "dev"} <= set(extras)
    assert "playwright" in _dependency_names(extras["render"])
    assert {"fastapi", "uvicorn"} <= _dependency_names(extras["ui"])
    assert "pybind11" in _dependency_names(extras["native"])
    assert {"pytest", "ruff", "mypy"} <= _dependency_names(extras["dev"])


def test_dev_extra_carries_the_toml_reader_for_python_310(project) -> None:
    requirements = project["optional-dependencies"]["dev"]
    readers = [item for item in requirements if item.lower().startswith("tomli")]
    assert readers, "the dev extra must declare tomli for Python 3.10"
    # Guarded so the dependency stays off 3.11+, where tomllib is stdlib.
    assert any("3.11" in item for item in readers), readers


# -- console scripts ----------------------------------------------------------


def test_console_scripts_are_declared(project) -> None:
    scripts = project["scripts"]
    assert scripts["omniframe"] == "omniframe.cli.main:run"
    assert scripts["mcp"] == "omniframe.mcp_server:main"


def test_console_script_targets_define_the_entry_callable(project) -> None:
    for name, value in sorted(project["scripts"].items()):
        module, attribute = _script_target(value)
        assert _module_defines(module, attribute), f"{name}: {module}.{attribute} missing"


# -- package data -------------------------------------------------------------


def test_py_typed_marker_ships_with_the_package(setuptools_table) -> None:
    declared = setuptools_table["package-data"]["omniframe"]
    assert "py.typed" in declared
    marker = PACKAGE / "py.typed"
    assert marker.is_file(), "py.typed is declared but not present in the package"
    # "partial" would opt every module out of the PEP 561 promise; we are typed.
    assert marker.read_text(encoding="utf-8").strip() != "partial"


def test_agent_schemas_are_package_data(setuptools_table) -> None:
    declared = setuptools_table["package-data"]["omniframe"]
    assert "agent/schemas/*.json" in declared
    schemas = sorted((PACKAGE / "agent" / "schemas").glob("*.json"))
    assert schemas, "no agent schema JSON files found to ship"
    parsed = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in schemas}
    tools = parsed["tools.json"]
    assert isinstance(tools.get("tools"), list) and tools["tools"]


# -- layout ------------------------------------------------------------------


def test_src_layout_is_authoritative(setuptools_table) -> None:
    assert setuptools_table["package-dir"] == {"": "src"}
    found = setuptools_table["packages"]["find"]
    assert found["where"] == ["src"]
    # An importable copy at the repository root would shadow the installed one.
    assert not (ROOT / "omniframe").exists()
    assert (PACKAGE / "__init__.py").is_file()


def test_build_backend_is_setuptools(document) -> None:
    build = document["build-system"]
    assert build["build-backend"] == "setuptools.build_meta"
    assert any(item.startswith("setuptools") for item in build["requires"])


# -- CI workflow -------------------------------------------------------------

#: Proprietary host binaries. CI must never try to launch one of these.
HOST_BINARIES = ("premiere", "afterfx", "resolve", "capcut", "krita")


def test_ci_workflow_exists() -> None:
    assert CI_WORKFLOW.is_file()
    assert _workflow()["jobs"]


def test_ci_matrix_covers_supported_python_versions() -> None:
    job = _job_with_matrix_key(_workflow(), "python-version")
    versions = set(_matrix_values(job, "python-version"))
    assert {"3.10", "3.11", "3.12"} <= versions, sorted(versions)


def test_ci_installs_without_and_with_dev_extras() -> None:
    job = _job_with_matrix_key(_workflow(), "extras")
    assert {"", "[dev]"} <= set(_matrix_values(job, "extras"))
    commands = "\n".join(step.get("run") or "" for step in _steps(job))
    assert "matrix.extras" in commands
    assert "pip install -e" in commands


def test_ci_builds_and_inspects_a_wheel() -> None:
    commands = "\n".join(_run_commands(_workflow()))
    assert "pip wheel" in commands, "CI must build a distribution artifact"
    # The wheel is read back and its payload asserted, not merely built.
    assert "py.typed" in commands
    assert "agent/schemas" in commands


def test_ci_smoke_tests_the_console_script() -> None:
    assert "omniframe --help" in "\n".join(_run_commands(_workflow()))


def test_ci_never_invokes_a_proprietary_host() -> None:
    commands = "\n".join(_run_commands(_workflow())).lower()
    offenders = [binary for binary in HOST_BINARIES if binary in commands]
    assert not offenders, f"CI must not launch host applications: {offenders}"



