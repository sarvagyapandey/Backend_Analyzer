"""
Run Robot Framework suites for backend analyzer and generate HTML reports.

Usage:
    python3 run_robot_tests.py
    python3 run_robot_tests.py --suite unit_tests.robot
    python3 run_robot_tests.py --outputdir reports
"""
from __future__ import annotations

import argparse
import html
import xml.etree.ElementTree as ET
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run Robot Framework test suites.")
    parser.add_argument("--suite", default="robot_tests", help="Robot suite file or directory.")
    parser.add_argument("--outputdir", default="robot_results", help="Where to write output.xml, log.html, and report.html.")
    args = parser.parse_args(argv)

    try:
        from robot import run
    except ImportError:
        print("Robot Framework is not installed. Run: pip install -r requirements.txt")
        return 1

    rc = run(
        args.suite,
        outputdir=args.outputdir,
        loglevel="INFO",
        reporttitle="Backend Analyzer Robot Report",
        logtitle="Backend Analyzer Robot Log",
    )
    _write_rich_report(Path(args.outputdir) / "output.xml", Path(args.outputdir) / "report.html")
    print(f"Robot reports written to: {args.outputdir}")
    return rc


def _collect_messages(test_elem):
    messages = []
    for msg in test_elem.findall(".//msg"):
        text = (msg.text or "").strip()
        if text:
            messages.append(f"[{msg.get('level', 'INFO')}] {text}")
    return messages


def _write_rich_report(output_xml: Path, report_html: Path) -> None:
    if not output_xml.exists():
        return

    root = ET.parse(output_xml).getroot()
    tests = []
    for test in root.iter("test"):
        status = test.find("status")
        tests.append(
            {
                "name": test.get("name", "Unnamed test"),
                "status": status.get("status") if status is not None else "UNKNOWN",
                "message": (status.text or "").strip() if status is not None and status.text else "",
                "doc": (test.findtext("doc") or "").strip(),
                "messages": _collect_messages(test),
            }
        )

    rows = []
    for item in tests:
        details = []
        if item["doc"]:
            details.append(f"<p><strong>Documentation:</strong> {html.escape(item['doc'])}</p>")
        if item["message"]:
            details.append(f"<p><strong>Status:</strong> {html.escape(item['message'])}</p>")
        if item["messages"]:
            details.append("<div class='messages'><strong>Messages</strong><ul>")
            for msg in item["messages"]:
                details.append(f"<li>{html.escape(msg)}</li>")
            details.append("</ul></div>")
        else:
            details.append("<p><em>No messages were logged for this test.</em></p>")

        rows.append(
            "<section class='test'>"
            f"<h2>{html.escape(item['name'])}</h2>"
            f"<div class='status {item['status'].lower()}'>{html.escape(item['status'])}</div>"
            + "".join(details)
            + "</section>"
        )

    report_html.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Backend Analyzer Robot Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111; }}
    .test {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; margin: 16px 0; }}
    .status {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; margin-bottom: 12px; }}
    .status.pass {{ background: #e6ffed; color: #116329; }}
    .status.fail {{ background: #fff1f1; color: #a40e26; }}
    .messages ul {{ margin: 8px 0 0 20px; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Backend Analyzer Robot Report</h1>
  <p>This report includes a visible messages section for each test.</p>
  {''.join(rows)}
</body>
</html>""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
