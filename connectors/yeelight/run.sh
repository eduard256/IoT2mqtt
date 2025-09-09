#!/bin/bash
# Run script with automatic venv activation

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if venv exists, create if not
if [ ! -d "$DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$DIR/venv"
    echo "Installing dependencies..."
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
fi

# Activate venv and run the requested script
if [ "$1" == "setup" ]; then
    "$DIR/venv/bin/python" "$DIR/setup.py" "${@:2}"
elif [ "$1" == "manage" ]; then
    "$DIR/venv/bin/python" "$DIR/manage.py" "${@:2}"
else
    echo "Usage: ./run.sh [setup|manage] [options]"
    echo "  setup  - Create new Yeelight instance"
    echo "  manage - Manage existing instances"
    exit 1
fi