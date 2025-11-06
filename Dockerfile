# Dockerfile — Ubuntu 24.04, install minimal deps and Blender tarball (no CUDA inside image)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ARG BLENDER_VER=4.2.14
# Use /opt/app as the application root inside the image to avoid accidental
# host bind mounts over /app hiding baked-in files. Keep /app for backward
# compat where needed, but we will run the app from /opt/app.
WORKDIR /opt/app

# Install OS deps (ensure wget/tar/xz-utils present). Use libgl1 + common X libs compatible with 24.04.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates wget xz-utils tar \
    curl gnupg \
    libgl1 libx11-6 libxext6 libxrender1 libxrandr2 \
    libxfixes3 libxi6 libxxf86vm1 libxkbcommon0 \
    libxcursor1 libxinerama1 libsm6 libice6 \
    git python3 python3-pip python3-setuptools \
    python3-flask python3-gunicorn python3-requests python3-flask-cors \
    && rm -rf /var/lib/apt/lists/*

# Download and extract Blender tarball
RUN mkdir -p /opt/blender
WORKDIR /opt/blender
RUN wget -q "https://download.blender.org/release/Blender${BLENDER_VER%.*}/blender-${BLENDER_VER}-linux-x64.tar.xz" \
    && tar -xf blender-${BLENDER_VER}-linux-x64.tar.xz \
    && rm blender-${BLENDER_VER}-linux-x64.tar.xz \
    && mv blender-${BLENDER_VER}-linux-x64 /opt/blender/current

WORKDIR /app

# Set up directory structure
# Create directories under /opt/app and copy application code there
RUN mkdir -p /opt/app/output /opt/app/main /opt/app/blender_agent

# Copy application code into the image (so the image works without host mounts)
COPY server/. /opt/app/main/
COPY agent/. /opt/app/blender_agent/

# Copy and build the frontend so Flask can serve it from ../frontend/build
# Copy frontend source AND build directory if it exists
COPY frontend/ /opt/app/frontend/
# NOTE: Building the React frontend inside the Docker image can be
# brittle due to npm dependency/tooling differences. The Flask app is
# already able to serve a built frontend from /opt/app/frontend/build
# if present. To avoid long, fragile builds in the image we copy the
# frontend source here and expect the build to be produced outside the
# image (or you can run a separate build container). If you want the
# image to build the frontend during docker build, re-add Node install
# and `npm run build` here.

# Return to app WORKDIR
WORKDIR /opt/app/main

# Make sure the startup script is executable and in the right place
COPY server/startup.sh /usr/local/bin/startup.sh
RUN chmod +x /usr/local/bin/startup.sh

# Python packages required by the agent were installed via apt (python3-flask, python3-requests, python3-gunicorn)
# Skip pip install here to avoid PEP 668 'externally-managed-environment' errors on Ubuntu 24.04.

EXPOSE 8000
# Expose the output directory as a volume (mapped to host ./output in compose)
VOLUME ["/opt/app/output"]

ENTRYPOINT ["/usr/local/bin/startup.sh"]
