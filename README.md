# Home Assistant Entity Availability and Error Monitoring

Monitor Home Assistant entities for outages and device-reported error states without creating a custom integration.

## Features

- Monitors:
   - Entity availability
   - Device or integration specific error states
- Sends notifications via:
   - Persistent Home Assistant notifications, and
   - Home Assistant notify groups (push to mobile or other 3rd-party systems)
- Supports multiple languages for user-facing messages
- Separates reusable logic from installation-specific entity definitions

## Installation

### 1. Place the project in your Home Assistant config directory

This repositories' files should sit inside your Home Assistant configuration root so the generator can read its source files and write the generated package to `packages/monitoring.yaml`.

### 2. Install the Python dependency

The build step requires Python 3 and PyYAML.

```
pip install -r monitoring/requirements.txt
```

### 3. Create your local monitoring configuration

Copy the sample files from `example/` into `monitoring/private/`.

Those files are the local, installation-specific part of the setup:

- `entities_availability.yaml`
- `entities_errors.yaml`
- `groups.yaml`
- `input_text.yaml`
- `input_select.yaml`

### 4. Define your wrapper entities

Edit the two entity files so they match your own devices and integrations.

You do not monitor raw entities directly. Instead, you define template binary sensors that answer questions like:

- Is this device offline?
- Is this integration unavailable?
- Does this device report an active error code?

Each wrapper entity should also provide user-facing metadata such as a display name and description.

### 5. Choose what gets monitored

Edit `groups.yaml` and list the wrapper entities that should be monitored for:

- availability
- error conditions

### 6. Set notification target and language

Edit:

- `input_text.yaml` to choose the Home Assistant notify target
- `input_select.yaml` to choose the language for generated user-facing messages

### 7. Generate the package

Run the build script from the Home Assistant config root:

```
py -3 monitoring/build_monitoring.py --root <path-to-home-assistant-config>
```

The generated output is written to:

```text
packages/monitoring.yaml
```

### 8. Reload or restart Home Assistant

After the package has been generated, reload the affected YAML configuration or restart Home Assistant.

## Quick Validation

To check whether the generated package is already up to date without rewriting it:

```
py -3 monitoring/build_monitoring.py --root <path-to-home-assistant-config> --check
```

Expected success output:

```text
Up to date: <path-to-home-assistant-config>/packages/monitoring.yaml
```

## Key Concepts

### Wrapper entities

You do not monitor raw entities directly. Instead, you create template binary sensors that define what counts as:

- unavailable
- error
- recovered

These wrapper entities also provide user-facing metadata such as:

- `source_name`
- `source_description`
- `source_error_code` for error sensors

This adapter layer is what makes the solution portable across very different devices and integrations.

### Entity groups

Two groups define what is monitored:

- availability monitoring group
- error monitoring group

The generator expands those group members into explicit automation triggers.

### Build step

Home Assistant state triggers require explicit entity IDs. The generator exists to compile your local monitoring definitions into explicit YAML before Home Assistant loads it.

## Configuration Contract

Your local configuration must provide the following inputs.

### Availability monitoring

Each monitored availability wrapper entity must:

- be a binary sensor
- become `unavailable` when the monitored source is offline
- return to a valid state when the source recovers
- expose `source_name`
- expose `source_description`

### Error monitoring

Each monitored error wrapper entity must:

- be a binary sensor
- be `on` while a problem is active
- be `off` when the problem is cleared
- expose `source_name`
- expose `source_description`
- expose `source_error_code`

### Notification target

The package expects a Home Assistant notify target that can forward push or external notifications.

### Language selection

User-facing text is selected by language code and falls back safely to English when needed.

## Notifications

The generated package creates synchronized notifications in two channels:

- Home Assistant persistent notifications
- notify-based messages for mobile apps or other notification backends

This gives you a durable in-UI alert and an immediate external notification at the same time.

## Updating

When you change reusable logic in this repository:

1. update the source files
2. run the build script again
3. reload or restart Home Assistant

When you change local monitoring behavior:

1. update your wrapper entities, groups, notify target, or language setting
2. run the build script again
3. reload or restart Home Assistant
