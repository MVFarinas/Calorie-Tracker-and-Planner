import subprocess
import sys
from pathlib import Path


def test_example_demo_runs():
    result = subprocess.run([sys.executable, "-m", "calorie_tracker.example"], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parent.parent, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "Maintenance Estimate:" in result.stdout
    assert "To achieve a weight of 190 lbs in 60 days:" in result.stdout
