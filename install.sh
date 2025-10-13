#!/usr/bin/env bash

# IoT2MQTT Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

INSTALL_DIR="/opt/iot2mqtt"
REPO_URL="https://github.com/eduard256/IoT2mqtt.git"
BRANCH="main"
LOG_FILE="/tmp/iot2mqtt-install-$$.log"
WEB_PORT_DEFAULT=8765

# ============================================================================
# Colors & Styling
# ============================================================================

if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
  BOLD=$(tput bold)
  DIM=$(tput dim)
  RESET=$(tput sgr0)
  CYAN=$(tput setaf 6)
  GREEN=$(tput setaf 2)
  YELLOW=$(tput setaf 3)
  RED=$(tput setaf 1)
  BLUE=$(tput setaf 4)
else
  BOLD="" DIM="" RESET="" CYAN="" GREEN="" YELLOW="" RED="" BLUE=""
fi

# ============================================================================
# Helper Functions
# ============================================================================

log() {
  local prefix="${CYAN}▸${RESET}"
  echo -e "${prefix} $*" | tee -a "$LOG_FILE"
}

success() {
  local prefix="${GREEN}✓${RESET}"
  echo -e "${prefix} ${GREEN}$*${RESET}" | tee -a "$LOG_FILE"
}

error() {
  local prefix="${RED}✗${RESET}"
  echo -e "${prefix} ${RED}$*${RESET}" | tee -a "$LOG_FILE"
}

step() {
  echo ""
  echo -e "${BOLD}${BLUE}━━━ $* ━━━${RESET}" | tee -a "$LOG_FILE"
}

run_cmd() {
  local desc="$1"
  shift
  log "$desc"
  if "$@" >>"$LOG_FILE" 2>&1; then
    success "Done"
  else
    error "Failed: $desc"
    error "Check log: $LOG_FILE"
    exit 1
  fi
}

show_header() {
  clear
  cat <<'EOF'

  ██╗ ██████╗ ████████╗██████╗ ███╗   ███╗ ██████╗ ████████╗████████╗
  ██║██╔═══██╗╚══██╔══╝╚════██╗████╗ ████║██╔═══██╗╚══██╔══╝╚══██╔══╝
  ██║██║   ██║   ██║    █████╔╝██╔████╔██║██║   ██║   ██║      ██║
  ██║██║   ██║   ██║   ██╔═══╝ ██║╚██╔╝██║██║▄▄ ██║   ██║      ██║
  ██║╚██████╔╝   ██║   ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║      ██║
  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚══▀▀═╝    ╚═╝      ╚═╝

EOF
  echo -e "  ${DIM}Direct IoT → MQTT • Zero Host Dependencies${RESET}"
  echo ""
}

get_lan_ip() {
  local ip
  if command -v ip >/dev/null 2>&1 && ip route get 1.1.1.1 >/dev/null 2>&1; then
    ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}')
  fi
  if [ -z "${ip:-}" ] && command -v hostname >/dev/null 2>&1; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
  echo "${ip:-127.0.0.1}"
}

# ============================================================================
# Sudo Setup
# ============================================================================

SUDO=""
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    error "This script requires root or sudo"
    exit 1
  fi
fi

# ============================================================================
# Package Manager Detection
# ============================================================================

detect_pkg_manager() {
  if command -v apt-get >/dev/null 2>&1; then echo "apt"; return; fi
  if command -v dnf >/dev/null 2>&1; then echo "dnf"; return; fi
  if command -v yum >/dev/null 2>&1; then echo "yum"; return; fi
  if command -v pacman >/dev/null 2>&1; then echo "pacman"; return; fi
  if command -v apk >/dev/null 2>&1; then echo "apk"; return; fi
  echo "unknown"
}

install_packages() {
  local pm="$1"
  shift
  case "$pm" in
    apt)
      $SUDO apt-get update -qq
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
      ;;
    dnf|yum)
      $SUDO "$pm" install -y "$@"
      ;;
    pacman)
      $SUDO pacman -Sy --noconfirm "$@"
      ;;
    apk)
      $SUDO apk add --no-cache "$@"
      ;;
    *)
      return 1
      ;;
  esac
}

# ============================================================================
# Main Installation
# ============================================================================

main() {
  show_header

  # Initialize log
  echo "Installation started at $(date)" > "$LOG_FILE"

  # Step 1: Check system
  step "Checking System"

  PM=$(detect_pkg_manager)
  log "Package manager: ${PM}"

  if ! command -v git >/dev/null 2>&1; then
    run_cmd "Installing git" install_packages "$PM" git
  else
    success "Git already installed"
  fi

  # Step 2: Install Docker
  step "Setting up Docker"

  if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker..."
    if curl -fsSL https://get.docker.com 2>>"$LOG_FILE" | $SUDO sh >>"$LOG_FILE" 2>&1; then
      success "Docker installed"
    else
      error "Failed to install Docker"
      exit 1
    fi
  else
    success "Docker already installed"
  fi

  # Start Docker
  if ! docker info >/dev/null 2>&1; then
    run_cmd "Starting Docker daemon" $SUDO systemctl enable --now docker 2>/dev/null || $SUDO service docker start 2>/dev/null || true
    sleep 2
  fi

  # Wait for Docker
  log "Waiting for Docker to be ready..."
  for i in {1..30}; do
    if docker info >/dev/null 2>&1; then
      success "Docker is ready"
      break
    fi
    sleep 1
  done

  if ! docker info >/dev/null 2>&1; then
    error "Docker daemon is not running"
    exit 1
  fi

  # Step 3: Install Docker Compose
  step "Setting up Docker Compose"

  if docker compose version >/dev/null 2>&1; then
    success "Docker Compose already installed"
  elif command -v docker-compose >/dev/null 2>&1; then
    success "Docker Compose (standalone) already installed"
  else
    log "Installing Docker Compose plugin..."
    COMPOSE_VERSION=$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest 2>>"$LOG_FILE" | grep -Po '"tag_name": "\K[^"]*' || echo "v2.24.0")
    ARCH=$(uname -m)
    case "$ARCH" in
      x86_64) ARCH="x86_64" ;;
      aarch64|arm64) ARCH="aarch64" ;;
      armv7l) ARCH="armv7" ;;
    esac

    COMPOSE_URL="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-${ARCH}"
    $SUDO mkdir -p /usr/local/lib/docker/cli-plugins

    if $SUDO curl -fsSL -o /usr/local/lib/docker/cli-plugins/docker-compose "$COMPOSE_URL" >>"$LOG_FILE" 2>&1; then
      $SUDO chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
      success "Docker Compose installed"
    else
      error "Failed to install Docker Compose"
      exit 1
    fi
  fi

  # Step 4: Clone repository
  step "Downloading IoT2MQTT"

  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating existing installation..."

    # Backup user data before update
    BACKUP_DIR="/tmp/iot2mqtt-backup-$$"
    mkdir -p "$BACKUP_DIR"

    log "Backing up user data..."
    [ -f "$INSTALL_DIR/.env" ] && cp "$INSTALL_DIR/.env" "$BACKUP_DIR/" 2>/dev/null || true
    [ -f "$INSTALL_DIR/discovered_devices.json" ] && cp "$INSTALL_DIR/discovered_devices.json" "$BACKUP_DIR/" 2>/dev/null || true
    [ -f "$INSTALL_DIR/discovery_config.json" ] && cp "$INSTALL_DIR/discovery_config.json" "$BACKUP_DIR/" 2>/dev/null || true
    [ -d "$INSTALL_DIR/instances" ] && cp -r "$INSTALL_DIR/instances" "$BACKUP_DIR/" 2>/dev/null || true
    [ -d "$INSTALL_DIR/secrets" ] && cp -r "$INSTALL_DIR/secrets" "$BACKUP_DIR/" 2>/dev/null || true

    # Safe update: pull latest code
    (cd "$INSTALL_DIR" && git fetch origin "$BRANCH" && git reset --hard "origin/$BRANCH") >>"$LOG_FILE" 2>&1 || true

    # Restore user data
    log "Restoring user data..."
    [ -f "$BACKUP_DIR/.env" ] && cp "$BACKUP_DIR/.env" "$INSTALL_DIR/" 2>/dev/null || true
    [ -f "$BACKUP_DIR/discovered_devices.json" ] && cp "$BACKUP_DIR/discovered_devices.json" "$INSTALL_DIR/" 2>/dev/null || true
    [ -f "$BACKUP_DIR/discovery_config.json" ] && cp "$BACKUP_DIR/discovery_config.json" "$INSTALL_DIR/" 2>/dev/null || true
    [ -d "$BACKUP_DIR/instances" ] && cp -r "$BACKUP_DIR/instances" "$INSTALL_DIR/" 2>/dev/null || true
    [ -d "$BACKUP_DIR/secrets" ] && cp -r "$BACKUP_DIR/secrets" "$INSTALL_DIR/" 2>/dev/null || true

    # Cleanup backup
    rm -rf "$BACKUP_DIR"

    success "Repository updated (user data preserved)"
  else
    run_cmd "Cloning repository" $SUDO git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    $SUDO chown -R "$(id -u):$(id -g)" "$INSTALL_DIR" 2>/dev/null || true
  fi

  # Step 5: Configure
  step "Configuring"

  mkdir -p "$INSTALL_DIR/secrets" "$INSTALL_DIR/connectors" "$INSTALL_DIR/shared" 2>/dev/null || true

  if [ ! -f "$INSTALL_DIR/.env" ]; then
    WEB_PORT=${WEB_PORT:-$WEB_PORT_DEFAULT}
    TZ_VAL=$(cat /etc/timezone 2>/dev/null || echo "UTC")

    cat > "$INSTALL_DIR/.env" <<EOF
# IoT2MQTT Configuration
WEB_PORT=${WEB_PORT}
MQTT_HOST=
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_BASE_TOPIC=IoT2mqtt
LOG_LEVEL=INFO
TZ=${TZ_VAL}
EOF
    success "Configuration created"
  else
    success "Using existing configuration"
  fi

  # Step 6: Build & Start
  step "Building & Starting Services"

  log "This may take 1-2 minutes..."
  echo ""

  cd "$INSTALL_DIR"

  # Detect Docker socket
  if [ -n "${DOCKER_HOST:-}" ] && echo "$DOCKER_HOST" | grep -q '^unix://'; then
    export DOCKER_SOCK_PATH="${DOCKER_HOST#unix://}"
  elif [ -S "/var/run/docker.sock" ]; then
    export DOCKER_SOCK_PATH="/var/run/docker.sock"
  elif [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -S "${XDG_RUNTIME_DIR}/docker.sock" ]; then
    export DOCKER_SOCK_PATH="${XDG_RUNTIME_DIR}/docker.sock"
  fi

  # Find compose file
  COMPOSE_FILE=""
  for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
    if [ -f "$f" ]; then
      COMPOSE_FILE="$f"
      break
    fi
  done

  if [ -z "$COMPOSE_FILE" ]; then
    error "No docker-compose file found"
    exit 1
  fi

  # Determine compose command
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
  else
    COMPOSE_CMD="docker-compose"
  fi

  # Build with live output
  log "Building containers..."
  echo ""
  if $COMPOSE_CMD -f "$COMPOSE_FILE" build 2>&1 | tee -a "$LOG_FILE"; then
    echo ""
    success "Build complete"
  else
    error "Build failed"
    exit 1
  fi

  echo ""
  log "Starting containers..."
  echo ""
  if $COMPOSE_CMD -f "$COMPOSE_FILE" up -d 2>&1 | tee -a "$LOG_FILE"; then
    echo ""
    success "Services started"
  else
    error "Failed to start services"
    exit 1
  fi

  # Step 7: Health check
  step "Waiting for Services"

  WEB_PORT=$(grep -E '^WEB_PORT=' "$INSTALL_DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d ' \r' || echo "$WEB_PORT_DEFAULT")
  HEALTH_URL="http://127.0.0.1:${WEB_PORT}/api/health"

  log "Checking health endpoint..."
  for i in {1..60}; do
    if curl -fsSL "$HEALTH_URL" >/dev/null 2>&1; then
      success "Service is healthy"
      break
    fi
    sleep 1
    [ $i -eq 60 ] && error "Health check timeout"
  done

  # Step 8: Success!
  echo ""
  echo ""
  echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${GREEN}${BOLD}║                                                                ║${RESET}"
  echo -e "${GREEN}${BOLD}║            🎉  IoT2MQTT is ready!  🎉                          ║${RESET}"
  echo -e "${GREEN}${BOLD}║                                                                ║${RESET}"
  echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════════╝${RESET}"
  echo ""

  APP_IP=$(get_lan_ip)
  URL="http://${APP_IP}:${WEB_PORT}"

  echo -e "  ${BOLD}Web Interface:${RESET} \033]8;;${URL}\033\\${CYAN}${BOLD}${URL}${RESET}\033]8;;\033\\"
  echo ""
  echo -e "  ${DIM}• Containers restart automatically on boot${RESET}"
  echo -e "  ${DIM}• Logs: docker logs -f iot2mqtt_web${RESET}"
  echo -e "  ${DIM}• Config: ${INSTALL_DIR}/.env${RESET}"
  echo ""
  echo -e "${DIM}Installation log: ${LOG_FILE}${RESET}"
  echo ""

  # Completion marker for Proxmox installer
  echo "### IOT2MQTT_INSTALL_COMPLETE ###"
}

# ============================================================================
# Run
# ============================================================================

main "$@"
