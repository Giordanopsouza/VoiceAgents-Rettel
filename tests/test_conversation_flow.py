import json
from pathlib import Path

from app.settings import Settings

RETELL_DIR = Path(__file__).resolve().parent.parent / "retell"
FLOW_PATH = RETELL_DIR / "conversation-flow.json"
AVAILABILITY_SCHEMA_PATH = RETELL_DIR / "check_availability.json"
BOOKING_SCHEMA_PATH = RETELL_DIR / "book_appointment.json"
DIAGRAM_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "diagrams"
    / "02-retell-conversation-flow.mmd"
)
CHECKLIST_PATH = RETELL_DIR / "conversation-flow.md"

REQUIRED_NODE_IDS = {
    "greet",
    "collect",
    "check_availability",
    "offer_slots",
    "confirm",
    "book_appointment",
    "success",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _nodes_by_id(flow: dict) -> dict[str, dict]:
    return {node["id"]: node for node in flow["nodes"]}


def _incoming(flow: dict, node_id: str) -> list[dict]:
    return [edge for edge in flow["edges"] if edge["to"] == node_id]


def test_flow_covers_greeting_through_completion():
    flow = _load_json(FLOW_PATH)
    nodes = _nodes_by_id(flow)

    assert flow["start_node_id"] == "greet"
    assert flow["start_speaker"] == "agent"
    assert REQUIRED_NODE_IDS <= nodes.keys()
    assert nodes["greet"]["type"] == "conversation"
    assert nodes["collect"]["type"] == "conversation"
    assert nodes["check_availability"]["type"] == "function"
    assert nodes["offer_slots"]["type"] == "conversation"
    assert nodes["confirm"]["type"] == "conversation"
    assert nodes["book_appointment"]["type"] == "function"
    assert nodes["success"]["type"] == "conversation"
    assert {node["type"] for node in nodes.values() if node["id"].startswith("end_")} == {
        "end"
    }


def test_booking_node_is_unreachable_until_explicit_confirmation():
    flow = _load_json(FLOW_PATH)
    nodes = _nodes_by_id(flow)
    incoming = _incoming(flow, "book_appointment")

    assert nodes["book_appointment"]["tool"] == "book_appointment"
    assert incoming == [
        {
            "from": "confirm",
            "to": "book_appointment",
            "kind": "prompt",
            "condition": "Caller explicitly confirmed the dentist, date, and time.",
        }
    ]
    assert nodes["confirm"].get("tool") is None
    booking_tools = [
        node["id"]
        for node in flow["nodes"]
        if node.get("tool") == "book_appointment" or node.get("type") == "subagent"
    ]
    assert booking_tools == ["book_appointment"]


def test_agent_language_is_fictional_demo_without_sensitive_collection():
    flow = _load_json(FLOW_PATH)
    prompt = flow["global_prompt"].casefold()
    greet = _nodes_by_id(flow)["greet"]["instruction"]["text"].casefold()
    collect = _nodes_by_id(flow)["collect"]["instruction"]["text"].casefold()

    assert "fictional" in prompt
    assert "demonstration" in prompt
    assert "dr. elena voss" in prompt
    assert "2026-09-14" in prompt
    assert "2026-09-15" in prompt
    assert "never request a phone number, email address, mailing address, payment information, insurance, or any medical or dental history" in prompt
    assert "fictional" in greet
    assert "not a real clinic" in greet
    assert "do not collect phone, email, payment, or medical details" in collect


def test_tool_http_settings_match_failure_lab_timeout_contract():
    settings = Settings(_env_file=None)
    flow = _load_json(FLOW_PATH)
    availability = _load_json(AVAILABILITY_SCHEMA_PATH)
    booking = _load_json(BOOKING_SCHEMA_PATH)
    contract = flow["timeout_contract"]

    booking_timeout_ms = int(settings.retell_function_timeout_seconds * 1000)
    delay_ms = int(settings.failure_lab_delay_seconds * 1000)

    assert booking["http"]["method"] == "POST"
    assert booking["http"]["path"] == "/retell/book_appointment"
    assert booking["http"]["url"] == "https://<PUBLIC_HOST>/retell/book_appointment"
    assert booking["http"]["timeout_ms"] == booking_timeout_ms == contract["booking_timeout_ms"]
    assert booking["http"]["max_retry"] == contract["booking_max_retry"] == 1
    assert booking["http"]["args_at_root"] is False
    assert booking["http"]["timeout_ms"] < delay_ms == contract["failure_lab_delay_ms"]

    assert availability["http"]["method"] == "POST"
    assert availability["http"]["path"] == "/retell/check_availability"
    assert availability["http"]["url"] == "https://<PUBLIC_HOST>/retell/check_availability"
    assert availability["http"]["timeout_ms"] == contract["availability_timeout_ms"] == 10000
    assert availability["http"]["max_retry"] == contract["availability_max_retry"] == 0
    assert availability["http"]["args_at_root"] is False

    assert booking["function_node"]["wait_for_result"] is True
    assert availability["function_node"]["wait_for_result"] is True


def test_flow_json_tools_point_at_checked_in_schemas():
    flow = _load_json(FLOW_PATH)
    schemas = {tool["schema"]: tool["name"] for tool in flow["tools"]}

    assert schemas == {
        "check_availability.json": "check_availability",
        "book_appointment.json": "book_appointment",
    }
    for filename in schemas:
        assert (RETELL_DIR / filename).is_file()


def test_repository_includes_flow_diagram_and_recreation_checklist():
    checklist = CHECKLIST_PATH.read_text()
    diagram = DIAGRAM_PATH.read_text()

    assert "## Dashboard recreation checklist" in checklist
    assert "2000" in checklist
    assert "max_retry" in checklist
    assert "<PUBLIC_HOST>" in checklist
    assert "greet" in diagram
    assert "book_appointment" in diagram
    assert "Caller explicitly confirms?" in diagram
