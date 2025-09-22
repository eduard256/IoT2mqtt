import json
from pathlib import Path

from models.schemas import FlowSetupSchema


def test_yeelight_schema_loads() -> None:
    schema_path = Path(__file__).resolve().parents[3] / 'connectors' / 'yeelight' / 'setup.json'
    if not schema_path.exists():
        pytest.skip(f"Schema file not found: {schema_path}")

    data = json.loads(schema_path.read_text())
    parsed = FlowSetupSchema(**data)
    assert parsed.display_name == 'Yeelight'
    assert parsed.flows, 'Expected at least one flow'
    assert parsed.flows[0].steps, 'Expected the first flow to include steps'


def test_xiaomi_schema_loads() -> None:
    schema_path = Path(__file__).resolve().parents[3] / 'connectors' / 'xiaomi_miio' / 'setup.json'
    if not schema_path.exists():
        pytest.skip(f"Schema file not found: {schema_path}")

    data = json.loads(schema_path.read_text())
    parsed = FlowSetupSchema(**data)
    assert any(flow.id == 'cloud_setup' for flow in parsed.flows)
