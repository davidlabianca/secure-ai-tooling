FROM ubuntu:noble

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}
ARG WORKSPACE=/workspaces
ARG WORKSPACE_REPO=secure-ai-tooling

# Install system packages: core utilities + Playwright Chromium system dependencies
# Core: sudo, build-essential, bash-completion, vim, curl, wget, git, ca-certificates
# Playwright deps: 31 packages needed by Chromium on Ubuntu Noble (with t64 suffixes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    build-essential \
    bash-completion \
    vim \
    curl \
    wget \
    git \
    ca-certificates \
    libasound2t64 \
    libatk-bridge2.0-0t64 \
    libatk1.0-0t64 \
    libatspi2.0-0t64 \
    libcairo2 \
    libcups2t64 \
    libdbus-1-3 \
    libdrm2 \
    libegl1 \
    libgbm1 \
    libglib2.0-0t64 \
    libgtk-3-0t64 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xvfb \
    fonts-noto-color-emoji \
    fonts-unifont \
    libfontconfig1 \
    libfreetype6 \
    libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

# Create vscode user with configurable UID/GID
RUN groupadd --gid ${USER_GID} ${USERNAME} && \
    useradd --uid ${USER_UID} --gid ${USER_GID} --shell /bin/bash --create-home ${USERNAME} \
    && echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# Create workspace directory with proper permissions
RUN mkdir -p ${WORKSPACE}/${WORKSPACE_REPO} && chown -R ${USERNAME}:${USERNAME} ${WORKSPACE}

USER ${USERNAME}
WORKDIR ${WORKSPACE}/${WORKSPACE_REPO}
