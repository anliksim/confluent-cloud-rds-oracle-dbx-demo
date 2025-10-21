# !/usr/bin/env sh

. $VENV_DIR/bin/activate

echo -e "\nInitializing workspace..."
echo "python version $(python --version)"
echo "pip version $(pip --version)"
echo "pulumi version $(pulumi version)"
echo -e "\nDone.\n"
