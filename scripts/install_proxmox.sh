#!/usr/bin/env bash

# IoT2MQTT Proxmox LXC Installer
# Based on tteck's Proxmox scripts architecture
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/scripts/install_proxmox.sh)

# Disable version check and source tteck's build functions
YW=$(echo "\033[33m")
BL=$(echo "\033[36m")
RD=$(echo "\033[01;31m")
BGN=$(echo "\033[4;92m")
GN=$(echo "\033[1;92m")
DGN=$(echo "\033[32m")
CL=$(echo "\033[m")
RETRY_NUM=10
RETRY_EVERY=3
NUM=$RETRY_NUM
CM="${GN}✓${CL}"
CROSS="${RD}✗${CL}"
BFR="\\r\\033[K"
HOLD="-"
set -Eeuo pipefail
trap 'error_handler $LINENO "$BASH_COMMAND"' ERR
function error_handler() {
  local exit_code="$?"
  local line_number="$1"
  local command="$2"
  local error_message="${RD}[ERROR]${CL} in line ${RD}$line_number${CL}: exit code ${RD}$exit_code${CL}: while executing command ${YW}$command${CL}"
  echo -e "\n$error_message\n"
}

# Source tteck's build functions (skipping version check)
source <(curl -s https://raw.githubusercontent.com/tteck/Proxmox/main/misc/build.func 2>/dev/null | sed '/pve_check/d')

function header_info {
clear
cat <<"EOF"
   ██╗ ██████╗ ████████╗██████╗ ███╗   ███╗ ██████╗ ████████╗████████╗
   ██║██╔═══██╗╚══██╔══╝╚════██╗████╗ ████║██╔═══██╗╚══██╔══╝╚══██╔══╝
   ██║██║   ██║   ██║    █████╔╝██╔████╔██║██║   ██║   ██║      ██║
   ██║██║   ██║   ██║   ██╔═══╝ ██║╚██╔╝██║██║▄▄ ██║   ██║      ██║
   ██║╚██████╔╝   ██║   ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║      ██║
   ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚══▀▀═╝    ╚═╝      ╚═╝

                    Proxmox LXC Installer v3.0
EOF
}

header_info
echo -e "Loading..."

# Application settings
APP="IoT2MQTT"
var_disk="8"
var_cpu="2"
var_ram="2048"
var_os="ubuntu"
var_version="22.04"

# Load tteck's variables and functions
variables
color
catch_errors

function default_settings() {
  CT_TYPE="1"
  PW=""
  CT_ID=$NEXTID
  HN=$NSAPP
  DISK_SIZE="$var_disk"
  CORE_COUNT="$var_cpu"
  RAM_SIZE="$var_ram"
  BRG="vmbr0"
  NET="dhcp"
  GATE=""
  APT_CACHER=""
  APT_CACHER_IP=""
  DISABLEIP6="no"
  MTU=""
  SD=""
  NS=""
  MAC=""
  VLAN=""
  SSH="no"
  VERB="no"
  echo_default
}

function update_script() {
  header_info
  if [[ ! -d /opt/iot2mqtt ]]; then
    msg_error "No ${APP} Installation Found!"
    exit
  fi
  msg_info "Updating ${APP}"
  cd /opt/iot2mqtt
  git pull &>/dev/null
  msg_ok "Updated ${APP}"
  exit
}

# Post-installation: Install IoT2MQTT
function install_iot2mqtt() {
  msg_info "Installing IoT2MQTT application"

  # Install IoT2MQTT using the main install script
  $STD bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/install.sh)

  msg_ok "Installed IoT2MQTT"
}

# Build and configure container
start
build_container
description

# Install IoT2MQTT after container is created
install_iot2mqtt

msg_ok "Completed Successfully!\n"
echo -e "${APP} is running on: ${BL}http://${IP}:8765${CL}\n"
