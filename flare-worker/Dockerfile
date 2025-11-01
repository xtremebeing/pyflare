FROM docker.io/cloudflare/sandbox:0.4.14

# On a Mac with Apple Silicon, you might need to specify the platform:
# FROM --platform=linux/arm64 docker.io/cloudflare/sandbox:0.4.14

# Install cloudpickle which we need for serialization
# Pin to same version as client to avoid compatibility issues
RUN pip install --no-cache-dir 'cloudpickle>=3.0.0,<4.0.0'

# Required during local development to access exposed ports
EXPOSE 8080
