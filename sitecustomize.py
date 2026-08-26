"""Initialize the database startup hook only once.

The application currently registers a before-request function named ``startup``
that calls init_db() on every HTTP request. On PostgreSQL this can repeatedly
open connections and run ALTER TABLE statements, eventually causing Gunicorn
timeouts. Python imports sitecustomize during interpreter startup, so this
small compatibility shim prevents that hook from being registered as a
request hook and executes it once when the decorator is evaluated.
"""

from flask import Flask

_original_before_request = Flask.before_request


def _before_request_once(self, func):
    if func.__name__ == "startup":
        try:
            func()
        except Exception as exc:
            print(f"[startup] database initialization failed: {exc}", flush=True)
        return func
    return _original_before_request(self, func)


Flask.before_request = _before_request_once
