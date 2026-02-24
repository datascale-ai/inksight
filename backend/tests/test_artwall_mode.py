"""
测试 ARTWALL 模式
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from core.json_content import generate_json_mode_content
from core.json_renderer import render_json_mode
import json

load_dotenv()


async def main():
    print("Testing ARTWALL mode...")

    mode_path = os.path.join(
        os.path.dirname(__file__), "..", "core", "modes", "builtin", "artwall.json"
    )
    with open(mode_path, "r", encoding="utf-8") as f:
        mode_def = json.load(f)

    content = await generate_json_mode_content(
        mode_def,
        date_str="2月14日",
        weather_str="晴 15°C",
        festival="情人节",
        llm_provider="aliyun",
        llm_model="qwen-image-max",
    )
    
    print(f"Generated content:")
    print(f"  Title: {content['artwork_title']}")
    print(f"  Image URL: {content.get('image_url', 'N/A')[:50]}...")
    print(f"  Description: {content['description']}")
    
    img = render_json_mode(
        mode_def,
        content,
        date_str="2月14日 周六",
        weather_str="晴 15°C",
        battery_pct=85,
        weather_code=0,
        time_str="14:30",
    )
    
    img.save("test_artwall_output.png")
    print("✓ Saved to test_artwall_output.png")


if __name__ == "__main__":
    asyncio.run(main())
