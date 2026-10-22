"""Run the UC8154 wire-level tests with a host C++ compiler; no ESP32 required."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    firmware = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="inksight-uc8154-") as temp_dir:
        binary = str(Path(temp_dir) / "test_uc8154")
        subprocess.run(
            shlex.split(os.environ.get("CXX", "c++"))
            + [
                "-std=c++11", "-Wall", "-Wextra", "-Wno-unused-variable",
                "-DBOARD_PROFILE_ESP32_C3", "-DPIN_EPD_CS2=8",
                "-DEPD_PANEL_42_WFH0420CZ11_UC8154_2IC",
                "-I", str(firmware / "tests/fakes"),
                "-I", str(firmware / "src"),
                str(firmware / "src/epd_driver.cpp"),
                str(firmware / "tests/test_uc8154.cpp"), "-o", binary,
            ],
            check=True,
        )
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    main()
