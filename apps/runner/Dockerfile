FROM python:3.12-slim

WORKDIR /app

# Install git (needed for workspace operations)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY apps/ apps/

# Install dependencies
RUN pip install --no-cache-dir .

# Create workspace directory
RUN mkdir -p /tmp/workspaces

ENV LAILATOV_WORKSPACE_ROOT=/tmp/workspaces
ENV PORT=8001

EXPOSE 8001

CMD ["uvicorn", "apps.runner.main:app", "--host", "0.0.0.0", "--port", "8001"]
