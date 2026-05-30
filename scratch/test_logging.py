import os
import sys
sys.path.insert(0, './src')

from core.tool_registry import ToolRegistry
from core.logging_config import setup_logging
import logging

setup_logging(mode='bot')
registry = ToolRegistry()

@registry.register(name='test_success', description='desc', parameters={})
def test_success():
    return 'Yay'

@registry.register(name='test_error', description='desc', parameters={})
def test_error():
    raise ValueError('Simulated Error')

@registry.register(name='test_str_err', description='desc', parameters={})
def test_str_err():
    return 'Error: Failed to connect'

print("--- Testing Success ---")
registry.execute('test_success', {})

print("\n--- Testing Exception Error ---")
registry.execute('test_error', {})

print("\n--- Testing String Error ---")
registry.execute('test_str_err', {})
