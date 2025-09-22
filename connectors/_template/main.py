#!/usr/bin/env python3
"""Entry point used inside the connector container."""

from connector import Connector


def main() -> None:
    connector = Connector()
    connector.start()


if __name__ == '__main__':
    main()
