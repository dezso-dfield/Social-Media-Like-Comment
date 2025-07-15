import asyncio
import random
import sys
import os
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# === CONFIGURATION ===
AGENT_NAME = "agent_1"
USER_DATA_DIR = f"./user_data/{AGENT_NAME}"
SESSION_FILE = f"{USER_DATA_DIR}/session_storage.json"

MIN_DELAY = 30    # seconds
MAX_DELAY = 60

# Ensure there are comments available
COMMENT_OPTIONS = ["🔥🔥🔥", "Love this!", "Amazing post!", "💯", "So good!"]

# === LOGIN DETECTION ===
async def wait_until_logged_in(page):
    print("[🔐] Checking if we're logged in...")
    while True:
        try:
            await page.goto("https://www.instagram.com/", timeout=60000)
            await page.wait_for_timeout(5000)
            selectors = [
                'svg[aria-label="New post"]',
                'svg[aria-label="Home"]',
                'a[href="/accounts/edit/"]',
                'img[alt*="profile picture"]',
            ]
            for selector in selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible():
                        print(f"[✅] Detected logged-in session via `{selector}`.")
                        return
                except:
                    continue
            if "accounts/login" in page.url:
                print("[🚫] Redirected to login page. Login required.")
            cookies = await page.context.cookies()
            if any(c['name'] == 'ds_user_id' for c in cookies):
                print("[✅] Found valid Instagram session cookie.")
                return
        except PlaywrightTimeoutError:
            pass
        print("[⏳] Still waiting for manual login... (Browser open)")
        await page.screenshot(path="login_wait.png")
        await page.wait_for_timeout(5000)

# === MANUAL MODE ===
async def manual_mode():
    print("[🧍] Launching browser in manual mode...")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = await browser.new_page()
        await page.goto("https://www.instagram.com/", timeout=0)
        print("[✅] Please log in manually, then close the browser tab.")
        while len(browser.pages) > 0:
            await asyncio.sleep(2)
        print("[💾] Saving cookies and localStorage...")
        storage_state = await browser.storage_state()
        with open(SESSION_FILE, "w") as f:
            json.dump(storage_state, f, indent=2)
        print(f"[✅] Session saved to {SESSION_FILE}")
        await browser.close()

# === AUTOMATION MODE ===
async def interact_with_post(url: str):
    print(f"[🚀] Launching automation bot for {AGENT_NAME}")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = await browser.new_page()
        await wait_until_logged_in(page)
        print(f"[📷] Navigating to post: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        if not page.url.startswith(url):
            print(f"[⚠️] Unexpected redirect. Still on: {page.url}")
            await page.screenshot(path="redirect_error.png")
            await browser.close()
            return
        else:
            print("[📌] On correct post URL.")

        delay = random.randint(MIN_DELAY, MAX_DELAY)
        print(f"[🕒] Sleeping {delay} seconds before interacting...")
        await page.wait_for_timeout(delay * 1000)

        # === LIKE SECTION ===
        try:
            print("[🤍] Checking if post is already liked...")
            liked_icon_locator = page.locator('svg[aria-label="Mégsem tetszik"][width="24"], svg[aria-label="Unlike"][width="24"]')
            # Hungarian and English 'Like' labels for the unliked icon
            unliked_icon_locator = page.locator('svg[aria-label="Tetszik"][width="24"], svg[aria-label="Like"][width="24"]')


            is_already_liked = False
            try:
                await liked_icon_locator.first.wait_for(state="visible", timeout=3000)
                is_already_liked = True
                print("[❤️] Post already liked.")
            except PlaywrightTimeoutError:
                is_already_liked = False

            if not is_already_liked:
                print("[🤍] Post not liked yet. Attempting to click the 'Like' icon or its parents...")
                like_svg_icon_element = page.locator(
                    'svg[aria-label="Tetszik"][width="24"], '
                    'svg[aria-label="Like"][width="24"]'
                ).first

                clickable_targets = []
                clickable_targets.append(("SVG icon", like_svg_icon_element))

                inner_button = like_svg_icon_element.locator('xpath=ancestor::div[contains(@role, "button")][1]').first
                if await inner_button.is_visible():
                    clickable_targets.append(("Inner Button DIV", inner_button))

                outer_wrapper = like_svg_icon_element.locator('xpath=ancestor::div[contains(@class, "x1ypdohk")][1]').first
                if await outer_wrapper.is_visible():
                    clickable_targets.append(("Outer Wrapper", outer_wrapper))

                top_span = like_svg_icon_element.locator('xpath=ancestor::span[contains(@class, "x1qfufaz")][1]').first
                if await top_span.is_visible():
                    clickable_targets.append(("Top Span", top_span))

                for name, locator in clickable_targets:
                    try:
                        print(f"[🤍] Trying to click: {name}")
                        await locator.click(force=True)
                        await liked_icon_locator.first.wait_for(state="visible", timeout=5000)
                        print(f"[❤️] Liked the post by clicking: {name}")
                        break  # STOP iterating click targets, BUT DO NOT return or exit here
                    except Exception as e: # Catch specific exception for more precise handling
                        print(f"[⚠️] Click on {name} failed: {e}")
            else:
                # If already liked, still proceed to comment section
                pass # No action needed, proceed to next section
        except Exception as e:
            print(f"[❌] Like process failed: {e}")

        # === COMMENT SECTION (ALWAYS RUNS) ===
        try:
            # We want to make sure it tries to comment every time with this update
            # The original code had a 60% chance (random.random() < 0.6), removed for consistent commenting
            comment = random.choice(COMMENT_OPTIONS)
            print(f"[💬] Preparing to comment: {comment}")
            
            # More robust selectors for the comment box, including roles and specific data attributes if available
            comment_box_locators = [
                'textarea[aria-label*="Hozzászólás"]',
                'textarea[aria-label*="Comment"]',
                'textarea[placeholder*="Hozzászólás"]',
                'textarea[placeholder*="Comment"]',
                'div[aria-label*="Hozzászólás"]', # Sometimes it's a div acting as a textbox
                'div[aria-label*="Comment"]',
                'div[role="textbox"]' # Common role for editable text areas
            ]
            
            comment_box = None
            for selector in comment_box_locators:
                current_locator = page.locator(selector).first
                try:
                    await current_locator.wait_for(state="visible", timeout=5000) # Shorter individual timeout
                    if await current_locator.is_editable() or await current_locator.is_enabled():
                        comment_box = current_locator
                        print(f"[✅] Found comment box using selector: {selector}")
                        break
                except PlaywrightTimeoutError:
                    print(f"[ℹ️] Comment box not found with selector: {selector}. Trying next...")
                except Exception as e:
                    print(f"[⚠️] Error checking selector {selector}: {e}")

            if comment_box:
                await comment_box.click(force=True)
                await page.wait_for_timeout(1000) # Small delay after clicking
                await comment_box.fill("") # Clear any pre-existing text
                await page.keyboard.type(comment, delay=100)
                await page.keyboard.press("Enter")
                print(f"[✅] Commented: {comment}")
                await page.wait_for_timeout(3000) # Wait for comment to potentially post
            else:
                print("[❌] Could not find an interactive comment box after trying all selectors.")
                await page.screenshot(path="comment_box_not_found.png") # Screenshot for debugging
        except Exception as e:
            print(f"[❌] Comment failed: {e}")
            await page.screenshot(path="comment_error.png") # Screenshot on comment failure


        await page.wait_for_timeout(2000)
        await browser.close()

# === ENTRYPOINT ===
if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--manual":
        asyncio.run(manual_mode())
    elif len(sys.argv) == 2 and sys.argv[1].startswith("https://www.instagram.com/"):
        post_url = sys.argv[1]
        asyncio.run(interact_with_post(post_url))
    else:
        print("Usage:")
        print("  Manual login mode: python ig_bot.py --manual")
        print("  Auto post mode:    python ig_bot.py <instagram_post_url>")
        sys.exit(1)
