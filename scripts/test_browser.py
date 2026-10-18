import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge", headless=True)
            print("Successfully launched Microsoft Edge via Playwright!")
            await browser.close()
            return "msedge"
        except Exception as e:
            print("Edge failed:", e)
        try:
            browser = await p.chromium.launch(channel="chrome", headless=True)
            print("Successfully launched Google Chrome via Playwright!")
            await browser.close()
            return "chrome"
        except Exception as e:
            print("Chrome failed:", e)
        try:
            browser = await p.chromium.launch(headless=True)
            print("Successfully launched default Chromium via Playwright!")
            await browser.close()
            return "chromium"
        except Exception as e:
            print("Default chromium failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
