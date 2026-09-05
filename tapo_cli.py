"""Wrapper module for tapo-cli to support standard Python imports and CLI entry points."""
import importlib.util
import os
import sys

_script_path = os.path.join(os.path.dirname(__file__), 'tapo-cli.py')
_spec = importlib.util.spec_from_file_location("tapo_core", _script_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

tapo = _mod.tapo
main = _mod.tapo

if __name__ == '__main__':
    tapo()
