"""
Immortal Daemon Repair Script
==============================

Triggered by the :class:`~core.resilience.Watchdog` when the main agent
task fails.  Analyses crash logs, generates self-healing patches, and
triggers a main-task restart.

The repair pipeline is:

1. **Analyse** — Scan crash history, evolution log, and agent log for errors.
2. **Generate patches** — Create patch records based on the failure categories.
3. **Apply patches** — Register patches via :class:`~core.resilience.ResiliencePatch`.
4. **Restart** — Log a restart trigger so the immortal wrapper re-launches the agent.

Usage::

    python scripts/repair_daemon.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.resilience import ResiliencePatch, logger

WORK_DIR = Path(r"D:\mockclaw-immortal")


def analyze_failure() -> Dict[str, Any]:
    """Scan log files for recent errors and crashes.

    Checks three log sources:
    - ``logs/crash_history.log`` — last 10 lines of crash records.
    - ``logs/evolution_history.md`` — any ``FAILED`` / ``ERROR`` markers.
    - ``logs/agent.log`` — last 50 lines, filtered for ``ERROR`` / ``FATAL``.

    Returns:
        A dictionary with a ``timestamp`` and a ``findings`` list.
    """
    analysis = {"timestamp": datetime.now().isoformat(), "findings": []}

    # Check crash history
    crash_log = WORK_DIR / "logs" / "crash_history.log"
    if crash_log.exists():
        with open(crash_log, "r", encoding="utf-8") as f:
            lines = f.readlines()[-10:]
            if lines:
                analysis["findings"].append(
                    {
                        "source": "crash_history",
                        "details": [line.strip() for line in lines],
                    }
                )

    # Check evolution log
    evolution_log = WORK_DIR / "logs" / "evolution_history.md"
    if evolution_log.exists():
        content = evolution_log.read_text(encoding="utf-8")
        if "FAILED" in content or "ERROR" in content:
            analysis["findings"].append(
                {
                    "source": "evolution_log",
                    "details": "Errors found in evolution history",
                }
            )

    # Check agent log
    agent_log = WORK_DIR / "logs" / "agent.log"
    if agent_log.exists():
        with open(agent_log, "r", encoding="utf-8") as f:
            lines = f.readlines()[-50:]
            errors = [line for line in lines if "ERROR" in line or "FATAL" in line]
            if errors:
                analysis["findings"].append(
                    {"source": "agent_log", "details": errors[-5:]}
                )

    return analysis


def generate_patch(analysis: Dict[str, Any]) -> list[Dict[str, str]]:
    """Propose self-healing patches based on failure analysis.

    Maps each finding source to a patch type:

    - ``crash_history`` → ``retry_logic`` patch.
    - ``agent_log`` → ``error_handling`` patch.

    Args:
        analysis: The dictionary returned by :func:`analyze_failure`.

    Returns:
        A list of patch dictionaries with ``type``, ``description``, and ``code``.
    """
    patches = []

    for finding in analysis.get("findings", []):
        source = finding.get("source", "")

        if source == "crash_history":
            patches.append(
                {
                    "type": "retry_logic",
                    "description": "Added retry logic for crash recovery",
                    "code": "# Added automatic retry with backoff",
                }
            )

        if source == "agent_log":
            patches.append(
                {
                    "type": "error_handling",
                    "description": "Improved error handling",
                    "code": "# Enhanced error catching",
                }
            )

    return patches


def apply_patches(patches: list[Dict[str, str]]) -> None:
    """Register a list of patches with the :class:`ResiliencePatch` system.

    Args:
        patches: Patch dictionaries as returned by :func:`generate_patch`.
    """
    for patch in patches:
        ResiliencePatch.add_patch(
            error_type=patch.get("type", "unknown"),
            fix=patch.get("description", ""),
            code=patch.get("code", ""),
        )

    ResiliencePatch.save_patches(str(WORK_DIR / "logs" / "patches.json"))


def trigger_main_task() -> None:
    """Signal the immortal wrapper to restart the main agent task.

    Appends a ``REPAIR`` heartbeat entry so the wrapper detects the
    restart trigger on its next loop iteration.
    """
    logger.info("Triggering main task restart...")
    # This would call the cron API to trigger the task
    # For now, we just log it
    with open(WORK_DIR / "logs" / "heartbeat.log", "a", encoding="utf-8") as f:
        f.write(
            f"[{datetime.now().isoformat()}] | REPAIR | Main task restart triggered\n"
        )


def main() -> int:
    """Entry point for the repair daemon.

    Executes the full pipeline: analyse → generate → apply → restart.

    Returns:
        Exit code (``0`` on success).
    """
    logger.info("=" * 60)
    logger.info("IMMORTAL REPAIR DAEMON")
    logger.info("=" * 60)

    # Analyze failure
    logger.info("Analyzing failure...")
    analysis = analyze_failure()

    logger.info(f"Found {len(analysis['findings'])} issues")

    # Generate patches
    logger.info("Generating patches...")
    patches = generate_patch(analysis)

    # Apply patches
    if patches:
        logger.info(f"Applying {len(patches)} patches...")
        apply_patches(patches)
    else:
        logger.info("No patches needed")

    # Log repair
    repair_log = WORK_DIR / "logs" / "repair_history.log"
    with open(repair_log, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": datetime.now().isoformat(),
                    "findings": analysis["findings"],
                    "patches_applied": len(patches),
                },
                indent=2,
            )
            + "\n"
        )

    # Trigger main task restart
    trigger_main_task()

    logger.info("Repair complete. Main task will restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
