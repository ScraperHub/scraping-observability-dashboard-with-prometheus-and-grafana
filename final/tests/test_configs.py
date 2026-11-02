"""Static checks for the Prometheus and Grafana files (promtool runs separately)."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "grafana" / "dashboards" / "crawlbase.json"
RULES = ROOT / "prometheus" / "rules" / "crawlbase.rules.yml"
ALERTS = ROOT / "grafana" / "provisioning" / "alerting" / "crawlbase-alerts.yml"


def all_panels(dash):
    for panel in dash["panels"]:
        yield panel
        yield from panel.get("panels", [])


def recorded_names():
    rules = yaml.safe_load(RULES.read_text())
    return {r["record"] for g in rules["groups"] for r in g["rules"] if "record" in r}


def test_dashboard_loads_and_has_required_panels():
    dash = json.loads(DASHBOARD.read_text())
    assert dash["uid"] == "crawlbase-observability"
    titles = {p["title"] for p in all_panels(dash)}
    for required in [
        "Success rate per domain",
        "p95 latency by complexity tier",
        "Credits remaining",
        "Projected days to zero",
        "Top failing domains (range)",
        "cb_status breakdown",
        "Local vs Account API success rate",
    ]:
        assert required in titles


def test_dashboard_matches_generator():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_dashboard", ROOT / "scripts" / "build_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.build() == json.loads(DASHBOARD.read_text())


def test_panel_ids_unique_and_datasource_set():
    dash = json.loads(DASHBOARD.read_text())
    ids = [p["id"] for p in all_panels(dash)]
    assert len(ids) == len(set(ids))
    for panel in all_panels(dash):
        if panel["type"] != "row":
            assert panel["datasource"]["uid"] == "prometheus"
            assert panel["targets"]


def test_every_recording_rule_used_in_panels_exists():
    names = recorded_names()
    dash = json.loads(DASHBOARD.read_text())
    used = set()
    for panel in all_panels(dash):
        for t in panel.get("targets", []):
            used |= set(re.findall(r"crawlbase:[a-z0-9_:]+", t["expr"]))
    assert used, "dashboard should use recording rules"
    assert used <= names, used - names


def test_grafana_alert_rules():
    data = yaml.safe_load(ALERTS.read_text())
    rules = [r for g in data["groups"] for r in g["rules"]]
    assert {r["uid"] for r in rules} == {"cb-domain-success-low", "cb-normal-token-blocked", "cb-credits-low"}
    names = recorded_names()
    for rule in rules:
        query = rule["data"][0]
        assert query["datasourceUid"] == "prometheus"
        for ref in re.findall(r"crawlbase:[a-z0-9_:]+", query["model"]["expr"]):
            assert ref in names
        refs = {d["refId"] for d in rule["data"]}
        assert rule["condition"] in refs
    by_uid = {r["uid"]: r for r in rules}
    assert by_uid["cb-domain-success-low"]["for"] == "10m"
    assert by_uid["cb-domain-success-low"]["data"][2]["model"]["conditions"][0]["evaluator"]["params"] == [0.9]
    assert by_uid["cb-credits-low"]["data"][2]["model"]["conditions"][0]["evaluator"]["params"] == [3]
    assert "576" in json.dumps(yaml.safe_load(RULES.read_text()))


def test_alert_templates_use_single_dollar():
    # Grafana 11 keeps "$$" literally in alert annotations (seen live), so use "$".
    text = ALERTS.read_text()
    assert "$$" not in text
    assert "$labels.domain" in text and "$values.B.Value" in text
