"""Run pytest and surface failures as public GitHub check annotations."""

import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode:
        failure = result.stdout.split("=================================== FAILURES", 1)[-1]
        message = failure[-12000:].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Pytest failure::{message}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
