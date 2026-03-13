#!/bin/bash

# ---- Start Jupyter Notebook ----
# Run this script from your project folder whenever
# you want to use Jupyter notebooks in PyCharm.
#
# What it does:
#   1. Makes sure your Docker container is running.
#   2. Starts a Jupyter Notebook server inside it.
#
# Usage:
#   Open a second terminal tab, navigate to your
#   project folder, and run:
#       ./start_jupyter.sh
#
# To stop the Jupyter server, press Ctrl+C in this
# terminal. Your container will keep running for
# PyCharm to use with .py files.
#
# PyCharm Configured Server URL:
#   http://127.0.0.1:8888/tree?token=mytoken

docker compose up -d
docker compose exec app jupyter notebook \
  --ip=0.0.0.0 \
  --port=8888 \
  --no-browser \
  --allow-root \
  --NotebookApp.token='mytoken'
