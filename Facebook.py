import asyncio
import random
import sys
import os
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# === CONFIGURATION ===
AGENT_NAME = "facebook_agent"
USER_DATA_DIR = f"./user_data/{AGENT_NAME}"
SESSION_FILE = f"{USER_DATA_DIR}/session_storage.json"

MIN_DELAY = 30    # seconds
MAX_DELAY = 60

COMMENT_OPTIONS = ["🔥🔥🔥", "Love this!", "Amazing post!", "💯", "So good!"]

# === LOGIN DETECTION ===
async def wait_until_logged_in(page):
    print("[🔐] Checking if we're logged in...")
    while True:
        try:
            await page.goto("https://www.facebook.com/", timeout=60000)
            await page.wait_for_timeout(5000)

            cookies = await page.context.cookies()
            if any(c['name'] == 'c_user' for c in cookies):
                print("[✅] Found Facebook session cookie. Assuming logged in.")
                return

            selectors = [
                'div[aria-label="Your profile"]',
                'div[aria-label="Home"]',
                'div[aria-label="Create a post"]',
                'img[alt*="profile picture"]',
                'a[href*="/me/"]',
            ]
            
            is_logged_in_via_ui = False
            for selector in selectors:
                try:
                    el = page.locator(selector).first
                    await el.wait_for(state="visible", timeout=3000) 
                    if await el.is_visible():
                        print(f"[✅] Detected logged-in session via `{selector}`.")
                        is_logged_in_via_ui = True
                        break
                except PlaywrightTimeoutError:
                    continue
                except Exception as e:
                    print(f"[⚠️] Error checking selector `{selector}`: {e}")
                    continue

            if is_logged_in_via_ui:
                return

            if "facebook.com/login" in page.url or "facebook.com/checkpoint" in page.url:
                print("[🚫] Redirected to login/checkpoint page. Manual login required.")
            
        except PlaywrightTimeoutError:
            print("[⏳] Page navigation timed out during login check. Retrying...")
        except Exception as e:
            print(f"[❌] An error occurred during login detection: {e}")
            
        print("[⏳] Still waiting for manual login... (Browser open)")
        await page.screenshot(path="facebook_login_wait.png")
        await page.wait_for_timeout(5000)

# === MANUAL MODE ===
async def manual_mode():
    print("[🧍] Launching browser in manual mode for Facebook...")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = await browser.new_page()
        await page.goto("https://www.facebook.com/", timeout=0)
        print("[✅] Please log in manually to Facebook, then close the browser tab.")
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
    print(f"[🚀] Launching automation bot for {AGENT_NAME} on Facebook")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = await browser.new_page()
        await wait_until_logged_in(page)
        print(f"[📷] Navigating to Facebook post: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        if not page.url.startswith("https://www.facebook.com/"):
            print(f"[⚠️] Unexpected redirect. Still on: {page.url}")
            await page.screenshot(path="facebook_redirect_error.png")
            await browser.close()
            return
        else:
            print("[📌] On Facebook post URL.")

        delay = random.randint(MIN_DELAY, MAX_DELAY)
        print(f"[🕒] Sleeping {delay} seconds before interacting...")
        await page.wait_for_timeout(delay * 1000)

        # === LIKE SECTION ===
        try:
            print("[🤍] Checking if Facebook post is already liked...")
            
            # Selectors for the "liked" state (button has changed to "Unlike" or icon has changed)
            liked_state_locators = [
                'div[aria-label="Tetszik eltávolítása"]', # Hungarian for "Remove Like"
                'div[aria-label="Unlike"]',              # English for "Unlike"
                # Check for the specific icon background position that indicates liked
                'div[role="button"] i[data-visualcompletion="css-img"][style*="background-position: 0px -714px;"]',
                # Check for the blue text color on the 'Tetszik' span
                'span[data-ad-rendering-role="tetszik_button"][style*="color: var(--reaction-like, #0866FF);"]'
            ]

            is_already_liked = False
            for locator_str in liked_state_locators:
                try:
                    # Use wait_for for visibility with timeout, then check is_visible
                    liked_el = page.locator(locator_str).first
                    await liked_el.wait_for(state="visible", timeout=2000) 
                    if await liked_el.is_visible(): # Now this will work correctly
                        is_already_liked = True
                        print(f"[❤️] Post already liked (detected via: {locator_str}).")
                        break
                except PlaywrightTimeoutError:
                    continue
                except Exception as e:
                    print(f"[⚠️] Error checking liked state with locator `{locator_str}`: {e}")

            if not is_already_liked:
                print("[🤍] Facebook post not liked yet. Attempting to click the 'Like' button...")
                clicked_successfully = False
                # Selectors for the "unlike" state (i.e., the button to click to like)
                # Prioritize specific combination of role="button" and aria-label/span text
                like_button_locators = [
                    # Most specific: role="button" with aria-label matching "Tetszik" or "Like"
                    'div[role="button"][aria-label="Tetszik"]',
                    'div[role="button"][aria-label="Like"]',
                    # Less specific but still good: role="button" containing the 'Tetszik' span without color
                    'div[role="button"]:has(span[data-ad-rendering-role="tetszik_button"][style=""])',
                    'div[role="button"]:has(span[data-ad-rendering-role="tetszik_button"]):not(:has(span[style*="color: var(--reaction-like"]'
                ]

                for name, locator_str in [
                    ("Like Button (aria-label Tetszik/Like)", 'div[role="button"][aria-label="Tetszik"], div[role="button"][aria-label="Like"]'),
                    ("Like Button (Text Tetszik/Like without color)", 'div[role="button"]:has(span[data-ad-rendering-role="tetszik_button"][style=""]), div[role="button"]:has(span:has-text("Like"):not([style*="color"]))')
                ]:
                    try:
                        like_button_element = page.locator(locator_str).first
                        await like_button_element.wait_for(state="visible", timeout=5000)
                        await like_button_element.click(force=True)
                        print(f"[❤️] Liked the Facebook post by clicking: {name}")
                        clicked_successfully = True
                        # After clicking, confirm the like by checking for the 'liked' state
                        await page.wait_for_timeout(2000) # Small pause
                        is_now_liked = False
                        for liked_locator_str_confirm in liked_state_locators:
                            try:
                                await page.locator(liked_locator_str_confirm).first.wait_for(state="visible", timeout=3000)
                                is_now_liked = True
                                print(f"[✅] Confirmed like by seeing '{liked_locator_str_confirm}'.")
                                break
                            except PlaywrightTimeoutError:
                                continue
                        if not is_now_liked:
                            print("[⚠️] Post was clicked but could not confirm liked state.")
                        break # Stop trying to click if one succeeded
                    except PlaywrightTimeoutError:
                        print(f"[⚠️] Like button '{name}' not found or visible. Trying next...")
                    except Exception as e:
                        print(f"[❌] Click on '{name}' failed: {e}")
                
                if not clicked_successfully:
                    print("[❌] Failed to find and click any 'Like' button.")
                    await page.screenshot(path="facebook_like_fail.png")

        except Exception as e:
            print(f"[❌] Facebook Like process failed: {e}")
            await page.screenshot(path="facebook_like_error.png")

        # === COMMENT SECTION (ALWAYS RUNS) ===
        try:
            comment = random.choice(COMMENT_OPTIONS)
            print(f"[💬] Preparing to comment on Facebook post: {comment}")
            
            comment_box_locators = [
                'div[aria-label="Hozzászólás írása…"][contenteditable="true"][role="textbox"]',
                'div[aria-label="Write a comment…"][contenteditable="true"][role="textbox"]',
                'div[role="textbox"][contenteditable="true"]',
                'textarea[aria-label*="comment"]',
                'textarea[placeholder*="comment"]',
            ]
            
            comment_box = None
            for selector in comment_box_locators:
                current_locator = page.locator(selector).first
                try:
                    await current_locator.wait_for(state="visible", timeout=5000)
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
                await page.wait_for_timeout(1000)
                await comment_box.fill("")
                await page.keyboard.type(comment, delay=100)
                
                post_button_locators = [
                    'div[aria-label="Post"]',
                    'div[aria-label="Comment"]',
                    'div[role="button"]:has(span:has-text("Post"))',
                    'div[role="button"]:has(span:has-text("Comment"))',
                ]
                
                post_button_found = False
                for post_btn_selector in post_button_locators:
                    try:
                        post_button = page.locator(post_btn_selector).first
                        await post_button.wait_for(state="visible", timeout=2000)
                        await post_button.click(force=True)
                        print(f"[✅] Clicked 'Post' button for comment.")
                        post_button_found = True
                        break
                    except PlaywrightTimeoutError:
                        continue
                    except Exception as e:
                        print(f"[⚠️] Error clicking post button with selector {post_btn_selector}: {e}")

                if not post_button_found:
                    print("[ℹ️] No explicit 'Post' button found. Attempting to press Enter.")
                    await page.keyboard.press("Enter")

                print(f"[✅] Commented: {comment}")
                await page.wait_for_timeout(3000)
            else:
                print("[❌] Could not find an interactive comment box after trying all selectors.")
                await page.screenshot(path="facebook_comment_box_not_found.png")
        except Exception as e:
            print(f"[❌] Facebook Comment failed: {e}")
            await page.screenshot(path="facebook_comment_error.png")

        await page.wait_for_timeout(2000)
        await browser.close()

# === ENTRYPOINT ===
if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--manual":
        asyncio.run(manual_mode())
    elif len(sys.argv) == 2 and sys.argv[1].startswith("https://www.facebook.com/"):
        post_url = sys.argv[1]
        asyncio.run(interact_with_post(post_url))
    else:
        print("Usage:")
        print("  Manual login mode: python fb_bot.py --manual")
        print("  Auto post mode:    python fb_bot.py <facebook_post_url>")
        sys.exit(1)
