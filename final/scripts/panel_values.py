"""Evaluate every dashboard panel query once (instant) and print the results.

Grafana variables are replaced with fixed windows: $__range=30m, $__rate_interval=1m.
Run inside the compose network:
    docker run --rm --network cbwatch_default -v "$PWD:/app" -w /app cbwatch-dev python scripts/panel_values.py
"""

import json
from pathlib import Path

import httpx

PROM = "http://prometheus:9090/api/v1/query"
DASH = Path(__file__).resolve().parents[1] / "grafana" / "dashboards" / "crawlbase.json"


def panels(dash):
    for p in dash["panels"]:
        yield p
        yield from p.get("panels", [])


def main() -> None:
    dash = json.loads(DASH.read_text())
    for panel in panels(dash):
        for target in panel.get("targets", []):
            expr = target["expr"].replace("$__range", "30m").replace("$__rate_interval", "1m")
            result = httpx.get(PROM, params={"query": expr}).json()["data"]["result"]
            values = []
            for s in result:
                labels = {k: v for k, v in s["metric"].items() if k not in ("__name__", "instance", "job")}
                values.append((labels, round(float(s["value"][1]), 3)))
            print(f"{panel['title']} [{target['refId']}]: {values}")


if __name__ == "__main__":
    main()
