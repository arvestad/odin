"""Stream Snakemake's progress output into Odin.

Usage::

    snakemake 2>&1 | odin snakemake

Reads Snakemake's interleaved stdout/stderr line by line, passes every line
through to stdout unchanged (so the normal terminal output still works), and
additionally parses progress lines (``"15 of 30 steps (50%) done"``) and
known failure markers to report to an Odin server via :class:`Reporter`.
"""

import re
import sys

from odin.reporter import Reporter

PROGRESS_RE = re.compile(r"(\d+)\s+of\s+(\d+)\s+steps")
ERROR_RE = re.compile(
    r"^(Error in rule \S+:|WorkflowError:|RuleException|MissingInputException"
    r"|Exiting because a job execution failed)"
)


def run(label: str = "snakemake") -> None:
    reporter: Reporter | None = None
    try:
        for raw_line in sys.stdin:
            sys.stdout.write(raw_line)
            sys.stdout.flush()
            line = raw_line.rstrip("\n")

            match = PROGRESS_RE.search(line)
            if match:
                value, total = int(match.group(1)), int(match.group(2))
                if reporter is None:
                    reporter = Reporter(label, total=total)
                reporter.progress(value)
            elif ERROR_RE.search(line):
                if reporter is None:
                    reporter = Reporter(label)
                reporter.error(line)
    except KeyboardInterrupt:
        if reporter is not None:
            reporter.error("Interrupted")
        raise
    finally:
        if reporter is not None:
            reporter.done()
