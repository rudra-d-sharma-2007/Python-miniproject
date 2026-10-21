#!/bin/sh
# Build the static site into dist/ for production hosting.
# No dependencies to install: plain HTML/CSS/JS plus the Python module it fetches.
set -e

rm -rf dist
mkdir -p dist
cp web/* dist/
cp duplicate_detector.py dist/
