#!/usr/bin/env bash

# IoT2MQTT Proxmox LXC Installer
# Based on tteck's Proxmox scripts architecture
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/eduard256/IoT2mqtt/main/scripts/install_proxmox.sh)

# Source tteck's build functions
source <(curl -s https://raw.githubusercontent.com/tteck/Proxmox/main/misc/build.func)

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
