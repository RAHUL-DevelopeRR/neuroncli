#!/bin/bash
# NeuronCLI — Install script for Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/RAHUL-DevelopeRR/neuroncli/master/install.sh | bash

set -e

echo ""
echo "  Installing NeuronCLI..."
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "  Error: Python 3.10+ is required."
    echo "  Install it from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo "  Error: Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi

# Install via pip
echo "  Python $PYTHON_VERSION detected"
echo "  Installing from PyPI..."
pip3 install --upgrade neuroncli

# Verify
if command -v neuron &> /dev/null; then
    echo ""
    echo "  NeuronCLI installed successfully!"
    echo "  Run 'neuron' in any project directory to start."
    echo ""
else
    echo ""
    echo "  Installed, but 'neuron' not in PATH."
    echo "  Try: python3 -m neuroncli"
    echo "  Or add ~/.local/bin to your PATH"
    echo ""
fi
