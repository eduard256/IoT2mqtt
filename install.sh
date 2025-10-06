#!/usr/bin/env bash

# IoT2MQTT universal installer
# Usage (recommended):
#   curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh | bash

set -Eeuo pipefail
set -o errtrace

# -------------- Styling --------------
ESC="\033"
RESET="${ESC}[0m"
BOLD="${ESC}[1m"
DIM="${ESC}[2m"
ITALIC="${ESC}[3m"
UNDERLINE="${ESC}[4m"

FG_BLACK="${ESC}[30m"; FG_RED="${ESC}[31m"; FG_GREEN="${ESC}[32m"; FG_YELLOW="${ESC}[33m"; FG_BLUE="${ESC}[34m"; FG_MAGENTA="${ESC}[35m"; FG_CYAN="${ESC}[36m"; FG_WHITE="${ESC}[37m"
FG_BR_CYAN="${ESC}[96m"; FG_BR_WHITE="${ESC}[97m"

# -------------- Globals --------------
TOTAL_STEPS=9
CURRENT_STEP=0
WEB_PORT_DEFAULT=8765
INSTALL_DIR="/opt/iot2mqtt"
REPO_URL="https://github.com/eduard256/IoT2mqtt.git"
BRANCH="main"
LOG_FILE="/var/log/iot2mqtt-install.log"
declare -a LOG_LINES

# Setup sudo if not root
SUDO=""
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    if sudo -n true 2>/dev/null; then
      SUDO="sudo -n"
    else
      # Will prompt if needed, but try to keep non-interactive
      SUDO="sudo"
    fi
  fi
fi

# Ensure log file directory exists as the VERY first side-effect
if [ -n "$SUDO" ]; then
  $SUDO mkdir -p "$(dirname "$LOG_FILE")" || true
  $SUDO touch "$LOG_FILE" || true
else
  mkdir -p "$(dirname "$LOG_FILE")" || true
  : > "$LOG_FILE" || true
fi

echo "[installer] starting at $(date -Is)" >>"$LOG_FILE" 2>&1 || true

# -------------- Error handling hooks --------------
cleanup() {
  [ ${CLEANED:-0} -eq 1 ] && return || true
  CLEANED=1
  stop_log_monitor || true
  show_cursor || true
  printf "\n\n%bInstallation log:%b %s\n" "$DIM" "$RESET" "$LOG_FILE"
}
trap cleanup EXIT

on_error() {
  local line=$1; local cmd=$2
  printf "\n%s\n" "ERROR: line ${line}: ${cmd}" >>"$LOG_FILE" 2>&1 || true
  printf "\nInstallation failed. See log: %s\n" "$LOG_FILE" 1>&2
}
trap 'on_error $LINENO "$BASH_COMMAND"' ERR

is_lxc_env() {
  if command -v systemd-detect-virt >/dev/null 2>&1; then
    systemd-detect-virt -c 2>/dev/null | grep -qi "lxc" && return 0
  fi
  grep -qa 'container=lxc' /proc/1/environ 2>/dev/null && return 0
  grep -qa '/lxc/' /proc/1/cgroup 2>/dev/null && return 0
  return 1
}

# Determine if stdout is a terminal to decide fancy UI
USE_TPUT=0
if command -v tput >/dev/null 2>&1 && [ -t 1 ]; then
  USE_TPUT=1
fi

# -------------- UI Helpers --------------
term_rows() { if [ "$USE_TPUT" -eq 1 ]; then tput lines; else echo 24; fi; }
term_cols() { if [ "$USE_TPUT" -eq 1 ]; then tput cols; else echo 80; fi; }

hide_cursor() { [ "$USE_TPUT" -eq 1 ] && tput civis 2>/dev/null || true; }
show_cursor() { [ "$USE_TPUT" -eq 1 ] && tput cnorm 2>/dev/null || true; }
move_to() { [ "$USE_TPUT" -eq 1 ] && tput cup "$1" "$2" 2>/dev/null || true; }
clear_screen() { [ "$USE_TPUT" -eq 1 ] && tput clear 2>/dev/null || printf "\n%.0s" {1..3}; }

draw_logo() {
  local cols=$(term_cols)
  local logo
  logo=$(cat <<'EOF'
 ######     ####     ######    ######   ##    ##    ####     ######    ######  
   ##      ##  ##      ##     ##   ##   ###  ###   ##  ##      ##        ##    
   ##      ##  ##      ##         ##    ########   ##  ##      ##        ##    
   ##      ##  ##      ##        ##     ## ## ##   ##  ##      ##        ##    
   ##      ##  ##      ##       ##      ##    ##   ## ##       ##        ##    
   ##      ##  ##      ##      ##       ##    ##    ####       ##        ##    
 ######     ####       ##     ######    ##    ##       ##      ##        ##    
EOF
)
  # Center the logo
  local line
  local row=1
  while IFS= read -r line; do
    local pad=$(( (cols - ${#line}) / 2 ));
    [ $pad -lt 0 ] && pad=0
    move_to "$row" "$pad"; printf "%b%s%b\n" "$FG_BR_CYAN$BOLD" "$line" "$RESET"
    row=$((row+1))
  done <<<"$logo"
  move_to $row 0
  printf "%b%s%b\n" "$FG_BR_WHITE$BOLD" "Direct IoT → MQTT • Zero Host Dependencies" "$RESET"
}

progress_row() {
  # Row just below the logo + 1
  echo 8
}

log_area_row() {
  # Start logs below progress bar + 2
  echo 11
}

log_area_height() {
  local rows=$(term_rows)
  # Reserve space: logo(8) + progress(3) + success message(7) = 18
  local available=$(( rows - 18 ))
  [ $available -lt 5 ] && available=5
  [ $available -gt 15 ] && available=15
  echo $available
}

draw_log_line() {
  if [ "$USE_TPUT" -ne 1 ]; then return; fi
  local line="$1"
  local row=$(log_area_row)
  local height=$(log_area_height)
  local cols=$(term_cols)

  # Shift existing lines up in memory
  for ((i=0; i<height-1; i++)); do
    LOG_LINES[$i]="${LOG_LINES[$i+1]:-}"
  done

  # Add new line at bottom
  LOG_LINES[$((height-1))]="$line"

  # Redraw all log lines
  for ((i=0; i<height; i++)); do
    move_to $((row + i)) 0
    # Clear line and print
    printf "%b%-${cols}s%b" "$DIM" "${LOG_LINES[$i]}" "$RESET"
  done
}

clear_log_area() {
  if [ "$USE_TPUT" -ne 1 ]; then return; fi
  local row=$(log_area_row)
  local height=$(log_area_height)
  local cols=$(term_cols)

  for ((i=0; i<height; i++)); do
    move_to $((row + i)) 0
    printf "%-${cols}s" " "
  done
}

draw_progress() {
  local step="$1"; shift || true
  local label="$1"; shift || true
  local cols=$(term_cols)
  local row=$(progress_row)
  local width=$(( cols - 12 ))
  [ $width -lt 20 ] && width=20

  local filled=$(( (step * width) / 100 ))
  local empty=$(( width - filled ))
  local bar
  bar="$(printf "%0.s█" $(seq 1 $filled))$(printf "%0.s░" $(seq 1 $empty))"

  local text=" ${step}%% ${label}"
  move_to "$row" 0; printf "%b" "$FG_WHITE$BOLD"
  printf " %-6s %s\r" "[${step}%]" "$label"
  move_to "$((row+1))" 0; printf "%b" "$FG_CYAN"
  printf " %s\n" "$bar"
  printf "%b" "$RESET"
}

increment_progress() {
  local inc=${1:-1}
  CURRENT_STEP=$(( CURRENT_STEP + inc ))
  local pct=$(( (CURRENT_STEP * 100) / TOTAL_STEPS ))
  [ $pct -gt 99 ] && pct=99
  draw_progress "$pct" "$2"
}

finalize_progress() {
  draw_progress 100 "Done"
}

# Background log monitor
start_log_monitor() {
  if [ "$USE_TPUT" -ne 1 ]; then return; fi
  (
    # Monitor log file and display new lines
    local last_line=0
    while kill -0 $$ 2>/dev/null; do
      if [ -f "$LOG_FILE" ]; then
        local total_lines=$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)
        if [ "$total_lines" -gt "$last_line" ]; then
          # Read new lines
          tail -n +$((last_line + 1)) "$LOG_FILE" 2>/dev/null | while IFS= read -r line; do
            # Truncate long lines
            local cols=$(term_cols)
            local max_len=$((cols - 4))
            if [ ${#line} -gt $max_len ]; then
              line="${line:0:$max_len}..."
            fi
            draw_log_line "$line"
          done
          last_line=$total_lines
        fi
      fi
      sleep 0.1
    done
  ) &
  LOG_MONITOR_PID=$!
}

stop_log_monitor() {
  if [ -n "${LOG_MONITOR_PID:-}" ] && kill -0 "$LOG_MONITOR_PID" 2>/dev/null; then
    kill "$LOG_MONITOR_PID" 2>/dev/null || true
    wait "$LOG_MONITOR_PID" 2>/dev/null || true
  fi
}

# -------------- System helpers --------------
detect_pkg_manager() {
  if command -v apt-get >/dev/null 2>&1; then echo apt; return; fi
  if command -v dnf >/dev/null 2>&1; then echo dnf; return; fi
  if command -v yum >/dev/null 2>&1; then echo yum; return; fi
  if command -v zypper >/dev/null 2>&1; then echo zypper; return; fi
  if command -v pacman >/dev/null 2>&1; then echo pacman; return; fi
  if command -v apk >/dev/null 2>&1; then echo apk; return; fi
  echo unknown
}

pkg_install() {
  local pm="$1"; shift
  local pkgs=("$@")
  case "$pm" in
    apt)
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update >>"$LOG_FILE" 2>&1 || true
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}" >>"$LOG_FILE" 2>&1
      ;;
    dnf)
      $SUDO dnf -y install "${pkgs[@]}" >>"$LOG_FILE" 2>&1
      ;;
    yum)
      $SUDO yum -y install "${pkgs[@]}" >>"$LOG_FILE" 2>&1
      ;;
    zypper)
      $SUDO zypper -n install "${pkgs[@]}" >>"$LOG_FILE" 2>&1
      ;;
    pacman)
      $SUDO pacman -Sy --noconfirm "${pkgs[@]}" >>"$LOG_FILE" 2>&1
      ;;
    apk)
      $SUDO apk add --no-cache "${pkgs[@]}" >>"$LOG_FILE" 2>&1
      ;;
    *) return 1;;
  esac
}

start_docker_service() {
  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable --now docker >>"$LOG_FILE" 2>&1 || true
  fi
  if command -v service >/dev/null 2>&1; then
    $SUDO service docker start >>"$LOG_FILE" 2>&1 || true
  fi
  if command -v rc-service >/dev/null 2>&1; then
    $SUDO rc-update add docker default >>"$LOG_FILE" 2>&1 || true
    $SUDO rc-service docker start >>"$LOG_FILE" 2>&1 || true
  fi
  # Fallback: spawn dockerd if nothing else worked
  if ! docker info >>"$LOG_FILE" 2>&1; then
    nohup $SUDO dockerd >>"$LOG_FILE" 2>&1 & disown || true
  fi
}

ensure_docker() {
  if command -v docker >/dev/null 2>&1; then return 0; fi
  local pm=$(detect_pkg_manager)
  case "$pm" in
    apt|dnf|yum)
      # Use Docker convenience script (handles repo setup + compose plugin)
      curl -fsSL https://get.docker.com | $SUDO sh >>"$LOG_FILE" 2>&1
      ;;
    zypper)
      pkg_install zypper docker docker-compose || true
      ;;
    pacman)
      pkg_install pacman docker docker-compose || true
      ;;
    apk)
      pkg_install apk docker docker-cli-compose || pkg_install apk docker docker-compose || true
      ;;
    *)
      # Try convenience script anyway
      curl -fsSL https://get.docker.com | $SUDO sh >>"$LOG_FILE" 2>&1 || return 1
      ;;
  esac
}

ensure_compose() {
  if docker compose version >/dev/null 2>&1; then return 0; fi
  if command -v docker-compose >/dev/null 2>&1; then return 0; fi
  # Install compose plugin (static binary)
  local uname_s=$(uname -s)
  local uname_m=$(uname -m)
  local dest_dir="/usr/local/lib/docker/cli-plugins"
  $SUDO mkdir -p "$dest_dir"
  $SUDO curl -fsSL -o "$dest_dir/docker-compose" "https://github.com/docker/compose/releases/latest/download/docker-compose-${uname_s}-${uname_m}" >>"$LOG_FILE" 2>&1
  $SUDO chmod +x "$dest_dir/docker-compose"
  # Also symlink classic binary for compatibility
  if ! command -v docker-compose >/dev/null 2>&1; then
    $SUDO ln -sf "$dest_dir/docker-compose" /usr/local/bin/docker-compose || true
  fi
}

lan_ip() {
  local ip
  # Try primary route
  if ip route get 1.1.1.1 >/dev/null 2>&1; then
    ip=$(ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}')
  fi
  # Fallback to hostname -I
  if [ -z "${ip:-}" ]; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
  # Choose private range if multiple
  if [ -n "$ip" ]; then
    echo "$ip"
    return
  fi
  echo "127.0.0.1"
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi
}

# -------------- Begin --------------
clear_screen || true
hide_cursor || true

if [ "$USE_TPUT" -eq 1 ]; then
  draw_logo || true
  draw_progress 1 "Starting installer" || true
  clear_log_area || true
  start_log_monitor || true
else
  printf "IoT2MQTT installer starting...\n" | tee -a "$LOG_FILE" >/dev/null 2>&1 || true
fi

# Step 1: Preflight
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Checking system"; fi

# Ensure curl exists (it does, because we used curl), git may be missing
PM=$(detect_pkg_manager)
if ! command -v git >/dev/null 2>&1; then
  if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Installing git"; fi
  pkg_install "$PM" git || true
fi

# Step 2: Install Docker
if ! command -v docker >/dev/null 2>&1; then
  if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Installing Docker"; fi
  ensure_docker || {
    move_to $(( $(progress_row)+3 )) 0
    printf "%bError:%b failed to install Docker. See %s\n" "$FG_RED$BOLD" "$RESET" "$LOG_FILE"
    exit 1
  }
else
  if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Docker found"; fi
fi

# Step 3: Start Docker
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Starting Docker"; fi
start_docker_service

# Wait for Docker up
i=0; until docker info >>"$LOG_FILE" 2>&1; do sleep 1; i=$((i+1)); [ $i -gt 60 ] && break; done
if ! docker info >>"$LOG_FILE" 2>&1; then
  move_to $(( $(progress_row)+3 )) 0
  printf "%bError:%b Docker daemon not running.\n" "$FG_RED$BOLD" "$RESET"
  exit 1
fi

# Step 4: Ensure Compose
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Installing Compose"; fi
ensure_compose || true

# Step 5: Clone/Update repo
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Preparing files"; fi
if [ -d "$INSTALL_DIR/.git" ]; then
  ( cd "$INSTALL_DIR" && git fetch --depth 1 origin "$BRANCH" >>"$LOG_FILE" 2>&1 && git reset --hard "origin/$BRANCH" >>"$LOG_FILE" 2>&1 ) || true
else
  $SUDO mkdir -p "$INSTALL_DIR"
  $SUDO chown "$(id -u)":"$(id -g)" "$INSTALL_DIR" 2>/dev/null || true
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" >>"$LOG_FILE" 2>&1
fi

# Log directory content for troubleshooting
{
  echo "[debug] INSTALL_DIR=$INSTALL_DIR"
  ls -la "$INSTALL_DIR"
} >>"$LOG_FILE" 2>&1 || true

# Step 6: .env and dirs
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Configuring"; fi
mkdir -p "$INSTALL_DIR/secrets" "$INSTALL_DIR/connectors" "$INSTALL_DIR/shared" || true
if [ ! -f "$INSTALL_DIR/.env" ]; then
  WEB_PORT=${WEB_PORT:-$WEB_PORT_DEFAULT}
  TZ_VAL="$(cat /etc/timezone 2>/dev/null || echo UTC)"
  cat > "$INSTALL_DIR/.env" <<EOF
# IoT2MQTT Configuration
# Generated on $(date -Is)

# Web Interface
WEB_PORT=${WEB_PORT}

# MQTT Settings (configure in Web UI)
MQTT_HOST=
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_BASE_TOPIC=IoT2mqtt

# System
LOG_LEVEL=INFO
TZ=${TZ_VAL}
EOF
fi

# Step 7: Build images
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Building containers"; fi
COMPOSE_CMD=$(compose_cmd)
# Detect rootless Docker socket path
if [ -n "${DOCKER_HOST:-}" ] && echo "$DOCKER_HOST" | grep -q '^unix://'; then
  export DOCKER_SOCK_PATH="${DOCKER_HOST#unix://}"
elif [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -S "${XDG_RUNTIME_DIR}/docker.sock" ]; then
  export DOCKER_SOCK_PATH="${XDG_RUNTIME_DIR}/docker.sock"
else
  export DOCKER_SOCK_PATH="/var/run/docker.sock"
fi
# Determine compose file explicitly
COMPOSE_FILE=""
for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
  if [ -f "$INSTALL_DIR/$f" ]; then COMPOSE_FILE="$f"; break; fi
done
if [ -z "$COMPOSE_FILE" ]; then
  echo "[error] no compose file found in $INSTALL_DIR" >>"$LOG_FILE"
  move_to $(( $(progress_row)+3 )) 0
  printf "%bError:%b compose file not found in %s\n" "$FG_RED$BOLD" "$RESET" "$INSTALL_DIR"
  exit 1
fi

if ! ( cd "$INSTALL_DIR" && env DOCKER_SOCK_PATH="$DOCKER_SOCK_PATH" $COMPOSE_CMD -f "$COMPOSE_FILE" build >>"$LOG_FILE" 2>&1 ); then
  move_to $(( $(progress_row)+3 )) 0
  printf "%bError:%b failed to build Docker images. See %s\n" "$FG_RED$BOLD" "$RESET" "$LOG_FILE"
  exit 1
fi

# Step 8: Up
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Starting services"; fi
( cd "$INSTALL_DIR" && env DOCKER_SOCK_PATH="$DOCKER_SOCK_PATH" $COMPOSE_CMD ${COMPOSE_FILE:+-f "$COMPOSE_FILE"} up -d >>"$LOG_FILE" 2>&1 ) || {
  move_to $(( $(progress_row)+3 )) 0
  printf "%bError:%b failed to start services. See %s\n" "$FG_RED$BOLD" "$RESET" "$LOG_FILE"
  exit 1
}

# Step 9: Healthcheck
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Warming up"; fi
WEB_PORT="$(grep -E '^WEB_PORT=' "$INSTALL_DIR/.env" | head -n1 | cut -d= -f2 | tr -d '\r' | tr -d ' ')"
[ -n "$WEB_PORT" ] || WEB_PORT=$WEB_PORT_DEFAULT
HEALTH_URL="http://127.0.0.1:${WEB_PORT}/api/health"
for i in $(seq 1 120); do
  if curl -fsS "$HEALTH_URL" >>"$LOG_FILE" 2>&1; then break; fi
  sleep 1
done

if [ "$USE_TPUT" -eq 1 ]; then finalize_progress; fi

# -------------- Success Output --------------
APP_IP=$(lan_ip)
URL="http://${APP_IP}:${WEB_PORT}"

if [ "$USE_TPUT" -eq 1 ]; then
  # Stop log monitor and clear log area
  stop_log_monitor || true
  sleep 0.2  # Allow final logs to be processed
  clear_log_area || true

  # Display success message
  move_to $(( $(progress_row) + 3 )) 0
  printf "\n%b══════════════════════════════════════════════════════════════%b\n" "$FG_GREEN$BOLD" "$RESET"
  printf "%b IoT2MQTT is up and running! %b\n" "$FG_GREEN$BOLD" "$RESET"
  printf "%b Web: %b\033]8;;%s\033\\%s\033]8;;\033\\%b\n" "$FG_BR_WHITE$BOLD" "$FG_BR_CYAN$UNDERLINE" "$URL" "$URL" "$RESET"
  printf "%b Containers restart automatically on boot. %b\n" "$FG_BR_WHITE$DIM" "$RESET"
  printf "%b══════════════════════════════════════════════════════════════%b\n" "$FG_GREEN$BOLD" "$RESET"
else
  printf "IoT2MQTT is up. Web: \033]8;;%s\033\\%s\033]8;;\033\\\n" "$URL" "$URL"
fi

exit 0
