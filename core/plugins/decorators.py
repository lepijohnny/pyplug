from typing import Callable


def on_setup(func: Callable):
    func._rpc_method = "setup"
    return func


def on_run(func: Callable):
    func._rpc_method = "run"
    return func


def on_teardown(func: Callable):
    func._rpc_method = "teardown"
    return func


def on_kill(func: Callable):
    func._rpc_method = "kill"
    return func
