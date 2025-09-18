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

can_use_game() {
  # Need a real TTY and working termios on /dev/tty
  if [ "$USE_TPUT" -ne 1 ]; then return 1; fi
  if ! tty -s 2>/dev/null; then return 1; fi
  if [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then return 1; fi
  if ! stty -F /dev/tty -g >/dev/null 2>&1; then return 1; fi
  return 0
}

draw_logo() {
  local cols=$(term_cols)
  local logo
  logo=$(cat <<'EOF'
██╗ ██████╗ ████████╗    ██████╗     ███╗   ███╗ ██████╗
██║██╔═══██╗╚══██╔══╝    ╚════██╗    ████╗ ████║██╔═══██╗
██║██║   ██║   ██║         █████╔╝    ██╔████╔██║██║   ██║
██║██║   ██║   ██║        ██╔═══╝     ██║╚██╔╝██║██║▄▄ ██║
██║╚██████╔╝   ██║        ███████╗    ██║ ╚═╝ ██║╚██████╔╝
╚═╝ ╚═════╝    ╚═╝        ╚══════╝    ╚═╝     ╚═╝ ╚══▀▀═╝
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

game_top_row() {
  # Leave space for logo and progress, then center game vertically
  local rows=$(term_rows)
  local game_rows=14
  local top=$(( ($(progress_row) + 3) + (rows - (progress_row + 3) - game_rows) / 2 ))
  [ $top -lt 10 ] && top=10
  echo $top
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

# -------------- Snake Game (centered) --------------
# Runs in a subshell to isolate traps and reads
start_snake_game() {
(
  set +Eeuo pipefail
  # visuals
  [ "$USE_TPUT" -eq 1 ] || exit 0

  trap 'tput cnorm 2>/dev/null; exit 0' EXIT
  trap 'tput cnorm 2>/dev/null; exit 0' INT

  local cols=28
  local rows=12
  local X_TIME=0.08
  local Y_TIME=0.12
  local REFRESH_TIME=$X_TIME
  declare -A screen
  declare -a snakebod_x
  declare -a snakebod_y
  local score=0
  local vel_x=1
  local vel_y=0
  local food_x
  local food_y
  local key=""
  local SNAKE_ICON="${FG_BR_WHITE}${BOLD}█${RESET}"
  local FOOD_ICON="${FG_YELLOW}${BOLD}●${RESET}"
  local EMPTY=" "
  local HORIZONTAL_BAR="${FG_BLUE}─${RESET}"
  local VERTICAL_BAR="${FG_BLUE}│${RESET}"
  local CORNER_ICON="${FG_BLUE}┼${RESET}"

  local top_off=$(game_top_row)
  local total_cols=$(term_cols)
  local left_off=$(( (total_cols - cols) / 2 ))
  [ $left_off -lt 0 ] && left_off=0

  set_pixel() { tput cup $((top_off + $1)) $((left_off + $2)); printf "%s" "$3"; }

  clear_game_area_screen() {
    # draw empty area and border
    for ((i=1;i<rows;i++)); do
      for ((j=1;j<cols;j++)); do
        screen[$i,$j]=$EMPTY
      done
    done
    draw_game_area_boundaries
  }

  draw_game_area_boundaries(){
    for i in 0 $rows; do
      for ((j=0;j<cols;j++)); do screen[$i,$j]=$HORIZONTAL_BAR; done
    done
    for j in 0 $cols; do
      for ((i=0;i<rows+1;i++)); do screen[$i,$j]=$VERTICAL_BAR; done
    done
    screen[0,0]=$CORNER_ICON
    screen[0,$cols]=$CORNER_ICON
    screen[$rows,$cols]=$CORNER_ICON
    screen[$rows,0]=$CORNER_ICON
  }

  print_screen(){
    for ((i=0;i<rows+1;i++)); do
      for ((j=0;j<cols+1;j++)); do printf "%s" "${screen[$i,$j]}"; done
      tput cup $((top_off + i)) $((left_off + cols + 1)); printf "\n"
    done
  }

  set_food(){
    while :; do
      food_x=$(( 1+$RANDOM%(cols-1) ))
      food_y=$(( 1+$RANDOM%(rows-1) ))
      local screen_val=${screen[$food_y,$food_x]}
      if [[ $screen_val == "$EMPTY" ]]; then
        screen[$food_y,$food_x]=$FOOD_ICON
        set_pixel "$food_y" "$food_x" "$FOOD_ICON"
        return
      fi
    done
  }

  calc_new_snake_head_x(){
    local cur_head_x=$1; local v_x=$2; new_head_x=$(( cur_head_x+v_x ))
    if (( new_head_x == 0 )); then new_head_x=$(( cols-1 ))
    elif (( new_head_x == cols )); then new_head_x=1; fi
  }
  calc_new_snake_head_y(){
    local cur_head_y=$1; local v_y=$2; new_head_y=$(( cur_head_y+v_y ))
    if (( new_head_y == 0 )); then new_head_y=$(( rows-1 ))
    elif (( new_head_y == rows )); then new_head_y=1; fi
  }

  handle_input(){
    case "$1" in
      A) (( vel_y != 1 ))  && { vel_x=0; vel_y=-1; REFRESH_TIME=$Y_TIME; };;
      B) (( vel_y != -1 )) && { vel_x=0; vel_y=1;  REFRESH_TIME=$Y_TIME; };;
      C) (( vel_x != -1 )) && { vel_x=1; vel_y=0;  REFRESH_TIME=$X_TIME; };;
      D) (( vel_x != 1 ))  && { vel_x=-1; vel_y=0; REFRESH_TIME=$X_TIME; };;
    esac
  }

  clear_snake(){
    local snake_length=${#snakebod_x[@]}
    for ((i=0;i<snake_length;i++)); do screen[${snakebod_y[i]},${snakebod_x[i]}]=$EMPTY; done
    set_pixel "${snakebod_y[snake_length-1]}" "${snakebod_x[snake_length-1]}" "$EMPTY"
  }

  draw_snake(){
    local snake_length=${#snakebod_x[@]}
    for ((i=0;i<snake_length;i++)); do screen[${snakebod_y[i]},${snakebod_x[i]}]="$SNAKE_ICON"; done
    set_pixel "${snakebod_y[0]}" "${snakebod_x[0]}" "$SNAKE_ICON"
  }

  game(){
    clear_snake
    local head_x=${snakebod_x[0]}
    local head_y=${snakebod_y[0]}
    local new_head_x; local new_head_y
    calc_new_snake_head_x $head_x $vel_x
    calc_new_snake_head_y $head_y $vel_y
    local snake_length=${#snakebod_x[@]}

    # self hit
    for ((i=0;i<snake_length-1;i++)); do
      if [[ ${snakebod_y[i]} -eq $new_head_y ]] && [[ ${snakebod_x[i]} -eq $new_head_x ]]; then
        return 1
      fi
    done

    if (( new_head_x == food_x )) && (( new_head_y == food_y )); then
      snakebod_x=($new_head_x ${snakebod_x[@]:0:${#snakebod_x[@]}})
      snakebod_y=($new_head_y ${snakebod_y[@]:0:${#snakebod_y[@]}})
      draw_snake; set_food; ((score++))
    else
      snakebod_x=($new_head_x ${snakebod_x[@]:0:${#snakebod_x[@]}-1})
      snakebod_y=($new_head_y ${snakebod_y[@]:0:${#snakebod_y[@]}-1})
      draw_snake
    fi
    return 0
  }

  while :; do
    # init new game
    score=0; vel_x=1; vel_y=0
    snakebod_x=( $((cols/2)) ); snakebod_y=( $((rows/2)) )
    clear_game_area_screen; print_screen; set_food
    # loop: step game + poll key
    while :; do
      # non-blocking key read from controlling tty
      if [ -r /dev/tty ]; then
        IFS= read -rsn1 -t 0.02 key </dev/tty || key=""
      else
        key=""
        sleep 0.02
      fi
      tput cup "$top_off" "$left_off"
      handle_input "$key"; game; rc=$?
      if [ "$rc" -ne 0 ]; then
        break
      fi
      sleep "$REFRESH_TIME"
    done
  done
)
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

# -------------- Cleanup traps --------------
CLEANED=0
finalize_cleanup() {
  # Final tidy and terminate snake if running
  if [ -n "${SNAKE_PID:-}" ] && kill -0 "$SNAKE_PID" >/dev/null 2>&1; then
    kill "$SNAKE_PID" >/dev/null 2>&1 || true
  fi
}

# -------------- Begin --------------
clear_screen || true
hide_cursor || true

if [ "$USE_TPUT" -eq 1 ]; then
  draw_logo || true
  draw_progress 1 "Starting installer" || true
else
  printf "IoT2MQTT installer starting...\n" | tee -a "$LOG_FILE" >/dev/null 2>&1 || true
fi

# Start snake game in background (non-blocking)
if [ "$USE_TPUT" -eq 1 ] && can_use_game; then
  start_snake_game &
  SNAKE_PID=$!
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
( cd "$INSTALL_DIR" && $COMPOSE_CMD build >>"$LOG_FILE" 2>&1 ) || true

# Step 8: Up
if [ "$USE_TPUT" -eq 1 ]; then increment_progress 1 "Starting services"; fi
( cd "$INSTALL_DIR" && $COMPOSE_CMD up -d >>"$LOG_FILE" 2>&1 ) || {
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
  move_to $(( $(game_top_row) - 2 )) 0
  printf "\n%b══════════════════════════════════════════════════════════════%b\n" "$FG_GREEN$BOLD" "$RESET"
  printf "%b IoT2MQTT is up and running! %b\n" "$FG_GREEN$BOLD" "$RESET"
  printf "%b Web: %b%s%b\n" "$FG_BR_WHITE$BOLD" "$FG_BR_CYAN$UNDERLINE" "$URL" "$RESET"
  printf "%b Containers restart automatically on boot. %b\n" "$FG_BR_WHITE$DIM" "$RESET"
  printf "%b══════════════════════════════════════════════════════════════%b\n" "$FG_GREEN$BOLD" "$RESET"
else
  printf "IoT2MQTT is up. Web: %s\n" "$URL"
fi

# Keep the snake running for a bit so user can play; then exit.
sleep 1
if [ -n "${SNAKE_PID:-}" ] && kill -0 "$SNAKE_PID" >/dev/null 2>&1; then
  sleep 5 || true
  kill "$SNAKE_PID" >/dev/null 2>&1 || true
fi

exit 0
