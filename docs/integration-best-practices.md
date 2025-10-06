# Integration Best Practices

This guide covers recommended patterns for creating user-friendly integration setup flows.

## Form Field Organization

### Essential Fields First

Place only the **required** fields users must fill out in the main form view:

```json
{
  "fields": [
    {
      "type": "text",
      "name": "friendly_name",
      "label": "Friendly name",
      "required": true,
      "description": "A descriptive name for this device"
    },
    {
      "type": "text",
      "name": "ip",
      "label": "IP address",
      "required": true
    }
  ]
}
```

### Advanced Fields

Move optional configuration and fields with sensible defaults to the advanced section:

```json
{
  "fields": [
    {
      "type": "text",
      "name": "friendly_name",
      "label": "Friendly name",
      "required": true
    },
    {
      "type": "text",
      "name": "instance_id",
      "label": "Instance ID",
      "placeholder": "auto",
      "description": "Leave empty to auto-generate from friendly name",
      "advanced": true
    },
    {
      "type": "number",
      "name": "port",
      "label": "Port",
      "default": 55443,
      "advanced": true
    },
    {
      "type": "number",
      "name": "timeout",
      "label": "Connection timeout (seconds)",
      "default": 10,
      "min": 1,
      "max": 60,
      "advanced": true
    }
  ]
}
```

**What to mark as advanced:**
- Instance ID (when auto-generation is available)
- Network ports with defaults
- Timeouts and intervals
- Protocol-specific options (polling intervals, retry counts)
- Debug/logging settings
- Model identifiers that can be auto-detected

**What NOT to mark as advanced:**
- Credentials (username, password, API keys, tokens)
- Required connection information (IP, hostname)
- Friendly name
- Device-specific configuration that has no sensible default

## Instance ID Handling

The platform automatically generates instance IDs from friendly names when the field is empty or set to "auto".

### Recommended Pattern

```json
{
  "type": "text",
  "name": "instance_id",
  "label": "Instance ID",
  "placeholder": "auto",
  "description": "Leave empty to auto-generate from friendly name",
  "advanced": true
}
```

**Generation rules:**
- Input: `"Living Room Light"` → Output: `"living_room_light"`
- Input: `"My Device #1!"` → Output: `"my_device_1"`
- Lowercase, spaces to underscores, special chars removed
- Pattern enforced: `^[a-z0-9_-]+$`

### When to Pre-populate

In auto-discovery flows, pre-populate `instance_id` with device-specific identifiers:

```json
{
  "type": "text",
  "name": "instance_id",
  "label": "Instance ID",
  "default": "{{ selection.selected_device.device_id }}",
  "advanced": true
}
```

Users can still override this value if needed.

## Default Values

Always provide defaults for optional fields to minimize required user input:

```json
{
  "type": "select",
  "name": "transition",
  "label": "Transition effect",
  "default": "smooth",
  "advanced": true,
  "options": [
    { "value": "smooth", "label": "Smooth" },
    { "value": "sudden", "label": "Instant" }
  ]
}
```

## Field Descriptions

Use `description` to provide context for complex or ambiguous fields:

```json
{
  "type": "password",
  "name": "token",
  "label": "Device token",
  "required": true,
  "description": "32-character hex string from device settings"
}
```

For advanced fields, explain **why** someone might want to change the default:

```json
{
  "type": "number",
  "name": "poll_interval",
  "label": "Polling interval (seconds)",
  "default": 30,
  "description": "Lower values increase responsiveness but use more bandwidth",
  "advanced": true
}
```

## Flow Design

### Multiple Flows for Different Scenarios

Offer separate flows for different setup methods:

```json
{
  "flows": [
    {
      "id": "auto_discovery",
      "name": "Auto Discovery",
      "description": "Scan network and configure automatically",
      "default": true,
      "steps": [...]
    },
    {
      "id": "manual_entry",
      "name": "Manual",
      "description": "Enter device details manually",
      "steps": [...]
    },
    {
      "id": "cloud_import",
      "name": "Cloud",
      "description": "Import from manufacturer's cloud service",
      "steps": [...]
    }
  ]
}
```

### Flow Switching Actions

Allow users to switch between flows at appropriate decision points:

```json
{
  "id": "manual_form",
  "type": "form",
  "title": "Manual configuration",
  "schema": { "fields": [...] },
  "actions": [
    {
      "type": "goto_flow",
      "label": "Use auto-discovery instead",
      "flow": "auto_discovery"
    },
    {
      "type": "open_url",
      "label": "Need help finding device info?",
      "url": "https://docs.example.com/setup"
    }
  ]
}
```

## Validation

### Pattern Validation

Use `pattern` for format validation:

```json
{
  "type": "text",
  "name": "mac_address",
  "label": "MAC Address",
  "pattern": "^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$",
  "placeholder": "AA:BB:CC:DD:EE:FF",
  "description": "Device MAC address in standard format"
}
```

### Numeric Bounds

Set realistic min/max values:

```json
{
  "type": "number",
  "name": "brightness",
  "label": "Default brightness (%)",
  "default": 100,
  "min": 1,
  "max": 100,
  "step": 1
}
```

## Example: Well-Structured Form

```json
{
  "id": "device_setup",
  "type": "form",
  "title": "Device configuration",
  "description": "Enter your device details to get started",
  "schema": {
    "fields": [
      {
        "type": "text",
        "name": "friendly_name",
        "label": "Friendly name",
        "required": true,
        "placeholder": "Living Room Light",
        "description": "Choose a memorable name for this device"
      },
      {
        "type": "text",
        "name": "ip",
        "label": "IP address",
        "required": true,
        "pattern": "^((25[0-5]|(2[0-4]|1\\d|[1-9]|)\\d)\\.?\\b){4}$",
        "placeholder": "192.168.1.100"
      },
      {
        "type": "password",
        "name": "token",
        "label": "Device token",
        "required": true,
        "pattern": "^[0-9a-fA-F]{32}$",
        "description": "32-character hex token from device settings"
      },
      {
        "type": "text",
        "name": "instance_id",
        "label": "Instance ID",
        "placeholder": "auto",
        "description": "Leave empty to auto-generate from friendly name",
        "advanced": true
      },
      {
        "type": "number",
        "name": "port",
        "label": "Port",
        "default": 55443,
        "min": 1,
        "max": 65535,
        "advanced": true
      },
      {
        "type": "select",
        "name": "protocol_version",
        "label": "Protocol version",
        "default": "auto",
        "advanced": true,
        "options": [
          { "value": "auto", "label": "Auto-detect" },
          { "value": "v1", "label": "Version 1" },
          { "value": "v2", "label": "Version 2" }
        ]
      },
      {
        "type": "number",
        "name": "timeout",
        "label": "Connection timeout (seconds)",
        "default": 5,
        "min": 1,
        "max": 30,
        "description": "Increase if device is on a slow network",
        "advanced": true
      }
    ]
  },
  "actions": [
    {
      "type": "goto_flow",
      "label": "Use auto-discovery instead",
      "flow": "auto_discovery"
    },
    {
      "type": "open_url",
      "label": "How to find device token",
      "url": "https://docs.example.com/token"
    }
  ]
}
```

This form presents 3 essential fields immediately, with 4 advanced options hidden until requested.

## Testing Your Integration

### Test Both Flows

If offering auto-discovery and manual entry, test both paths:
- Auto-discovery with devices present
- Auto-discovery with no devices (should show helpful message)
- Manual entry with valid data
- Manual entry with invalid data (test validation)

### Test Edge Cases

- Very long friendly names (truncation in UI)
- Special characters in names
- Default values vs. user-provided values
- Switching between flows mid-setup
- Instance ID conflicts (duplicate detection)

### Verify Generated IDs

Test the auto-generation with various friendly name patterns:
- Single word: `"Bedroom"` → `"bedroom"`
- Multiple words: `"Living Room"` → `"living_room"`
- Special chars: `"Device #1!"` → `"device_1"`
- Unicode: `"Спальня"` → `""` (falls back to empty, needs friendly_name in ASCII)

Consider providing a default friendly name in your discovery results if auto-detection is available.

## Summary

✅ **DO:**
- Mark optional fields as advanced
- Provide sensible defaults
- Auto-generate instance_id from friendly_name
- Offer multiple flows for different use cases
- Include helpful descriptions
- Validate input with patterns and bounds

❌ **DON'T:**
- Hide required credentials in advanced section
- Leave fields without defaults in advanced section
- Force users to manually create instance IDs
- Create single-flow setups when multiple methods exist
- Skip validation (rely on backend errors)
