"""Running the live command requires explicit opt-in before reading configuration."""

import subprocess
import sys
from pathlib import Path


def test_live_smoke_requires_explicit_enable(tmp_path):
    script = Path(__file__).parents[2] / "scripts" / "smoke_food_trends.py"
    output = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, str(script), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "Live calls require --enable-live" in result.stderr
    assert not output.exists()
