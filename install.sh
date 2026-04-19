#!/bin/bash
# NeuronCLI — Install script for Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/RAHUL-DevelopeRR/neuroncli/master/install.sh | bash

set -e

echo ""
echo "  Installing NeuronCLI v2.1..."
echo ""

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "  Error: Python 3.10+ is required."
    echo "  Install: sudo apt install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo "  Error: Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi

echo "  Python $PYTHON_VERSION detected"

# Try pipx first (recommended for modern Debian/Ubuntu/Fedora)
if command -v pipx &> /dev/null; then
    echo "  Installing via pipx (recommended)..."
    pipx install neuroncli
    echo ""
    echo "  NeuronCLI installed via pipx!"
    echo "  Run 'neuron' to start."
    echo ""
    exit 0
fi

# Try pip with --user flag
echo "  Trying pip install..."
if pip3 install --user neuroncli 2>/dev/null; then
    echo ""
    echo "  NeuronCLI installed!"
    echo "  Run 'neuron' to start."
    echo ""
    exit 0
fi

# If pip fails (externally-managed-environment), offer pipx
echo ""
echo "  pip install blocked by system (PEP 668)."
echo "  This is normal on modern Debian/Ubuntu/Fedora."
echo ""
echo "  Fix: Install pipx and retry:"
echo ""
echo "    sudo apt install pipx        # Debian/Ubuntu"
echo "    sudo dnf install pipx        # Fedora"
echo "    brew install pipx            # macOS"
echo ""
echo "    pipx ensurepath"
echo "    pipx install neuroncli"
echo ""
echo "  Or force pip (not recommended):"
echo "    pip install neuroncli --break-system-packages"
echo ""
