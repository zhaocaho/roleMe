import importlib


def test_tools_package_is_importable():
    tools_pkg = importlib.import_module("tools")
    assert hasattr(tools_pkg, "__file__")
