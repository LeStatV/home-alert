# The agent: one asyncio process. Copies are explicit -- never `COPY . .`, which would
# put .env and the data/ volume (Telethon session = full account access) in the image.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
# the image ships the example as its default config; a deployment mounts its own over it
COPY config.example.yaml ./config.yaml
COPY home_alert/ home_alert/
COPY profiles/ profiles/
RUN uv sync --frozen --no-dev
ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "--no-sync", "home-alert", "run"]
