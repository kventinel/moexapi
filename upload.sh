#!/usr/bin/env bash
rm -r dist || true
python3 -m build
python3 -m twine upload dist/*
