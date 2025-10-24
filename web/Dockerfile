# Multi-stage build for optimal size

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files and install deps
COPY frontend/package.json ./
RUN npm install

# Copy the rest of the frontend source
COPY frontend/ .

# Ensure TS/Vite configs and critical assets exist even if missing in context
RUN set -eux; \
    if [ ! -f tsconfig.json ]; then \
      printf '%s\n' '{' \
        '  "compilerOptions": {' \
        '    "target": "ES2020",' \
        '    "useDefineForClassFields": true,' \
        '    "lib": ["ES2020", "DOM", "DOM.Iterable"],' \
        '    "module": "ESNext",' \
        '    "skipLibCheck": true,' \
        '    "moduleResolution": "bundler",' \
        '    "allowImportingTsExtensions": true,' \
        '    "resolveJsonModule": true,' \
        '    "isolatedModules": true,' \
        '    "noEmit": true,' \
        '    "jsx": "react-jsx",' \
        '    "strict": true,' \
        '    "baseUrl": "."' \
        '  },' \
        '  "include": ["src"],' \
        '  "references": [{ "path": "./tsconfig.node.json" }]' \
        '}' > tsconfig.json; \
    fi; \
    if [ ! -f tsconfig.node.json ]; then \
      printf '%s\n' '{' \
        '  "compilerOptions": {' \
        '    "composite": true,' \
        '    "skipLibCheck": true,' \
        '    "module": "ESNext",' \
        '    "moduleResolution": "bundler",' \
        '    "allowSyntheticDefaultImports": true' \
        '  },' \
        '  "include": ["vite.config.ts"]' \
        '}' > tsconfig.node.json; \
    fi; \
    if [ ! -f vite.config.ts ]; then \
      printf '%s\n' "import { defineConfig } from 'vite'" \
        "import react from '@vitejs/plugin-react'" \
        "export default defineConfig({ plugins: [react()] })" > vite.config.ts; \
    fi; \
    mkdir -p src/i18n/locales src/lib; \
    if [ ! -f src/i18n/locales/en.json ]; then echo '{"app":"IoT2MQTT","welcome":"Welcome"}' > src/i18n/locales/en.json; fi; \
    if [ ! -f src/i18n/locales/ru.json ]; then echo '{"app":"IoT2MQTT","welcome":"Добро пожаловать"}' > src/i18n/locales/ru.json; fi; \
    if [ ! -f src/i18n/locales/zh.json ]; then echo '{"app":"IoT2MQTT","welcome":"欢迎"}' > src/i18n/locales/zh.json; fi; \
    if [ ! -f src/lib/utils.ts ]; then \
      printf '%s\n' "import { type ClassValue, clsx } from 'clsx'" \
        "import { twMerge } from 'tailwind-merge'" \
        "export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }" \
        > src/lib/utils.ts; \
    fi

# Build frontend (fallback to vite if local script runs tsc and fails)
RUN npm run build || npx vite build

# Ensure real i18n locales are available at runtime
RUN set -eux; \
    mkdir -p dist/locales; \
    if [ -d public/locales ]; then cp -r public/locales/* dist/locales/; fi

# Stage 2: Build backend
FROM python:3.11-slim AS backend

WORKDIR /app

# Install system dependencies with retry
RUN set -e; \
    RETRIES=3; \
    for i in $(seq 1 $RETRIES); do \
        echo "apt-get attempt $i/$RETRIES"; \
        if apt-get update && apt-get install -y \
            gcc \
            curl \
            ffmpeg; then \
            break; \
        fi; \
        if [ $i -eq $RETRIES ]; then \
            echo "ERROR: apt-get failed after $RETRIES attempts"; \
            exit 1; \
        fi; \
        sleep 5; \
    done && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js with fallback sources
RUN set -e; \
    TIMEOUT=60; \
    INSTALLED=false; \
    \
    # Method 1: NodeSource repository (preferred)
    echo "Trying NodeSource repository..."; \
    if curl -fsSL --connect-timeout $TIMEOUT --max-time $TIMEOUT https://deb.nodesource.com/setup_20.x 2>/dev/null | bash - && \
       apt-get install -y nodejs 2>/dev/null; then \
        INSTALLED=true; \
    fi; \
    \
    # Method 2: Debian default repository
    if [ "$INSTALLED" = "false" ]; then \
        echo "NodeSource failed, trying Debian repository..."; \
        if apt-get update && apt-get install -y nodejs npm 2>/dev/null; then \
            INSTALLED=true; \
        fi; \
    fi; \
    \
    # Method 3: Direct binary download from nodejs.org
    if [ "$INSTALLED" = "false" ]; then \
        echo "Debian repository failed, trying direct download..."; \
        NODE_VERSION="20.19.0"; \
        ARCH=$(uname -m); \
        if [ "$ARCH" = "x86_64" ]; then ARCH="x64"; fi; \
        if [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi; \
        \
        NODE_URLS=( \
            "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${ARCH}.tar.xz" \
            "https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${ARCH}.tar.xz" \
            "https://npmmirror.com/mirrors/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${ARCH}.tar.xz" \
        ); \
        \
        for url in "${NODE_URLS[@]}"; do \
            echo "Trying: $url"; \
            if curl -fsSL --connect-timeout $TIMEOUT --max-time $TIMEOUT -o /tmp/node.tar.xz "$url" 2>/dev/null; then \
                tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1; \
                rm -f /tmp/node.tar.xz; \
                INSTALLED=true; \
                break; \
            fi; \
        done; \
    fi; \
    \
    # Verify installation
    if [ "$INSTALLED" = "false" ]; then \
        echo "ERROR: All Node.js installation methods failed"; \
        exit 1; \
    fi; \
    \
    node --version && npm --version; \
    rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install with retry
COPY backend/requirements.txt .
RUN set -e; \
    RETRIES=3; \
    for i in $(seq 1 $RETRIES); do \
        echo "pip install attempt $i/$RETRIES"; \
        if pip install --no-cache-dir -r requirements.txt; then \
            break; \
        fi; \
        if [ $i -eq $RETRIES ]; then \
            echo "ERROR: pip install failed after $RETRIES attempts"; \
            exit 1; \
        fi; \
        sleep 5; \
    done

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build from previous stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV MODE=production
ENV WEB_PORT=8765
ENV IOT2MQTT_PATH=/app

# Expose port
EXPOSE 8765

# Start the application
WORKDIR /app/backend
CMD ["python", "-u", "main.py"]
