# ---- Base Image ----
# This is the foundation of your environment.
# python:3.12.12-slim is the official Python image,
# based on Debian Linux, with Python 3.12.12 pre-installed.
# "slim" means it includes only the essentials (~150 MB),
# unlike the full image (~900 MB) which has extras you
# probably do not need.
#
# CHANGE 3.12.12 to whatever Python version you want.
# Browse available versions at: hub.docker.com/_/python/tags
FROM python:3.12.12-slim

# ---- System-Level Dependencies ----
# Some Python libraries (numpy, pandas, scipy, etc.)
# contain C/C++ code that needs to be compiled during
# pip install. The 'build-essential' and 'gcc' packages
# provide the compilers needed for this.
# 'git' is included so pip can install packages directly
# from Git repositories if needed.
# The final 'rm' command deletes the package manager
# cache to keep the image size small.
RUN apt-get update && apt-get install -y --no-install-recommends \
build-essential \
gcc \
git \
curl \
wget \
&& rm -rf /var/lib/apt/lists/*

# ---- Install Quarto ----
# Quarto is a standalone CLI tool.
# We download the official .deb installer from GitHub
# releases and install it with dpkg.
#
# CHANGE the version number below when you want to
# upgrade. Browse releases at:
# https://github.com/quarto-dev/quarto-cli/releases
#
# We pin the version for reproducibility, just like
# we pin pip package versions in requirements.txt.
ARG QUARTO_VERSION=1.8.27
RUN curl -LO https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.deb \
    && dpkg -i quarto-${QUARTO_VERSION}-linux-amd64.deb \
    && rm quarto-${QUARTO_VERSION}-linux-amd64.deb

# ---- Install TinyTeX (LaTeX) ----
# Quarto ships with a built-in TinyTeX installer that
# gives you a minimal, Quarto-aware TeX distribution.
# Additional LaTeX packages are auto-installed on first
# use, but we pre-install a few common ones to avoid
# surprises at render time.
RUN quarto install tinytex --no-prompt \
    && ~/.TinyTeX/bin/*/tlmgr install \
        amsmath \
        amsfonts \
        booktabs \
        caption \
        geometry \
        hyperref \
        natbib \
        fancyhdr \
        setspace \
        xcolor

# ---- Working Directory ----
# Creates the /app directory inside the container and
# sets it as the default directory. All commands after
# this (COPY, RUN, CMD) will run relative to /app.
# When you open a terminal inside the container, you
# will start in /app.
WORKDIR /app

# ---- Install Python Libraries ----
# IMPORTANT: We copy ONLY requirements.txt first,
# BEFORE copying the rest of our code.
# Docker builds images in layers, and each layer is
# cached. If requirements.txt has not changed since
# the last build, Docker will skip the pip install
# entirely and use the cache. This saves minutes on
# rebuilds when you only changed your code, not your
# dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt

# ---- Copy Project Code ----
# Now copy everything else into the container.
# Because this is a separate layer from the pip install,
# changing your code does NOT re-trigger the (slow)
# pip install step.
COPY . .

# ---- Default Command ----
# This runs when you start the container without
# specifying a command. PyCharm overrides this when
# running your scripts, so this is mainly a fallback.
CMD ["python", "main.py"]