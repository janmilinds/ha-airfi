"""Every state and form field a user can see is translated and explained, and no language file keeps a stale key."""

import ast
from collections.abc import Callable
from functools import reduce
import json
from pathlib import Path
from typing import Any

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi.config_flow_handler.schemas import (
    get_discovery_confirm_schema,
    get_discovery_select_schema,
    get_reconfigure_schema,
    get_user_schema,
)
from custom_components.airfi.const import DOMAIN
from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations, recursive_flatten

TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations"

# Attributes every entity can carry; the frontend names them itself.
GENERIC_ATTRIBUTES = frozenset(
    {
        ATTR_ASSUMED_STATE,
        ATTR_ATTRIBUTION,
        ATTR_DEVICE_CLASS,
        ATTR_ENTITY_PICTURE,
        ATTR_FRIENDLY_NAME,
        ATTR_ICON,
        ATTR_SUPPORTED_FEATURES,
        ATTR_UNIT_OF_MEASUREMENT,
    }
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _key_paths(path: Path) -> set[str]:
    return set(recursive_flatten("", _load(path)))


def _translation(entity_translations: dict[str, Any], entry: er.RegistryEntry) -> dict[str, Any]:
    """Return the en.json block of one entity: its name, states and state attributes."""
    return entity_translations.get(entry.domain, {}).get(entry.translation_key, {})


@pytest.fixture
async def entity_translations(hass: HomeAssistant) -> dict[str, Any]:
    """Return the `entity` section of en.json."""
    return (await hass.async_add_executor_job(_load, TRANSLATIONS / "en.json")).get("entity", {})


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_every_option_has_a_state_translation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    entity_translations: dict[str, Any],
) -> None:
    """Each option of an enum sensor or a select is translated, so no raw code reaches the UI."""
    missing = [
        f"entity.{entry.domain}.{entry.translation_key}.state.{option}"
        for entry in er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
        if (state := hass.states.get(entry.entity_id)) is not None
        for option in state.attributes.get("options") or []
        if option not in _translation(entity_translations, entry).get("state", {})
    ]

    assert not missing, f"missing in en.json: {missing}"


async def _platform_attributes(hass: HomeAssistant, domains: set[str]) -> set[tuple[str, str]]:
    """Return the (domain, attribute) pairs Home Assistant's entity platforms translate themselves."""
    keys = await async_get_translations(hass, "en", "entity_component", domains)
    return {
        (parts[1], parts[-2])
        for key in keys
        if ".state_attributes." in key and key.endswith(".name")
        for parts in [key.split(".")]
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_every_attribute_has_a_display_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    entity_translations: dict[str, Any],
) -> None:
    """Each attribute the integration adds has a translated display name, not the raw key."""
    entries = er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    platform_attributes = await _platform_attributes(hass, {entry.domain for entry in entries})

    missing = [
        f"entity.{entry.domain}.{entry.translation_key}.state_attributes.{attribute}.name"
        for entry in entries
        if (state := hass.states.get(entry.entity_id)) is not None
        for attribute in state.attributes
        if attribute not in GENERIC_ATTRIBUTES
        and (entry.domain, attribute) not in platform_attributes
        and "name" not in _translation(entity_translations, entry).get("state_attributes", {}).get(attribute, {})
    ]

    assert not missing, f"missing in en.json: {missing}"


def test_language_files_keep_no_stale_keys() -> None:
    """A language file has no key en.json lacks; a key it lacks falls back to English."""
    reference = _key_paths(TRANSLATIONS / "en.json")

    stale = {
        path.name: sorted(extra)
        for path in sorted(TRANSLATIONS.glob("*.json"))
        if (extra := _key_paths(path) - reference)
    }

    assert not stale, json.dumps(stale, indent=2)


INTEGRATION = TRANSLATIONS.parent

# Every form a flow shows, by flow class and step: its block in en.json, the factory the step passes as
# data_schema, and the arguments to build it with here.
FORMS: dict[tuple[str, str], tuple[str, Callable[..., probatio.Schema], tuple[Any, ...]]] = {
    ("AirfiConfigFlowHandler", "manual"): ("config.step.manual", get_user_schema, ()),
    ("AirfiConfigFlowHandler", "reconfigure"): ("config.step.reconfigure", get_reconfigure_schema, ("", None)),
    ("AirfiConfigFlowHandler", "discovery_select"): (
        "config.step.discovery_select",
        get_discovery_select_schema,
        ([],),
    ),
    ("AirfiConfigFlowHandler", "discovery_confirm"): (
        "config.step.discovery_confirm",
        get_discovery_confirm_schema,
        (AirfiDiscoveredDevice(host="192.0.2.1", serial=1, model_id=1),),
    ),
    ("DeviceUnreachableRepairFlow", "init"): (
        "issues.device_unreachable.fix_flow.step.init",
        get_reconfigure_schema,
        ("", None),
    ),
}


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _shown_forms() -> set[tuple[str, str, str]]:
    """Return the flow class, step ID and schema factory of every `async_show_form` call in the flows."""
    forms = set()
    for path in [*sorted((INTEGRATION / "config_flow_handler").rglob("*.py")), INTEGRATION / "repairs.py"]:
        flows = [node for node in ast.parse(path.read_text(encoding="utf-8")).body if isinstance(node, ast.ClassDef)]
        for flow in flows:
            for node in ast.walk(flow):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "async_show_form"
                ):
                    where = f"{path.name}:{node.lineno}"
                    step_id = _keyword(node, "step_id")
                    schema = _keyword(node, "data_schema")
                    assert isinstance(step_id, ast.Constant), f"{where} has no literal step_id"
                    assert isinstance(schema, ast.Call), f"{where} builds its data_schema in place"
                    assert isinstance(schema.func, ast.Name), f"{where} passes no schema factory by name"
                    forms.add((flow.name, step_id.value, schema.func.id))
    return forms


def test_every_shown_form_is_checked() -> None:
    """Each form a flow shows has a row in FORMS naming the schema it passes, so no step skips the field check."""
    assert _shown_forms() == {(flow, step, factory.__name__) for (flow, step), (_, factory, _) in FORMS.items()}


@pytest.mark.parametrize(
    ("path", "schema"),
    [pytest.param(path, factory(*args), id=path) for path, factory, args in FORMS.values()],
)
def test_every_form_field_has_a_label_and_a_description(path: str, schema: probatio.Schema) -> None:
    """Every field of a setup, reconfigure or repair form has a label and a help line, and en.json names no other."""
    step = reduce(lambda block, key: block.get(key, {}), path.split("."), _load(TRANSLATIONS / "en.json"))
    fields = {str(key) for key in schema.schema}

    missing = sorted(
        f"{path}.{section}.{field}"
        for section in ("data", "data_description")
        for field in fields - set(step.get(section, {}))
    )
    stale = sorted(
        f"{path}.{section}.{field}"
        for section in ("data", "data_description")
        for field in set(step.get(section, {})) - fields
    )

    assert not missing, f"missing in en.json: {missing}"
    assert not stale, f"not in the form: {stale}"
