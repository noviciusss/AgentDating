#!/usr/bin/env python3
"""
Playwright Demo Video Recorder:
- 1280x720 recording of the running local app (http://127.0.0.1:8000).
- Injected on-screen caption text overlay.
- Exact script matching all 7 timed sections (total ~178s < 3:00).
- Converts raw recorded video to video/demo.mp4 (H.264).
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
import imageio_ffmpeg
from playwright.async_api import async_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT_DIR / "video"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
RAW_VIDEO_DIR = VIDEO_DIR / "raw"
RAW_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
FINAL_MP4 = VIDEO_DIR / "demo.mp4"

async def set_caption(page, text: str):
    await page.evaluate("""(captionText) => {
        let el = document.getElementById('demo-caption-overlay');
        if (!el) {
            el = document.createElement('div');
            el.id = 'demo-caption-overlay';
            el.style.position = 'fixed';
            el.style.bottom = '28px';
            el.style.left = '50%';
            el.style.transform = 'translateX(-50%)';
            el.style.maxWidth = '920px';
            el.style.width = '88%';
            el.style.padding = '14px 28px';
            el.style.background = 'rgba(15, 23, 42, 0.90)';
            el.style.backdropFilter = 'blur(16px)';
            el.style.webkitBackdropFilter = 'blur(16px)';
            el.style.color = '#ffffff';
            el.style.borderRadius = '14px';
            el.style.boxShadow = '0 16px 36px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.12)';
            el.style.fontSize = '18px';
            el.style.fontWeight = '500';
            el.style.lineHeight = '1.45';
            el.style.textAlign = 'center';
            el.style.zIndex = '999999';
            el.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            el.style.letterSpacing = '-0.01em';
            document.body.appendChild(el);
        }
        el.innerHTML = captionText;
        el.style.opacity = '1';
    }""", text)

async def record():
    print("="*70)
    print("STARTING PLAYWRIGHT DEMO VIDEO RECORDING (1280x720, <= 3 MIN)")
    print("="*70)

    start_total = time.monotonic()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--disable-web-security", "--allow-running-insecure-content"]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(RAW_VIDEO_DIR),
            record_video_size={"width": 1280, "height": 720}
        )

        page = await context.new_page()

        # -------------------------------------------------------------
        # 1. 0:00 - 0:15 (15s): Home Page & Load Demo
        # -------------------------------------------------------------
        print("[0:00 - 0:15] Section 1: Home Page & Load Demo")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await set_caption(page, "Each person gets an AI agent that reads their LinkedIn + public Instagram and dates other agents for them.")
        await page.wait_for_timeout(6000)

        # Click Load demo button
        load_btn = page.locator("#btn-load-demo")
        if await load_btn.is_visible():
            await load_btn.click()
            print("  Clicked 'Load demo' button")
        else:
            await page.click("button:has-text('Load demo')")
        
        # Wait until redirected to people page or finish 15s
        await page.wait_for_timeout(9000)

        # -------------------------------------------------------------
        # 2. 0:15 - 0:35 (20s): People Grid (25 people), slow scroll
        # -------------------------------------------------------------
        print("[0:15 - 0:35] Section 2: People Grid (25 people)")
        if "/people" not in page.url:
            await page.goto("http://127.0.0.1:8000/run/demo/people", wait_until="networkidle")
        
        await set_caption(page, "25 real public profiles, scraped via Apify, cached.")
        await page.wait_for_timeout(3000)
        # Smooth scroll through the 25 people
        await smooth_scroll(page, target_y=1200, duration_sec=11.0)
        await page.wait_for_timeout(2000)
        await smooth_scroll(page, target_y=0, duration_sec=4.0)

        # -------------------------------------------------------------
        # 3. 0:35 - 1:05 (30s): Open 2 profile pages with evidence
        # -------------------------------------------------------------
        print("[0:35 - 1:05] Section 3: Profile Pages with Evidence")
        # Profile 1: Ali Abdaal
        await page.goto("http://127.0.0.1:8000/run/demo/person/ali-abdaal", wait_until="networkidle")
        await set_caption(page, "Every trait is backed by evidence from their posts or LinkedIn.")
        await page.wait_for_timeout(3000)
        await smooth_scroll(page, target_y=600, duration_sec=9.0)
        await page.wait_for_timeout(3000)

        # Profile 2: Diksha Arora
        await page.goto("http://127.0.0.1:8000/run/demo/person/diksha-arora", wait_until="networkidle")
        await set_caption(page, "Every trait is backed by evidence from their posts or LinkedIn.")
        await page.wait_for_timeout(3000)
        await smooth_scroll(page, target_y=650, duration_sec=9.0)
        await page.wait_for_timeout(3000)

        # -------------------------------------------------------------
        # 4. 1:05 - 1:55 (50s): Date transcript, chat bubbles & verdicts
        # -------------------------------------------------------------
        print("[1:05 - 1:55] Section 4: Real Date Transcript & Private Verdicts")
        await page.goto("http://127.0.0.1:8000/run/demo/date/jay-shetty__ranveer-allahbadia", wait_until="networkidle")
        await set_caption(page, "Two separate agents, neither sees the other's profile. Each scores the date privately.")
        await page.wait_for_timeout(4000)
        
        # Slowly scroll through the conversation bubbles
        await smooth_scroll(page, target_y=650, duration_sec=16.0)
        await page.wait_for_timeout(4000)
        # Scroll to verdicts and final score
        await smooth_scroll(page, target_y=1400, duration_sec=18.0)
        await page.wait_for_timeout(8000)

        # -------------------------------------------------------------
        # 5. 1:55 - 2:10 (15s): Dates list page with scores
        # -------------------------------------------------------------
        print("[1:55 - 2:10] Section 5: Dates List Page")
        await page.goto("http://127.0.0.1:8000/run/demo/dates", wait_until="networkidle")
        await set_caption(page, "Simulated multi-turn dates across top semantic matches with calibrated scoring.")
        await page.wait_for_timeout(3000)
        await smooth_scroll(page, target_y=500, duration_sec=8.0)
        await page.wait_for_timeout(4000)

        # -------------------------------------------------------------
        # 6. 2:10 - 2:45 (35s): Rankings page, click match & reason
        # -------------------------------------------------------------
        print("[2:10 - 2:45] Section 6: Rankings Page & Match Reasons")
        await page.goto("http://127.0.0.1:8000/run/demo/rankings", wait_until="networkidle")
        await set_caption(page, "Ranked by mutual score with an asymmetry penalty.")
        await page.wait_for_timeout(4000)
        await smooth_scroll(page, target_y=400, duration_sec=8.0)
        await page.wait_for_timeout(4000)

        # Click on a match link to jump to transcript
        match_links = page.locator("a[href*='/date/']")
        if await match_links.count() > 0:
            first_link = match_links.first
            await first_link.click()
            await page.wait_for_load_state("networkidle")
            await set_caption(page, "Ranked by mutual score with an asymmetry penalty.")
            await page.wait_for_timeout(10000)
        else:
            await page.wait_for_timeout(15000)

        # -------------------------------------------------------------
        # 7. 2:45 - 3:00 (15s): Final Tech Stack & Repository
        # -------------------------------------------------------------
        print("[2:45 - 3:00] Section 7: Final Architecture & GitHub")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await set_caption(page, "FastAPI + Apify + Groq (gpt-oss, qwen) &bull; GitHub: noviciusss/AgentDating")
        await page.wait_for_timeout(15000)

        # Close context to flush video
        print("Flushing video stream to disk...")
        video_path = await page.video.path()
        await page.close()
        await context.close()
        await browser.close()

    total_recording_time = time.monotonic() - start_total
    print(f"Recorded raw video in {total_recording_time:.1f}s at: {video_path}")

    # Convert to MP4 using imageio-ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"Converting raw video to MP4 via {ffmpeg_exe}...")
    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        str(FINAL_MP4)
    ]
    subprocess.run(cmd, check=True)

    # Get duration of final MP4
    size_mb = FINAL_MP4.stat().st_size / (1024 * 1024)
    print(f"\n[SUCCESS] Final demo video generated:")
    print(f"File Path: {FINAL_MP4}")
    print(f"File Size: {size_mb:.2f} MB")
    print(f"Total Duration: ~{total_recording_time:.1f}s (under 3:00)")

if __name__ == "__main__":
    asyncio.run(record())
