FROM python:3.11-slim

LABEL org.opencontainers.image.title="Mecha"
LABEL org.opencontainers.image.description="A safety-first Coding Agent Harness"
LABEL org.opencontainers.image.version="0.1.0"

WORKDIR /workspace

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --break-system-packages \
    openai keyring pyyaml && \
    pip install --no-cache-dir --break-system-packages pytest

# Copy source code
COPY mecha/ /workspace/mecha/
COPY tests/ /workspace/tests/
COPY demo/ /workspace/demo/
COPY README.md .

# Create volume for persistent config
VOLUME ["/root/.mecha"]

# Set up entrypoint
ENTRYPOINT ["python", "-m", "mecha.cli"]