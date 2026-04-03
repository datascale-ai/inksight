import httpx
import asyncio

print(f"httpx version: {httpx.__version__}")

async def test():
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), max_redirects=10) as client:
        r = await client.get("https://api.github.com/repos/datascale-ai/inksight/releases")
        r.raise_for_status()
        releases = r.json()

        for release in releases:
            if release.get("draft"):
                continue
            tag = release.get("tag_name", "")
            version = tag.lstrip("v")
            print(f"\nRelease: {tag} ({version})")

            for asset in release.get("assets", []):
                name = asset.get("name", "")
                if not name.endswith(".bin"):
                    continue
                url = asset.get("browser_download_url", "")
                size = asset.get("size")
                print(f"  Asset: {name}")
                print(f"  Size from API: {size} bytes ({size/1024/1024:.2f} MB)" if size else "  Size from API: N/A")

                try:
                    head = await client.head(url)
                    print(f"  HEAD status: {head.status_code}")
                    print(f"  HEAD Content-Length: {head.headers.get('content-length', 'N/A')}")
                    print(f"  HEAD Content-Type: {head.headers.get('content-type', 'N/A')}")
                    print(f"  HEAD Transfer-Encoding: {head.headers.get('transfer-encoding', 'N/A')}")
                    print(f"  HEAD Location: {head.headers.get('location', 'N/A')}")
                except Exception as e:
                    print(f"  HEAD error: {e}")

                if "0.4" in version or "0.3" in version:
                    try:
                        resp = await client.get(url, headers={"Range": "bytes=0-15"})
                        print(f"  First 16 bytes (hex): {resp.content.hex()}")
                        print(f"  Magic byte: 0x{resp.content[0]:02x} (expected 0xe9 for ESP32)")
                        print(f"  Response headers: {dict(resp.headers)}")
                    except Exception as e:
                        print(f"  GET error: {e}")
                    break
            else:
                continue
            break

asyncio.run(test())
