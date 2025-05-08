#!/bin/bash
# Simple script to format Python code

# Check if files are provided as arguments
if [ $# -eq 0 ]; then
  # No arguments, format all Python files in the project
  FILES=$(find . -name "*.py" | grep -v "__pycache__" | grep -v ".venv" | grep -v "env")
else
  # Format only the specified files
  FILES="$@"
fi

echo "Formatting files: $FILES"

# Run formatters and linters
echo "Running isort..."
isort $FILES

echo "Running black..."
black $FILES

echo "Running ruff with auto-fix..."
ruff check --fix $FILES

echo "Running flake8 (checks only)..."
flake8 $FILES || echo "⚠️ Flake8 found some issues."

echo "Done!"
