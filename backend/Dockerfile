FROM python:3.12-slim

# --- Install tac_plus-ng dependencies and supervisor ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    automake \
    libtool \
    libc-ares-dev \
    pkg-config \
    curl \
    libcurl4-openssl-dev \
    libevent-dev \
    libpam0g-dev \
    libssl-dev \
    libpcre2-dev \
    perl \
    libauthen-radius-perl \
    libnet-ldap-perl \
    libnet-ip-perl \
    libsys-syslog-perl \
    unzip \
    wget \
    supervisor \
    procps \
    && rm -rf /var/lib/apt/lists/*

# --- Download and install tac_plus-ng ---
# We set LDFLAGS to ensure the linker finds the libraries in their standard locations.
RUN set -eux; \
    export LDFLAGS="-L/usr/lib/x86_64-linux-gnu"; \
    wget https://github.com/MarcJHuber/event-driven-servers/archive/refs/heads/master.zip -O event-driven-servers-master.zip; \
    unzip event-driven-servers-master.zip; \
    cd event-driven-servers-master && ./configure && make && make install; \
    cd / && rm -rf event-driven-servers-master.zip event-driven-servers-master

ENV PYTHONUNBUFFERED=1

WORKDIR /app/

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

ENV PYTHONPATH=/app

COPY ./tacacs_config /app/tacacs_config

COPY ./scripts /app/scripts

COPY ./pyproject.toml ./uv.lock ./alembic.ini /app/

COPY ./supervisord.conf /etc/supervisor/conf.d/supervisord.conf

COPY ./app /app/app
COPY ./tests /app/tests

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
