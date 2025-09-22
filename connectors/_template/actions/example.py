#!/usr/bin/env python3
"""Example action used during setup flows."""

import json
import sys


def main() -> None:
    payload = {
        "ok": True,
        "result": {
            "message": "Hello from the connector template"
        }
    }
    json.dump(payload, sys.stdout)


if __name__ == '__main__':
    main()
