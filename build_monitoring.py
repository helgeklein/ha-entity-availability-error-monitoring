from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from string import Template

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard for target machines
    project_dir_name = Path(__file__).resolve().parent.name
    raise SystemExit(
        f"PyYAML is required. Install it with: pip install -r {project_dir_name}/requirements.txt"
    ) from exc


PROJECT_DIR = Path(__file__).resolve().parent
PROJECT_DIR_NAME = PROJECT_DIR.name
DEFAULT_PRIVATE_DIR = Path(PROJECT_DIR_NAME) / "private"


TRANSLATIONS = {
    "en": {
        "availability_title": "⚠️ Entity is offline",
        "error_detected_title": "⚠️ Error detected",
        "error_changed_title": "⚠️ Error changed",
        "availability_mobile_message": "The entity {trigger_name} is offline.\n{trigger_description}",
        "availability_message": (
            "The entity **{trigger_name}** is offline.\n\n"
            "Entity description: {trigger_description}\n\n"
            "Monitored entity: `{trigger_entity}`\n\n"
            "Created by automation: **{automation_name}** (`{automation_entity}`)"
        ),
        "error_detected_mobile_message": "Entity: {trigger_name}\nError code: {trigger_error_code}",
        "error_detected_message": (
            "The entity **{trigger_name}** reports an error.\n\n"
            "Error code: `{trigger_error_code}`\n\n"
            "Entity description: {trigger_description}\n\n"
            "Monitored entity: `{trigger_entity}`\n\n"
            "Created by automation: **{automation_name}** (`{automation_entity}`)"
        ),
        "error_changed_mobile_message": "Entity: {trigger_name}\nNew error code: {trigger_error_code}",
        "error_changed_message": (
            "The entity **{trigger_name}** reports a different error.\n\n"
            "New error code: `{trigger_error_code}`\n\n"
            "Entity description: {trigger_description}\n\n"
            "Monitored entity: `{trigger_entity}`\n\n"
            "Created by automation: **{automation_name}** (`{automation_entity}`)"
        ),
    },
    "de": {
        "availability_title": "⚠️ Entität ist offline",
        "error_detected_title": "⚠️ Fehler erkannt",
        "error_changed_title": "⚠️ Fehler geändert",
        "availability_mobile_message": "Die Entität {trigger_name} ist offline.\n{trigger_description}",
        "availability_message": (
            "Die Entität **{trigger_name}** ist offline.\n\n"
            "Beschreibung der Entität: {trigger_description}\n\n"
            "Überwachte Entität: `{trigger_entity}`\n\n"
            "Erstellt von Automatisierung: **{automation_name}** (`{automation_entity}`)"
        ),
        "error_detected_mobile_message": "Entität: {trigger_name}\nFehlercode: {trigger_error_code}",
        "error_detected_message": (
            "Die Entität **{trigger_name}** meldet einen Fehler.\n\n"
            "Fehlercode: `{trigger_error_code}`\n\n"
            "Beschreibung der Entität: {trigger_description}\n\n"
            "Überwachte Entität: `{trigger_entity}`\n\n"
            "Erstellt von Automatisierung: **{automation_name}** (`{automation_entity}`)"
        ),
        "error_changed_mobile_message": "Entität: {trigger_name}\nNeuer Fehlercode: {trigger_error_code}",
        "error_changed_message": (
            "Die Entität **{trigger_name}** meldet einen anderen Fehler.\n\n"
            "Neuer Fehlercode: `{trigger_error_code}`\n\n"
            "Beschreibung der Entität: {trigger_description}\n\n"
            "Überwachte Entität: `{trigger_entity}`\n\n"
            "Erstellt von Automatisierung: **{automation_name}** (`{automation_entity}`)"
        ),
    },
}

MONITORING_TEMPLATE = Template(
    """#
# Monitoring and notifications
#
# GENERATED FILE. DO NOT EDIT MANUALLY.
#
# Source inputs:
$source_inputs
#

######################################################################
#
# Monitoring automations
#
######################################################################

automation:
$availability_automation$error_automation
######################################################################
#
# Notification scripts
#
######################################################################

script:
  monitoring_notification_create:
    alias: "Monitoring: Create Notification"
    description: "Creates a persistent notification and forwards it to a mobile notify group."
    mode: queued
    fields:
      notification_id:
        description: "Unique notification ID used for both HA and mobile notifications."
      notify_group:
        description: "Notify group name."
      channel:
        description: "Optional mobile notification channel name for platforms that support it."
      title:
        description: "Notification title."
      mobile_message:
        description: "Short plain-text variant for mobile notifications."
      message:
        description: "Notification message."
    sequence:
      - service: persistent_notification.create
        data:
          notification_id: "{{ notification_id }}"
          title: "{{ title }}"
          message: "{{ message }}"
      - action: "notify.{{ notify_group }}"
        data:
          title: "{{ title }}"
          message: "{{ mobile_message }}"
          data:
            tag: "{{ notification_id }}"
            channel: "{{ channel }}"

  monitoring_notification_dismiss:
    alias: "Monitoring: Dismiss Notification"
    description: "Dismisses a persistent notification and clears the matching mobile notification."
    mode: queued
    fields:
      notification_id:
        description: "Notification ID to dismiss and clear."
      notify_group:
        description: "Notify group name."
    sequence:
      - service: persistent_notification.dismiss
        data:
          notification_id: "{{ notification_id }}"
      - action: "notify.{{ notify_group }}"
        data:
          message: "clear_notification"
          data:
            tag: "{{ notification_id }}"

input_text:
    monitoring_test_availability:
        name: "Monitoring: Test Availability Source"
        initial: "on"
        min: 0
        max: 100

    monitoring_test_error_code:
        name: "Monitoring: Test Error Code"
        initial: "0"
        min: 0
        max: 100

template:
    - binary_sensor: !include $availability_include
    - binary_sensor: !include $error_include
"""
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build packages/monitoring.yaml from monitoring/private inputs. "
            "This can run on any machine with SMB access to the Home Assistant config directory."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_DIR.parent,
        help="Path to the Home Assistant config root. UNC/SMB paths are supported.",
    )
    parser.add_argument(
        "--private-dir",
        type=Path,
        default=DEFAULT_PRIVATE_DIR,
        help="Private monitoring config directory, relative to --root unless absolute.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional explicit output path. Defaults to <root>/packages/monitoring.yaml.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with code 1 if the generated output differs from the current file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated package to stdout instead of writing it.",
    )
    return parser.parse_args()


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_text(template: str, **placeholders: str) -> str:
    return template.format_map(placeholders)


def indent_block(text: str, indent: int) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def resolve_under_root(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def relative_posix_path(path: Path, start: Path) -> str:
    try:
        return Path(os.path.relpath(path, start)).as_posix()
    except ValueError as exc:
        raise SystemExit(
            f"Cannot express path '{path}' relative to '{start}'. "
            "Ensure the generated package and private config are reachable from the same filesystem root."
        ) from exc


def comment_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_yaml_document(path: Path):
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Failed to read {path}: {exc}") from exc

    try:
        loaded = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise SystemExit(f"Failed to parse YAML in {path}: {exc}") from exc

    return loaded


def read_yaml(path: Path) -> dict:
    loaded = read_yaml_document(path)

    if not isinstance(loaded, dict):
        raise SystemExit(f"Expected a YAML mapping in {path}, got {type(loaded).__name__}")
    return loaded


def validate_template_binary_sensors(
    path: Path,
    *,
    required_attributes: tuple[str, ...],
) -> None:
    loaded = read_yaml_document(path)

    if not isinstance(loaded, list):
        raise SystemExit(f"Expected a YAML list in {path}, got {type(loaded).__name__}")

    for index, item in enumerate(loaded, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"Expected list item {index} in {path} to be a mapping")

        for key in ("name", "unique_id", "state", "attributes"):
            if key not in item:
                raise SystemExit(f"Expected key '{key}' in list item {index} of {path}")

        attributes = item["attributes"]
        if not isinstance(attributes, dict):
            raise SystemExit(f"Expected 'attributes' in list item {index} of {path} to be a mapping")

        for attribute_name in required_attributes:
            if attribute_name not in attributes:
                raise SystemExit(
                    f"Expected attribute '{attribute_name}' in list item {index} of {path}"
                )


def require_mapping(data: dict, key: str, path: Path) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        raise SystemExit(f"Expected mapping '{key}' in {path}")
    return value


def require_entity_list(groups: dict, key: str, path: Path) -> list[str]:
    group = require_mapping(groups, key, path)
    entities = group.get("entities")
    if entities is None:
        return []
    if not isinstance(entities, list) or not all(isinstance(item, str) for item in entities):
        raise SystemExit(f"Expected '{key}.entities' in {path} to be a list of strings")
    return entities


def resolve_notify_group(input_text_data: dict, path: Path) -> str:
    config = require_mapping(input_text_data, "monitoring_notify_group", path)
    notify_group = config.get("initial")
    if not isinstance(notify_group, str) or not notify_group:
        raise SystemExit(f"Expected 'monitoring_notify_group.initial' in {path} to be a non-empty string")
    if not re.fullmatch(r"[a-z0-9_]+", notify_group):
        raise SystemExit(
            f"Invalid notify group '{notify_group}' in {path}. Expected lower-case service suffix like 'alle_gerate'."
        )
    return notify_group


def resolve_language(input_select_data: dict, path: Path) -> str:
    config = require_mapping(input_select_data, "monitoring_language", path)
    options = config.get("options")
    if not isinstance(options, list) or not all(isinstance(item, str) for item in options):
        raise SystemExit(f"Expected 'monitoring_language.options' in {path} to be a list of strings")
    selected = config.get("initial") or (options[0] if options else None)
    if not isinstance(selected, str):
        raise SystemExit(f"Could not determine selected language from {path}")
    if selected not in TRANSLATIONS:
        return "en"
    return selected


def render_entity_list(entities: list[str], indent: int) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}- {entity}" for entity in entities)


def render_availability_automation(entities: list[str], notify_group: str, t: dict[str, str]) -> str:
    if not entities:
        return ""

    entity_lines = render_entity_list(entities, 10)
    availability_mobile_message = render_text(
        t["availability_mobile_message"],
        trigger_name="{{ trigger_name }}",
        trigger_description="{{ trigger_description }}",
    )
    availability_message = render_text(
        t["availability_message"],
        trigger_name="{{ trigger_name }}",
        trigger_description="{{ trigger_description }}",
        trigger_entity="{{ trigger_entity }}",
        automation_name="{{ this.attributes.friendly_name }}",
        automation_entity="{{ this.entity_id }}",
    )
    availability_mobile_message_block = indent_block(availability_mobile_message, 20)
    availability_message_block = indent_block(availability_message, 20)
    return f'''  #
  # Monitor entity availability (must be binary_sensor!)
  #
  - id: "monitoring_entity_availability"
    alias: "Monitoring: Entity availability"
    description: "Monitors configured availability entities and sends a notification if any of them become unavailable."
    mode: parallel
    max: 10

    trigger:
      - platform: state
        id: unavailable
        entity_id:
{entity_lines}
        to: "unavailable"
        for:
          minutes: 5

      - platform: state
        id: recovery
        entity_id:
{entity_lines}
        from: "unavailable"

    action:
      - variables:
          trigger_name: "{{{{ state_attr(trigger.entity_id, 'source_name') or trigger.to_state.name }}}}"
          trigger_description: "{{{{ state_attr(trigger.entity_id, 'source_description') or '' }}}}"
          trigger_entity: "{{{{ trigger.entity_id }}}}"
          notification_target: {yaml_string(notify_group)}
          notification_channel: "{{{{ this.attributes.friendly_name }}}}"
          notification_id: "mon_{{{{ trigger.entity_id.split('.')[-1] }}}}"

      - choose:
          - conditions:
              - condition: trigger
                id: unavailable
            sequence:
              - action: script.monitoring_notification_create
                data:
                  notification_id: "{{{{ notification_id }}}}"
                  notify_group: "{{{{ notification_target }}}}"
                  channel: "{{{{ notification_channel }}}}"
                  title: {yaml_string(t['availability_title'])}
                  mobile_message: |-
{availability_mobile_message_block}
                  message: |-
{availability_message_block}

          - conditions:
              - condition: trigger
                id: recovery
              - condition: template
                value_template: "{{{{ trigger.to_state is not none and trigger.to_state.state in ['on', 'off'] }}}}"
            sequence:
              - action: script.monitoring_notification_dismiss
                data:
                  notification_id: "{{{{ notification_id }}}}"
                  notify_group: "{{{{ notification_target }}}}"

'''


def render_error_automation(entities: list[str], notify_group: str, t: dict[str, str]) -> str:
    if not entities:
        return ""

    entity_lines = render_entity_list(entities, 10)
    error_detected_mobile_message = render_text(
        t["error_detected_mobile_message"],
        trigger_name="{{ trigger_name }}",
        trigger_error_code="{{ trigger_error_code }}",
    )
    error_detected_message = render_text(
        t["error_detected_message"],
        trigger_name="{{ trigger_name }}",
        trigger_error_code="{{ trigger_error_code }}",
        trigger_description="{{ trigger_description }}",
        trigger_entity="{{ trigger_entity }}",
        automation_name="{{ this.attributes.friendly_name }}",
        automation_entity="{{ this.entity_id }}",
    )
    error_changed_mobile_message = render_text(
        t["error_changed_mobile_message"],
        trigger_name="{{ trigger_name }}",
        trigger_error_code="{{ trigger_error_code }}",
    )
    error_changed_message = render_text(
        t["error_changed_message"],
        trigger_name="{{ trigger_name }}",
        trigger_error_code="{{ trigger_error_code }}",
        trigger_description="{{ trigger_description }}",
        trigger_entity="{{ trigger_entity }}",
        automation_name="{{ this.attributes.friendly_name }}",
        automation_entity="{{ this.entity_id }}",
    )
    error_detected_mobile_message_block = indent_block(error_detected_mobile_message, 20)
    error_detected_message_block = indent_block(error_detected_message, 20)
    error_changed_mobile_message_block = indent_block(error_changed_mobile_message, 20)
    error_changed_message_block = indent_block(error_changed_message, 20)
    return f'''  #
  # Monitor entity error codes (must be binary_sensor!)
  #
  - id: "monitoring_entity_errors"
    alias: "Monitoring: Entity error codes"
    description: "Monitors configured error wrapper entities and sends a notification if any of them report a problem."
    mode: parallel
    max: 10

    trigger:
      - platform: state
        id: problem
        entity_id:
{entity_lines}
        to: "on"

      - platform: state
        id: problem_changed
        entity_id:
{entity_lines}
        attribute: source_error_code

      - platform: state
        id: recovery
        entity_id:
{entity_lines}
        from: "on"
        to: "off"

    action:
      - variables:
          trigger_name: "{{{{ state_attr(trigger.entity_id, 'source_name') or trigger.to_state.name or trigger.from_state.name }}}}"
          trigger_description: "{{{{ state_attr(trigger.entity_id, 'source_description') or '' }}}}"
          trigger_entity: "{{{{ trigger.entity_id }}}}"
          trigger_error_code: "{{{{ state_attr(trigger.entity_id, 'source_error_code') or '' }}}}"
          notification_target: {yaml_string(notify_group)}
          notification_channel: "{{{{ this.attributes.friendly_name }}}}"
          notification_id: "mon_{{{{ trigger.entity_id.split('.')[-1] }}}}"

      - choose:
          - conditions:
              - condition: trigger
                id: problem
            sequence:
              - action: script.monitoring_notification_create
                data:
                  notification_id: "{{{{ notification_id }}}}"
                  notify_group: "{{{{ notification_target }}}}"
                  channel: "{{{{ notification_channel }}}}"
                  title: {yaml_string(t['error_detected_title'])}
                  mobile_message: |-
{error_detected_mobile_message_block}
                  message: |-
{error_detected_message_block}

          - conditions:
              - condition: trigger
                id: problem_changed
              - condition: template
                value_template: >-
                  {{{{ trigger.from_state is not none
                     and trigger.to_state is not none
                     and trigger.from_state.state == 'on'
                     and trigger.to_state.state == 'on'
                     and trigger.from_state.attributes.get('source_error_code') != trigger.to_state.attributes.get('source_error_code') }}}}
            sequence:
              - action: script.monitoring_notification_create
                data:
                  notification_id: "{{{{ notification_id }}}}"
                  notify_group: "{{{{ notification_target }}}}"
                  channel: "{{{{ notification_channel }}}}"
                  title: {yaml_string(t['error_changed_title'])}
                  mobile_message: |-
{error_changed_mobile_message_block}
                  message: |-
{error_changed_message_block}

          - conditions:
              - condition: trigger
                id: recovery
            sequence:
              - action: script.monitoring_notification_dismiss
                data:
                  notification_id: "{{{{ notification_id }}}}"
                  notify_group: "{{{{ notification_target }}}}"

'''


def build_package(root: Path, private_dir: Path, output_path: Path) -> str:
    groups_path = private_dir / "groups.yaml"
    input_text_path = private_dir / "input_text.yaml"
    input_select_path = private_dir / "input_select.yaml"
    availability_entities_path = private_dir / "entities_availability.yaml"
    error_entities_path = private_dir / "entities_errors.yaml"

    groups_data = read_yaml(groups_path)
    input_text_data = read_yaml(input_text_path)
    input_select_data = read_yaml(input_select_path)
    validate_template_binary_sensors(
        availability_entities_path,
        required_attributes=("source_name", "source_description"),
    )
    validate_template_binary_sensors(
        error_entities_path,
        required_attributes=("source_name", "source_description", "source_error_code"),
    )

    availability_entities = require_entity_list(groups_data, "monitoring_entity_availability", groups_path)
    error_entities = require_entity_list(groups_data, "monitoring_entity_errors", groups_path)
    notify_group = resolve_notify_group(input_text_data, input_text_path)
    language = resolve_language(input_select_data, input_select_path)
    translations = TRANSLATIONS[language]

    availability_automation = render_availability_automation(availability_entities, notify_group, translations)
    error_automation = render_error_automation(error_entities, notify_group, translations)

    if not availability_automation and not error_automation:
        raise SystemExit("No monitoring automations were generated. At least one monitored entity group must contain entities.")

    source_inputs = "\n".join(
        [
            f"# - {comment_path(groups_path, root)}",
            f"# - {comment_path(input_text_path, root)}",
            f"# - {comment_path(input_select_path, root)}",
            f"# - {comment_path(availability_entities_path, root)}",
            f"# - {comment_path(error_entities_path, root)}",
            f"# - {comment_path(PROJECT_DIR / 'build_monitoring.py', root)}",
        ]
    )
    output_dir = output_path.parent
    availability_include = relative_posix_path(availability_entities_path, output_dir)
    error_include = relative_posix_path(error_entities_path, output_dir)

    return MONITORING_TEMPLATE.substitute(
        availability_automation=availability_automation,
        error_automation=error_automation,
        source_inputs=source_inputs,
        availability_include=availability_include,
        error_include=error_include,
    )


def write_if_changed(output_path: Path, content: str, check_only: bool) -> int:
    existing = None
    if output_path.exists():
        try:
            existing = output_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Failed to read existing output {output_path}: {exc}") from exc

    if existing == content:
        print(f"Up to date: {output_path}")
        return 0

    if check_only:
        print(f"Out of date: {output_path}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False, newline="\n") as temp_file:
        temp_file.write(content)
        temp_name = temp_file.name

    Path(temp_name).replace(output_path)
    print(f"Wrote: {output_path}")
    return 0


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    private_dir = resolve_under_root(root, args.private_dir).resolve()
    output_path = args.output.resolve() if args.output else root / "packages" / "monitoring.yaml"

    if not root.exists():
        raise SystemExit(f"Config root does not exist: {root}")
    if not private_dir.exists():
        raise SystemExit(f"Private monitoring config directory does not exist: {private_dir}")

    content = build_package(root, private_dir, output_path)

    if args.dry_run:
        sys.stdout.write(content)
        return 0

    return write_if_changed(output_path, content, args.check)


if __name__ == "__main__":
    sys.exit(main())