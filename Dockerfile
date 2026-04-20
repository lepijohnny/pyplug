FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY scripts/download_uv.py scripts/download_uv.py
RUN python3 scripts/download_uv.py

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN ./vendor/uv sync --frozen --no-dev

# Copy application
COPY core/ core/
COPY frontend/dist/ frontend/dist/
COPY Skill.md Skill.md

# Create default plugins mount point
RUN mkdir -p /plugins

EXPOSE 8000

CMD ["./vendor/uv", "run", "python", "-m", "core.app"]
