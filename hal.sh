#!/bin/bash

ENV_NAME="hal_env"

# Create environment if it doesn't exist
if ! conda env list | grep -q "^$ENV_NAME "; then
    echo "Creating conda environment '$ENV_NAME'..."
    conda create -y -n "$ENV_NAME" python=3.11
    conda run -n "$ENV_NAME" pip install ollama
fi

conda run --no-capture-output -n "$ENV_NAME" python3 -u "$(dirname "$0")/main.py" "$@"
