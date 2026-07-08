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

See [this blog post](https://helgeklein.com/blog/home-assistant-entity-availability-and-error-monitoring/) for a high-level architecture overview and for some things I learned while implementing this solution.

## Installation

### 1. Put the project into your Home Assistant config folder

Clone the repository into a subdirectory of your Home Assistant configuration directory (e.g., `config/monitoring`). Example:

```text
<your-ha-config>/monitoring/
```

The build script (see below) reads its source files from there and writes the finished package to:

```text
<your-ha-config>/packages/monitoring.yaml
```

### 2. Make sure Home Assistant packages are enabled

In your `configuration.yaml`, you need a packages section like this:

```yaml
homeassistant:
   packages: !include_dir_named packages
```

### 3. Install Python and the required Python package

On your PC, install Python 3. Then install the required Python packages by running:

```text
py -3 -m pip install -r "\\HA-MACHINE\config\monitoring\requirements.txt"
```

Note: I recommend the [Samba Share app](https://github.com/home-assistant/addons/blob/master/samba/DOCS.md) for easy access to your HA file system.

### 4. Create your local config files

Copy the sample files from `monitoring/example/` to `monitoring/private/`.

After that, `monitoring/private/` should contain these files:

- `entities_availability.yaml`
- `entities_errors.yaml`
- `groups.yaml`
- `input_text.yaml`
- `input_select.yaml`

This is where you configure what to monitor and where notifications should be sent to.

### 5. Define the sensors that should be monitored

Open these two files:

- `entities_availability.yaml`
- `entities_errors.yaml`

Replace the example entries with your own template binary sensors.

The idea is simple:

- Availability sensors answer: is this device or entity offline?
- Error sensors answer: is this device currently reporting a problem?

### 6. Choose which of those sensors should trigger notifications

Open `groups.yaml` and add the wrapper sensors from the previous step to the right groups:

- `monitoring_entity_availability` for availability monitoring
- `monitoring_entity_errors` for error-state monitoring

Only sensors listed in these groups will be monitored.

### 7. Create a Home Assistant notification group

Create a [notify group](https://www.home-assistant.io/integrations/group#notify-groups) in `configuration.yaml`. Example:

```yaml
notify:
  # This creates the notify group: notify.all_devices
  - name: "All Devices"
    platform: group
    services:
      - action: mobile_app_phone_1
      - action: mobile_app_phone_2
```

To find the correct mobile phone IDs, open Home Assistant and go to **Developer Tools** > **Actions**. Search for `mobile_app_` and look for services such as `notify.mobile_app_phone_name`. Use the service suffix shown there in the group definition (e.g., `phone_name`).

### 8. Choose notification target and language

Open these two files:

- `input_text.yaml`
- `input_select.yaml`

Set:

- the Home Assistant notify target or notify group that should receive alerts (use the suffix only: `all_devices` in the example above) 
- the language for user-facing messages (`en` or `de`)

### 9. Build the Home Assistant package

Run the following command to build the monitoring package with all definitions for Home Assistant:

```text
py -3 "\\HA-MACHINE\config\monitoring\build_monitoring.py" --root .
```

This creates or updates:

```text
packages/monitoring.yaml
```

### 10. Reload or restart Home Assistant

After the package has been generated, reload your YAML configuration or restart Home Assistant.

If everything is set up correctly, Home Assistant will start monitoring the sensors you added to the two monitoring groups.

## Test

The example configuration includes two built-in test entities:

- `binary_sensor.test_entity_availability`
- `binary_sensor.test_entity_error`

These test entities use two helper inputs that are created by the generated package:

- `input_text.monitoring_test_availability`
- `input_text.monitoring_test_error_code`

You can change those helper values in Home Assistant Developer Tools to check whether notifications are working.

### Test availability monitoring

1. Open Home Assistant.
2. Go to **Developer Tools** > **States**.
3. Find `input_text.monitoring_test_availability`.
4. Set its state to `unavailable` or `unknown`.
5. Wait 5 minutes.

Expected result:

- `binary_sensor.test_entity_availability` becomes unavailable.
- A persistent notification is created in Home Assistant.
- A notify-based alert is sent to your configured notification target.

To test recovery:

1. Set `input_text.monitoring_test_availability` to `on` or `off`.
2. Wait a moment for Home Assistant to update the template entity.

Expected result:

- the availability notification is dismissed
- the matching mobile notification is cleared

### Test error monitoring

1. Open Home Assistant.
2. Go to **Developer Tools** > **States**.
3. Find `input_text.monitoring_test_error_code`.
4. Set its state to a non-zero value such as `E1`.

Expected result:

- `binary_sensor.test_entity_error` turns on
- a persistent notification is created in Home Assistant
- a notify-based alert is sent to your configured notification target

To test recovery:

1. Set `input_text.monitoring_test_error_code` to `0` or an empty value.
2. Wait a moment for Home Assistant to update the template entity.

Expected result:

- `binary_sensor.test_entity_error` turns off
- the error notification is dismissed
- the matching mobile notification is cleared

If these tests do not trigger anything, check that the two test entities are listed in `groups.yaml`, then rebuild the package and reload or restart Home Assistant.

## Key Concepts

### Wrapper entities

You do not monitor raw entities directly. Instead, you create template binary sensors that define what counts as:

- unavailable
- unknown
- error
- recovered

These wrapper entities also provide user-facing metadata such as:

- `source_name`
- `source_description`
- `source_error_code` for error sensors

This adapter layer is what makes the solution flexible to use with different kinds of source entities.

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
- become `unavailable` when the monitored source is offline or unknown
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
