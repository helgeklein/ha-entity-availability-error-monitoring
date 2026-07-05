# Home Assistant Entity Availability and Error Monitoring

Home Assistant entity availability and error monitoring & alerting through native HA functionality only.

## Features

- Uses only native Home Assistant functionality plus a Python code generation script (required only when making changes)
- Clear separation of (private) configuration and (public) code
- Monitoring modes:
   - Entity availability
   - Entity error states
- Monitors almost any type of entity through user-created template sensors that define what counts as error or unavailable and specify user-friendly names for the UI
- Notification via:
   - Home Assistant persistent notifications that show up in the UI until dismissed
   - Mobile and 3rd-party notifications via HA notification groups
- Multi-language support for end-user facing messages

## Installation

### 1. Put the project into your Home Assistant config folder

This project must live inside your Home Assistant configuration directory.

Example:

```text
<your-ha-config>/monitoring/
```

The build script reads its source files from there and writes the finished package to:

```text
<your-ha-config>/packages/monitoring.yaml
```

### 2. Make sure Home Assistant packages are enabled

In your `configuration.yaml`, you need a packages section like this:

```yaml
homeassistant:
   packages: !include_dir_named packages
```

If you already use packages, you can skip this step.

### 3. Install the required Python package

The build script needs Python 3 and PyYAML.

Run this from your Home Assistant config folder:

```text
pip install -r monitoring/requirements.txt
```

### 4. Create your local config files

Copy the sample files from `monitoring/example/` to `monitoring/private/`.

After that, `monitoring/private/` should contain these files:

- `entities_availability.yaml`
- `entities_errors.yaml`
- `groups.yaml`
- `input_text.yaml`
- `input_select.yaml`

These are your own local files. This is where you tell the project what to monitor and where notifications should go.

### 5. Define the sensors that should be monitored

Open these two files:

- `entities_availability.yaml`
- `entities_errors.yaml`

Replace the example entries with your own template binary sensors.

The idea is simple:

- availability sensors answer: is this device or entity offline?
- error sensors answer: is this device currently reporting a problem?

Do not list random raw entities here. Create wrapper sensors that describe the situation clearly and provide readable metadata such as:

- `source_name`
- `source_description`
- `source_error_code` for error sensors

### 6. Choose which of those sensors should trigger notifications

Open `groups.yaml` and add your wrapper sensors to the right groups:

- `monitoring_entity_availability` for offline/unavailable monitoring
- `monitoring_entity_errors` for error-state monitoring

Only sensors listed in these groups will be monitored.

### 7. Choose notification target and language

Open these two files:

- `input_text.yaml`
- `input_select.yaml`

Set:

- the Home Assistant notify target or notify group that should receive alerts
- the language for user-facing messages (`en` or `de`)

### 8. Build the Home Assistant package

Run this command from your Home Assistant config folder:

```text
py -3 monitoring/build_monitoring.py --root .
```

This creates or updates:

```text
packages/monitoring.yaml
```

### 9. Reload or restart Home Assistant

After the package has been generated, reload your YAML configuration or restart Home Assistant.

If everything is set up correctly, Home Assistant will start monitoring the sensors you added to the two monitoring groups.

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
