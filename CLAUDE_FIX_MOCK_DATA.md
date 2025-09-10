# Task: Remove All Mock Data and Connect Real APIs

## Role
You are a senior full-stack developer with 10+ years of experience in React, TypeScript, and FastAPI. You specialize in refactoring code to connect frontend interfaces with existing backend APIs.

## Context
This IoT2MQTT project has a fully functional backend API but the frontend is using mock data everywhere. The backend provides complete REST APIs for:
- MQTT broker management at `/api/mqtt/*`
- Docker container control at `/api/docker/*`
- Device management at `/api/devices/*`
- Connector/integration management at `/api/connectors/*` and `/api/instances/*`

## Critical Issue Already Fixed
We discovered and fixed a critical authentication bug where the auth token from localStorage wasn't initialized on page load. This caused all API requests to return 403 Forbidden. The fix is already implemented in `main.tsx` - the token is now initialized BEFORE React starts.

## Your Task
Remove ALL mock data and connect the existing frontend to the real backend APIs. The backend is FULLY FUNCTIONAL - you just need to replace mock data with actual API calls.

## Specific Implementation Steps

### 1. Devices Page (`/pages/Devices.tsx`)
- Remove the entire `mockDevices` array
- Replace with actual fetch to `/api/devices` endpoint
- Use the existing Device interface - it matches the API response
- Keep all UI components and state management
- The polling mechanism should stay, just fetch real data

### 2. Containers Page (`/pages/Containers.tsx`)
- Remove `mockContainers` array completely
- Fetch real containers from `/api/docker/containers`
- Container logs should use WebSocket connection for real-time streaming
- Keep the existing UI with stats, controls, and log viewer
- All container operations (start/stop/restart) should call corresponding APIs

### 3. MQTT Explorer (`/pages/MQTTExplorer.tsx`)
- Remove any hardcoded topic trees or mock MQTT data
- Fetch real topics from `/api/mqtt/topics`
- Subscribe/publish should use `/api/mqtt/subscribe` and `/api/mqtt/publish`
- Topic tree should update in real-time via WebSocket
- Keep the existing tree visualization and interaction components

### 4. Discovery Modal (`/components/integrations/DiscoveryModal.tsx`)
- Remove `mockDevices` array and fake discovery simulation
- Use real discovery endpoint: `/api/connectors/{name}/discover`
- Connect to WebSocket for real-time discovery updates
- Keep the progress indicator and device selection UI

### 5. Integration Components
- All integration operations must use real `/api/connectors` and `/api/instances` endpoints
- Configuration should be saved through proper API calls
- Docker container creation and management must be real

## Constraints
- DO NOT create new components or pages
- DO NOT change the existing UI design or layout
- DO NOT modify backend code - it's already complete
- DO NOT add new dependencies
- KEEP all existing UI components, just connect them to real data
- PRESERVE all error handling and loading states
- MAINTAIN the existing component structure and props

## Architecture Notes
- Backend uses FastAPI with full REST API implementation
- Authentication uses JWT tokens with Bearer scheme
- All endpoints require authentication (except `/api/health` and `/api/mqtt/test`)
- WebSocket is available for real-time updates
- Docker operations use docker.sock mounted in the container
- MQTT service is already connected and operational

Remember: The backend is COMPLETE and WORKING. You only need to remove mock data and connect to existing endpoints. Every API you need already exists and is tested.