#!/usr/bin/env bash
# setup.sh — One-command production bootstrap.
#
# Creates .env from .env.example, generates every secret, starts Traefik under
# its own Compose project, then brings the application up.
#
# Usage:
#   bash setup.sh                 # interactive
#   DOMAIN=tacacs.example.com FIRST_SUPERUSER=admin@example.com bash setup.sh --yes
#   bash setup.sh --config-only   # write .env and stop, deploy by hand later
#
# Re-running is safe: an existing .env is never overwritten. Use --reconfigure
# to regenerate it (the old file is kept as .env.bak).

set -euo pipefail

ENV_FILE="./.env"
ENV_EXAMPLE="./.env.example"
TRAEFIK_PROJECT="traefik-public"
ASSUME_YES=0
RECONFIGURE=0
CONFIG_ONLY=0

for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    --reconfigure) RECONFIGURE=1 ;;
    --config-only) CONFIG_ONLY=1 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\033[31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- prerequisites

say "[1/6] Checking prerequisites"

command -v docker  >/dev/null || die "docker is not installed. See https://docs.docker.com/engine/install/"
command -v openssl >/dev/null || die "openssl is not installed (apt install openssl)."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is missing. 'docker compose version' must work."
docker info >/dev/null 2>&1 || die "Cannot talk to the Docker daemon. Run as a user in the 'docker' group, or with sudo."
[[ -f "$ENV_EXAMPLE" ]] || die "$ENV_EXAMPLE not found. Run this from the repository root."

info "docker $(docker version -f '{{.Server.Version}}'), compose $(docker compose version --short), openssl present"

# ------------------------------------------------------------------------ .env

# set_env KEY VALUE — replace the first "KEY=" line in $ENV_FILE, appending if
# absent. awk is used rather than sed because the values contain "$", "/" and
# "&", all of which sed would interpret.
set_env() {
  local key="$1" val="$2" tmp
  tmp="$(mktemp)"
  KEY="$key" VAL="$val" awk '
    BEGIN { key = ENVIRON["KEY"]; val = ENVIRON["VAL"]; done = 0 }
    !done && index($0, key "=") == 1 { print key "=" val; done = 1; next }
    { print }
    END { if (!done) print key "=" val }
  ' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
}

# ask VARNAME "prompt" [default] — honours an already-exported value and --yes.
# A default of OPTIONAL means an empty answer is accepted.
ask() {
  local var="$1" prompt="$2" default="${3:-}" current answer
  current="${!var:-}"
  if [[ -n "$current" ]]; then info "$var=$current (from environment)"; return; fi
  if [[ "$ASSUME_YES" == 1 ]]; then
    [[ -n "$default" ]] || die "$var must be set when running with --yes."
    [[ "$default" == OPTIONAL ]] && default=""
    printf -v "$var" '%s' "$default"; info "$var=${default:-(empty)} (default)"; return
  fi
  if [[ "$default" == OPTIONAL ]]; then
    read -rp "  $prompt: " answer
    printf -v "$var" '%s' "$answer"
  elif [[ -n "$default" ]]; then
    read -rp "  $prompt [$default]: " answer
    printf -v "$var" '%s' "${answer:-$default}"
  else
    while :; do
      read -rp "  $prompt: " answer
      [[ -n "$answer" ]] && break
      echo "  (required)"
    done
    printf -v "$var" '%s' "$answer"
  fi
}

say "[2/6] Configuring .env"

if [[ -f "$ENV_FILE" && "$RECONFIGURE" == 0 ]]; then
  info ".env already exists — keeping it. Pass --reconfigure to regenerate."
  KEEP_ENV=1
else
  KEEP_ENV=0
  [[ -f "$ENV_FILE" ]] && { cp "$ENV_FILE" .env.bak; info "Existing .env backed up to .env.bak"; }
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"

  ask DOMAIN          "Domain the application is served on (e.g. tacacs.example.com)"
  ask TOOLS_DOMAIN    "Domain carrying adminer. and traefik. (blank = nest under $DOMAIN)" OPTIONAL
  ask FIRST_SUPERUSER "Admin login email"
  ask EMAIL           "Let's Encrypt contact email" "$FIRST_SUPERUSER"
  ask TZ              "Timezone (drives TACACS+ log cron)" "$(cat /etc/timezone 2>/dev/null || echo UTC)"
  ask USERNAME        "Username for the Traefik/tools dashboard" "admin"

  TOOLS_DOMAIN="${TOOLS_DOMAIN// /}"

  # Secrets. FIRST_SUPERUSER_PASSWORD and TOOLS_PASSWORD are shown once at the
  # end; the rest are never needed by a human.
  SECRET_KEY="$(openssl rand -hex 32)"
  POSTGRES_PASSWORD="$(openssl rand -hex 24)"
  INTERNAL_SYNC_TOKEN="$(openssl rand -hex 32)"
  FIRST_SUPERUSER_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
  TOOLS_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"

  # Traefik basic-auth hash. Compose interpolates "$" inside .env values, so
  # every "$" is doubled here — a raw hash reaches Traefik mangled and rejects
  # every password without logging why.
  # Passed on stdin, not as an argument, so it never appears in "ps".
  HASHED_PASSWORD="$(printf '%s' "$TOOLS_PASSWORD" | openssl passwd -apr1 -stdin | sed -e 's/\$/\$\$/g')"

  set_env DOMAIN                   "$DOMAIN"
  set_env TOOLS_DOMAIN             "$TOOLS_DOMAIN"
  set_env FRONTEND_HOST            "https://$DOMAIN"
  set_env ENVIRONMENT              "production"
  set_env TZ                       "$TZ"
  set_env SECRET_KEY               "$SECRET_KEY"
  set_env FIRST_SUPERUSER          "$FIRST_SUPERUSER"
  set_env FIRST_SUPERUSER_PASSWORD "$FIRST_SUPERUSER_PASSWORD"
  set_env POSTGRES_PASSWORD        "$POSTGRES_PASSWORD"
  set_env INTERNAL_SYNC_TOKEN      "$INTERNAL_SYNC_TOKEN"
  set_env USERS_OPEN_REGISTRATION  "False"
  set_env EMAIL                    "$EMAIL"
  set_env USERNAME                 "$USERNAME"
  set_env HASHED_PASSWORD          "$HASHED_PASSWORD"
  # Only consulted when the provider is configured, but wrong values here are a
  # confusing failure much later, so point them at the real host now.
  set_env GOOGLE_REDIRECT_URI      "https://$DOMAIN/api/v1/oauth/google/callback"
  set_env KEYCLOAK_REDIRECT_URI    "https://$DOMAIN/api/v1/oauth/keycloak/callback"

  info "Wrote $ENV_FILE (mode 600)"
fi

# Read back, so a kept .env drives the rest of the run.
read_env() { grep -m1 "^$1=" "$ENV_FILE" | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
DOMAIN="$(read_env DOMAIN)"
TOOLS_DOMAIN="$(read_env TOOLS_DOMAIN)"
TOOLS_HOST="${TOOLS_DOMAIN:-$DOMAIN}"
[[ -n "$DOMAIN" && "$DOMAIN" != "localhost" ]] || die "DOMAIN in .env is unset or still 'localhost'."

if [[ "$CONFIG_ONLY" == 1 ]]; then
  say "Configuration written — stopping here (--config-only)"
  info "Deploy with: docker compose -p $TRAEFIK_PROJECT -f docker-compose.traefik.yml up -d"
  info "         and: docker compose -f docker-compose.yml up -d --build"
  if [[ "$KEEP_ENV" == 0 ]]; then
    printf '\n  Application   %s / %s\n  Tools (HTTP)  %s / %s\n\n' \
      "$FIRST_SUPERUSER" "$FIRST_SUPERUSER_PASSWORD" "$USERNAME" "$TOOLS_PASSWORD"
  fi
  exit 0
fi

# ---------------------------------------------------------------------- DNS

say "[3/6] Checking DNS"

server_ip="$(curl -fsS --max-time 10 https://ifconfig.me 2>/dev/null || echo "")"
dns_warn=0
for host in "$DOMAIN" "traefik.$TOOLS_HOST" "adminer.$TOOLS_HOST"; do
  resolved="$(getent ahostsv4 "$host" 2>/dev/null | awk 'NR==1{print $1}')"
  if [[ -z "$resolved" ]]; then
    info "$host -> (no A record)"; dns_warn=1
  elif [[ -n "$server_ip" && "$resolved" != "$server_ip" ]]; then
    info "$host -> $resolved (server is $server_ip)"; dns_warn=1
  else
    info "$host -> $resolved"
  fi
done
if [[ "$dns_warn" == 1 ]]; then
  echo
  info "DNS is incomplete. Certificates cannot be issued for a host that does not"
  info "resolve here, and Traefik will serve its self-signed default instead."
  if [[ "$ASSUME_YES" == 0 ]]; then
    read -rp "  Continue anyway? [y/N]: " cont
    [[ "$cont" =~ ^[Yy]$ ]] || die "Aborted. Point the A records at $server_ip and re-run."
  fi
fi

# ------------------------------------------------------------------- traefik

say "[4/6] Starting Traefik"

docker network inspect "$TRAEFIK_PROJECT" >/dev/null 2>&1 || docker network create "$TRAEFIK_PROJECT"

# -p is what keeps Traefik out of the application's Compose project. Without it
# each stack reports the other's containers as orphans, and a --remove-orphans
# on either one deletes the other.
existing_project="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' \
  "$(docker ps -aqf 'label=com.docker.compose.service=traefik' | head -1)" 2>/dev/null || true)"
if [[ -n "$existing_project" && "$existing_project" != "$TRAEFIK_PROJECT" ]]; then
  info "Found a Traefik container in Compose project '$existing_project' instead of"
  info "'$TRAEFIK_PROJECT'. Leaving it alone — see 'Already started it without -p'"
  info "in docs/en/deployment.md for how to move it."
else
  docker compose -p "$TRAEFIK_PROJECT" -f docker-compose.traefik.yml up -d
  info "Traefik running as project '$TRAEFIK_PROJECT'"
fi

# --------------------------------------------------------------- application

say "[5/6] Building and starting the application"

# -f docker-compose.yml alone: docker-compose.override.yml carries dev settings.
docker compose -f docker-compose.yml up -d --build

say "[6/6] Waiting for the stack to come up"

# "ps -q" plus "docker inspect" rather than a "ps --format" template: the
# template keys have changed between Compose releases, container inspection has
# not.
backend_health=""
for _ in $(seq 1 60); do
  backend_id="$(docker compose -f docker-compose.yml ps -q backend 2>/dev/null || true)"
  if [[ -n "$backend_id" ]]; then
    backend_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$backend_id" 2>/dev/null || true)"
    [[ "$backend_health" == "healthy" ]] && break
  fi
  sleep 5
done
[[ "$backend_health" == "healthy" ]] || info "backend is '$backend_health' after 5 minutes — continuing, but check its logs."

prestart_id="$(docker compose -f docker-compose.yml ps -aq prestart 2>/dev/null | head -1)"
prestart_code="$(docker inspect -f '{{.State.ExitCode}}' "$prestart_id" 2>/dev/null || echo 1)"
if [[ "$prestart_code" != "0" ]]; then
  info "Migrations did not finish cleanly. Logs:"
  docker compose -f docker-compose.yml logs prestart | tail -20
  die "prestart exited $prestart_code — the database is not initialised."
fi
info "Migrations and seed data applied"

if curl -fsS --max-time 20 "https://$DOMAIN/api/v1/utils/health-check/" >/dev/null 2>&1; then
  info "https://$DOMAIN is serving and the API answers"
else
  info "The stack is up, but https://$DOMAIN did not answer yet."
  info "Certificate issuance takes a few seconds on first request — retry shortly,"
  info "then check: docker compose -p $TRAEFIK_PROJECT -f docker-compose.traefik.yml logs"
fi

# ------------------------------------------------------------------ summary

cat <<EOF

────────────────────────────────────────────────────────────────
 Deployment complete

   Dashboard   https://$DOMAIN
   Swagger     https://$DOMAIN/docs
   MCP         https://$DOMAIN/mcp/
   Traefik     https://traefik.$TOOLS_HOST
   Adminer     https://adminer.$TOOLS_HOST
EOF

if [[ "$KEEP_ENV" == 0 ]]; then
  cat <<EOF

 Credentials — shown once, stored in .env

   Application   $FIRST_SUPERUSER / $FIRST_SUPERUSER_PASSWORD
   Tools (HTTP)  $USERNAME / $TOOLS_PASSWORD

 Save these now. Change the application password after first login.
EOF
fi

cat <<EOF
────────────────────────────────────────────────────────────────
EOF
