import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_role_ops_imports_when_tools_directory_is_on_pythonpath(tmp_role_home):
    env = os.environ.copy()
    env["ROLEME_HOME"] = str(tmp_role_home)
    env["PYTHONPATH"] = "tools"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from role_ops import list_roles, role_dir; "
                "print(list_roles()); "
                "print(role_dir('zhaochao'))"
            ),
        ],
        check=True,
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
    )

    assert "[]" in result.stdout
    assert str(tmp_role_home / "zhaochao") in result.stdout


@pytest.mark.parametrize("tools_dir", ["tools", "skills/roleme/tools"])
def test_all_tool_modules_import_when_tools_directory_is_on_pythonpath(tmp_path, tools_dir):
    tool_modules = sorted(
        path.stem
        for path in (Path.cwd() / tools_dir).glob("*.py")
        if path.name != "__init__.py"
    )
    code = "import importlib; " + "; ".join(
        f"importlib.import_module({module!r})" for module in tool_modules
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        cwd=tmp_path,
        env={"PYTHONPATH": str(Path.cwd() / tools_dir)},
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("package_root", [".", "skills/roleme"])
def test_all_tool_modules_import_when_package_root_is_on_pythonpath(tmp_path, package_root):
    tools_dir = Path.cwd() / package_root / "tools"
    tool_modules = sorted(
        f"tools.{path.stem}"
        for path in tools_dir.glob("*.py")
        if path.name != "__init__.py"
    )
    code = "import importlib; " + "; ".join(
        f"importlib.import_module({module!r})" for module in tool_modules
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        cwd=tmp_path,
        env={"PYTHONPATH": str(Path.cwd() / package_root)},
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


def test_python_files_do_not_contain_local_machine_paths():
    roots = [
        Path("bundle"),
        Path("scripts"),
        Path("skills/roleme"),
        Path("templates"),
        Path("tools"),
    ]
    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "/Users/zhaochao" in text:
                offenders.append(str(path))

    assert offenders == []
