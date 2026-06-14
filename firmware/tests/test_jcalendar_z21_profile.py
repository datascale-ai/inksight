import configparser
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class JCalendarZ21ProfileTest(unittest.TestCase):
    def test_platformio_env_targets_jcalendar_z21_hardware(self):
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(ROOT / "platformio.ini", encoding="utf-8")

        env = "env:epd_42_jcalendar_z21_esp32dev"
        self.assertIn(env, parser.sections())
        self.assertEqual(parser[env].get("extends"), "common")
        self.assertEqual(parser[env].get("board"), "esp32dev")
        self.assertEqual(
            parser[env].get("board_build.partitions"),
            "partitions/jcalendar_4mb_ota.csv",
        )

        flags = parser[env].get("build_flags", "")
        expected_flags = {
            "-DBOARD_PROFILE_JCALENDAR_ESP32",
            "-DEPD_WIDTH=400",
            "-DEPD_HEIGHT=300",
            "-DEPD_PANEL_42_Z21_BWR",
            "-DEPD_BPP=2",
            "-DALLOW_INSECURE_FALLBACK=0",
        }
        for flag in expected_flags:
            self.assertIn(flag, flags)

    def test_config_declares_exact_jcalendar_pinout_without_audio(self):
        config_h = read_text("src/config.h")
        match = re.search(
            r"#elif defined\(BOARD_PROFILE_JCALENDAR_ESP32\)(.*?)#elif defined",
            config_h,
            flags=re.S,
        )
        self.assertIsNotNone(match)
        block = match.group(1)

        expected_pins = {
            "PIN_EPD_MOSI": "23",
            "PIN_EPD_SCK": "18",
            "PIN_EPD_CS": "5",
            "PIN_EPD_DC": "17",
            "PIN_EPD_RST": "16",
            "PIN_EPD_BUSY": "4",
            "PIN_BAT_ADC": "32",
            "PIN_CFG_BTN": "14",
            "PIN_LED": "22",
            "PIN_AI_CHAT_SW": "-1",
        }
        for name, value in expected_pins.items():
            self.assertRegex(block, rf"#define\s+{name}\s+{re.escape(value)}\b")
        self.assertNotIn("BOARD_HAS_AUDIO", block)

    def test_epd_driver_has_explicit_z21_tricolor_path(self):
        driver = read_text("src/epd_driver.cpp")

        self.assertIn("EPD_PANEL_42_Z21_BWR", driver)
        self.assertIn("#include <GxEPD2_3C.h>", driver)
        self.assertIn("#include <epd3c/GxEPD2_420c_Z21.h>", driver)
        self.assertIn("GxEPD2_420c_Z21", driver)
        self.assertIn("writeZ21TricolorImage", driver)
        self.assertIn("epdDisplay2bpp", driver)

    def test_z21_2bpp_mapping_keeps_white_and_red_from_swapping(self):
        driver = read_text("src/epd_driver.cpp")
        match = re.search(
            r"#if defined\(EPD_PANEL_42_Z21_BWR\)\s*(static void z21SetPixel.*?)#endif",
            driver,
            flags=re.S,
        )
        self.assertIsNotNone(match)
        z21_block = match.group(1)

        self.assertRegex(
            z21_block,
            r"static\s+bool\s+z21IsRed2bppColor\s*\([^)]*\)\s*\{[^}]*color\s*==\s*0x03[^}]*color\s*==\s*0x02[^}]*\}",
        )
        self.assertIn("z21IsRed2bppColor(color)", z21_block)
        self.assertNotRegex(z21_block, r"else\s+if\s*\(\s*color\s*==\s*0x01\s*\)")

    def test_partition_table_matches_jcalendar_four_megabyte_flash(self):
        partitions = read_text("partitions/jcalendar_4mb_ota.csv")

        expected_rows = [
            "nvs,      data, nvs,     0x9000,  0x5000,",
            "otadata,  data, ota,     0xe000,  0x2000,",
            "app0,     app,  ota_0,   0x10000, 0x1e0000,",
            "app1,     app,  ota_1,   0x1f0000,0x1e0000,",
            "spiffs,   data, spiffs,  0x3d0000,0x20000,",
            "coredump, data, coredump,0x3f0000,0x10000,",
        ]
        for row in expected_rows:
            self.assertIn(row, partitions)

    def test_jcalendar_battery_voltage_uses_calibrated_lipo_mapping(self):
        network_cpp = read_text("src/network.cpp")
        match = re.search(
            r"#if defined\(BOARD_PROFILE_JCALENDAR_ESP32\)(.*?)#elif defined\(BOARD_PROFILE_ESP32_C3_WROOM02\)",
            network_cpp,
            flags=re.S,
        )
        self.assertIsNotNone(match)
        block = match.group(1)

        self.assertIn("analogReadMilliVolts(PIN_BAT_ADC)", block)
        self.assertIn("realBatteryVoltage", block)
        self.assertRegex(block, r"\*\s*2\.0f")
        self.assertIn("measuredLow  = 2.95f", block)
        self.assertIn("measuredHigh = 4.17f", block)
        self.assertIn("targetHigh   = 3.3f", block)
        self.assertNotIn("[BAT]", network_cpp)
        self.assertNotIn("report=%.2fV", network_cpp)
        self.assertNotIn("avgRaw * (3.3f / 4095.0f) * 2.0f", block)

    def test_jcalendar_setup_does_not_force_debug_battery_read(self):
        main_cpp = read_text("src/main.cpp")
        self.assertNotRegex(
            main_cpp,
            r"#if defined\(BOARD_PROFILE_JCALENDAR_ESP32\)\s*readBatteryVoltage\(\);\s*#endif",
        )


if __name__ == "__main__":
    unittest.main()
