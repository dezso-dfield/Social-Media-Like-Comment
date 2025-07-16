import asyncio
import random
import sys
import os
import json
import re # Import regex module
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- TOGETHER AI INTEGRATION ---
from dotenv import load_dotenv
from together import Together

load_dotenv() # Load environment variables from .env file
API_KEY = os.getenv("TOGETHER_API_KEY")

# Initialize Together AI client
client = Together(api_key=API_KEY)

# Function to load prompts from files
def load_prompt(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"[⚠️] Prompt file '{path}' not found. Creating a dummy file.")
        default_content = ""
        if "comment" in path:
            default_content = "You are an AI assistant for a social media bot. Your task is to generate short, positive, and engaging comments for Instagram posts. Keep responses under 20 words. Avoid anything controversial or negative. Use emojis appropriately."
        elif "message" in path:
            default_content = "You are an AI assistant for an Instagram bot. Your task is to generate concise and polite replies to direct messages.\nContext: The user's last message was: \"{last_message}\"\nThe sender's name is: \"{sender_name}\"\nKeep your reply under 30 words. Aim for a friendly and brief acknowledgment. If the message seems like a spam or a bot, you can give a generic polite response. Do not ask for personal information."
        
        # Ensure we write with utf-8 for consistency
        with open(path, "w", encoding="utf-8") as file:
            file.write(default_content)
        return default_content

# Load specific prompts for different contexts
SYSTEM_PROMPT_COMMENT = load_prompt("prompt_instagram_comment.txt")
SYSTEM_PROMPT_MESSAGE_REPLY = load_prompt("prompt_instagram_message.txt")

# Asynchronous function to call Together AI
async def generate_ai_response(prompt_type: str, user_message: str = "", sender_name: str = ""):
    messages_payload = []
    current_system_prompt = ""

    if prompt_type == "comment":
        current_system_prompt = SYSTEM_PROMPT_COMMENT
        messages_payload.append({"role": "user", "content": "Generate a short, positive comment for an Instagram post."})
    elif prompt_type == "message_reply":
        formatted_system_prompt = SYSTEM_PROMPT_MESSAGE_REPLY.format(
            last_message=user_message,
            sender_name=sender_name
        )
        messages_payload.append({"role": "user", "content": f"Based on this context, reply to '{sender_name}' who sent: '{user_message}'"})
    else:
        raise ValueError("Invalid prompt_type. Must be 'comment' or 'message_reply'.")

    messages_payload.insert(0, {"role": "system", "content": current_system_prompt})

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=messages_payload,
            max_tokens=50,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[❌] Error generating AI response: {e}")
        if prompt_type == "comment":
            return random.choice(["Great post!", "Awesome!", "Nice one!"])
        elif prompt_type == "message_reply":
            return random.choice(["Thanks for your message!", "Got it!"])
        return "Sorry, I can't generate a response right now."

# --- END TOGETHER AI INTEGRATION ---


# === CONFIGURATION ===
AGENT_NAME = "instagram_agent"
USER_DATA_DIR = f"./user_data/{AGENT_NAME}"
SESSION_FILE = f"{USER_DATA_DIR}/session_storage.json"

MIN_DELAY = 30    # seconds
MAX_DELAY = 60

MESSAGE_OPTIONS = ["🔥🔥🔥", "Love this!", "Amazing post!", "💯", "So good!", "Thanks for reaching out!", "Got it, will get back to you soon!", "Appreciate the message!", "Hello there!"]


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
                except PlaywrightTimeoutError:
                    continue
                except Exception as e:
                    print(f"[⚠️] Error checking selector `{selector}`: {e}")
            if "accounts/login" in page.url:
                print("[🚫] Redirected to login page. Login required.")
            cookies = await page.context.cookies()
            if any(c['name'] == 'ds_user_id' for c in cookies):
                print("[✅] Found valid Instagram session cookie.")
                return
        except PlaywrightTimeoutError:
            print("[⏳] Page navigation timed out during login check. Retrying...")
        except Exception as e:
            print(f"[❌] An error occurred during login detection: {e}")
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

# === AUTOMATION MODE - INTERACT WITH POST ===
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
                        break
                    except Exception as e:
                        print(f"[⚠️] Click on {name} failed: {e}")
            else:
                pass
        except Exception as e:
            print(f"[❌] Like process failed: {e}")

        # === COMMENT SECTION (ALWAYS RUNS) ===
        try:
            # For comments on posts, we need the post description/caption
            # This is a general attempt to find it. Instagram's caption is usually complex.
            # You might need to refine this selector based on actual post HTML
            post_description = "No description found."
            try:
                # Common pattern for Instagram post caption: div holding the text
                caption_locator = page.locator('div[role="dialog"] div[role="button"] ~ div span[dir="auto"]').first
                await caption_locator.wait_for(state="visible", timeout=3000)
                post_description = await caption_locator.text_content()
                post_description = post_description.strip()
                print(f"[💬] Found post description: '{post_description[:50]}...'")
            except PlaywrightTimeoutError:
                print("[⚠️] Post description not found. Using generic comment prompt.")
            except Exception as e:
                print(f"[⚠️] Error getting post description: {e}. Using generic comment prompt.")

            # Pass post_description to the AI for more contextual comment
            comment = await generate_ai_response(prompt_type="comment", user_message=post_description)
            print(f"[💬] Preparing to comment: {comment}")
            
            comment_box_locators = [
                'textarea[aria-label*="Hozzászólás"]',
                'textarea[aria-label*="Comment"]',
                'textarea[placeholder*="Hozzászólás"]',
                'textarea[placeholder*="Comment"]',
                'div[aria-label*="Hozzászólás"]',
                'div[aria-label*="Comment"]',
                'div[role="textbox"]'
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
                await page.keyboard.press("Enter")
                print(f"[✅] Commented: {comment}")
                await page.wait_for_timeout(3000)
            else:
                print("[❌] Could not find an interactive comment box after trying all selectors.")
                await page.screenshot(path="comment_box_not_found.png")
        except Exception as e:
            print(f"[❌] Comment failed: {e}")
            await page.screenshot(path="comment_error.png")

        await page.wait_for_timeout(2000)
        await browser.close()

# --- Helper function to process individual message threads ---
async def process_message_thread(page, thread_button_locator, initial_inbox_url, is_request=False):
    user_group_name = "N/A"
    last_message_text = "N/A"
    timestamp = "N/A"
    status_initial = "N/A"
    chat_url = "N/A"
    current_status_after_action = "N/A"
    
    core_info_extracted = False

    try:
        # Extract initial details from the thread card
        name_element = thread_button_locator.locator(
            'span[dir="auto"] > span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft'
        ).first
        await name_element.wait_for(state="visible", timeout=500)
        user_group_name = (await name_element.text_content()).strip()

        message_preview_locator = thread_button_locator.locator(
            'div.x6s0dn4.x78zum5 div.html-div.xmix8c7 span[dir="auto"] > span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft'
        ).first
        await message_preview_locator.wait_for(state="visible", timeout=500)
        last_message_text = (await message_preview_locator.text_content()).strip()

        timestamp_element = thread_button_locator.locator('abbr[aria-label]').first
        await timestamp_element.wait_for(state="visible", timeout=500)
        timestamp = await timestamp_element.get_attribute('aria-label')
        
        core_info_extracted = True

        if not is_request:
            try:
                unread_indicator_locator = thread_button_locator.locator(
                    'span[data-visualcompletion="ignore"]:has-text("Unread")'
                ).first
                await unread_indicator_locator.wait_for(state="visible", timeout=200)
                if await unread_indicator_locator.is_visible():
                    status_initial = "UNREAD"
                else:
                    status_initial = "Read"
            except PlaywrightTimeoutError:
                status_initial = "Read"
            except Exception:
                status_initial = "Error checking unread"
        else:
            status_initial = "REQUEST"

        # --- Click to get URL and potentially respond/accept ---
        print(f"  [🌐] Clicking to open chat for '{user_group_name}'...")
        await thread_button_locator.click(timeout=5000)
        
        if is_request:
            try:
                accept_button_locator = page.locator('div[role="button"]:has-text("Elfogadás"), div[role="button"]:has-text("Accept")').first
                await accept_button_locator.wait_for(state="visible", timeout=5000)
                print("  [👍] Clicking 'Accept' request...")
                await accept_button_locator.click(timeout=5000)
                await page.wait_for_timeout(2000)
                current_status_after_action = "Accepted"
            except PlaywrightTimeoutError:
                print("  [❌] 'Accept' button not found or timed out. Could not accept request.")
                current_status_after_action = "Request (Accept Failed)"
                return None # Indicate failure
            except Exception as e:
                print(f"  [❌] Error accepting request: {e}")
                current_status_after_action = f"Request (Accept Error: {e})"
                return None

        await page.wait_for_url(lambda url_str: "direct/t/" in url_str, timeout=10000)
        chat_url = page.url
        print(f"  [🔗] Chat URL: {chat_url}")

        if status_initial == "UNREAD" or (is_request and current_status_after_action == "Accepted"):
            print(f"  [💬] Status requires reply. Attempting to reply to '{user_group_name}'...")
            try:
                ai_response = await generate_ai_response(
                    prompt_type="message_reply",
                    user_message=last_message_text,
                    sender_name=user_group_name
                )
                
                message_input_box_locator = page.locator(
                    'div[aria-label="Üzenet"][role="textbox"][contenteditable="true"], '
                    'div[aria-label="Message"][role="textbox"][contenteditable="true"]'
                ).first
                
                await message_input_box_locator.wait_for(state="visible", timeout=5000)
                
                await message_input_box_locator.fill(ai_response)
                await page.keyboard.press("Enter")
                print(f"  [✅] Replied: '{ai_response}' to '{user_group_name}'.")
                await page.wait_for_timeout(3000)
                current_status_after_action = "Replied (was " + status_initial + ")" if not is_request else "Accepted & Replied"
            except PlaywrightTimeoutError:
                print("  [❌] Message input box not found. Could not reply.")
                current_status_after_action = "Reply Failed (was " + status_initial + ")"
            except Exception as e:
                print(f"  [❌] Error replying: {e}")
                current_status_after_action = f"Reply Error (was {status_initial}): {e}"
        else:
            print(f"  [ℹ️] Chat '{user_group_name}' was already Read. No reply sent.")
            current_status_after_action = "Read (No Reply)"

        return {
            "User/Group": user_group_name,
            "Last Message": last_message_text,
            "Initial Status": status_initial,
            "Outcome Status": current_status_after_action,
            "Timestamp": timestamp,
            "Chat URL": chat_url
        }

    except PlaywrightTimeoutError as e:
        print(f"  [❌] Timed out processing thread '{user_group_name}' for URL/response: {e}")
        return None 
    except Exception as e:
        print(f"  [❌] Unexpected error processing thread '{user_group_name}': {e}")
        return None
    finally:
        # Crucial: Always navigate back to the inbox after processing a thread, regardless of errors.
        # This ensures the main loop can proceed to the next item reliably.
        if "direct/inbox" not in page.url:
            print(f"  [🔙] Navigating back to inbox (from {page.url})...")
            await page.goto(initial_inbox_url, timeout=10000)
            await page.wait_for_url(initial_inbox_url, timeout=10000)
            await page.wait_for_timeout(2000)


# === NEW MODE: LIST MESSAGES AND REPLY TO UNREAD (Includes Requests) ===
async def list_messages():
    print("[✉️] Launching bot to list Instagram messages...")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = await browser.new_page()
        await wait_until_logged_in(page)
        
        print("[🔎] Navigating to Instagram Direct Inbox...")
        initial_inbox_url = "https://www.instagram.com/direct/inbox/"
        await page.goto(initial_inbox_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        if "direct/inbox" not in page.url:
            print(f"[⚠️] Failed to navigate to inbox. Current URL: {page.url}")
            await page.screenshot(path="inbox_navigation_error.png")
            await browser.close()
            return

        print("[✅] Successfully navigated to Direct Inbox.")

        final_extracted_chat_data = [] # To store all processed chats (inbox and requests)

        # --- PROCESS MESSAGE REQUESTS FIRST ---
        print("\n--- Checking for Message Requests ---")
        # Selector for the request tab based on text content, more robust
        request_tab_xpath = '//span[contains(@dir, "auto") and (contains(text(), "Request") or contains(text(), "Kérelmek"))]'
        
        try:
            request_tab_locator = page.locator(request_tab_xpath).first
            # We don't need the regex match if we just check if it's visible and contains number.
            # If the element exists, click it. The number will be displayed on the page.
            await request_tab_locator.wait_for(state="visible", timeout=5000)
            request_text_on_tab = await request_tab_locator.text_content()

            # Click the requests tab
            print(f"[📬] Found message requests tab: '{request_text_on_tab}'. Clicking to view requests...")
            await request_tab_locator.click(timeout=5000)
            await page.wait_for_timeout(3000) # Wait for requests page to load
            
            # Now, identify and process individual request threads on the requests page
            request_thread_selector = 'div.x13dflua.x19991ni' # This is the same wrapper as regular chats
            
            # Scroll to ensure all requests are loaded if dynamic
            for _ in range(3): 
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

            # Get all request thread wrappers
            requests_to_process_wrappers = await page.locator(request_thread_selector).all()
            
            if requests_to_process_wrappers:
                print(f"[📋] Found {len(requests_to_process_wrappers)} message requests. Processing...")
                
                # To avoid stale element references when navigating in/out of chats:
                # 1. Collect identifiers for all requests that need processing.
                request_identifiers_to_process = []
                for req_wrapper_element in requests_to_process_wrappers:
                    req_button_locator = req_wrapper_element.locator('div[role="button"][tabindex="0"]').first
                    try:
                        name_el = req_button_locator.locator('span[dir="auto"] > span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft').first
                        msg_el = req_button_locator.locator('div.x6s0dn4.x78zum5 div.html-div.xmix8c7 span[dir="auto"] > span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft').first
                        ts_el = req_button_locator.locator('abbr[aria-label]').first
                        
                        await name_el.wait_for(state="visible", timeout=100) # Quick check
                        name = (await name_el.text_content()).strip()
                        message = (await msg_el.text_content()).strip()
                        timestamp = await ts_el.get_attribute('aria-label')
                        
                        request_identifiers_to_process.append({
                            "name": name,
                            "message": message,
                            "timestamp": timestamp
                        })
                    except PlaywrightTimeoutError:
                        pass # Skip if initial info not found
                    except Exception as e:
                        print(f"  [⚠️] Error collecting request identifier: {e}")

                if request_identifiers_to_process:
                    for k, req_data in enumerate(request_identifiers_to_process):
                        print(f"\n--- Attempting to process Request {k+1}: '{req_data['name']}' ---")
                        # Re-navigate to requests page for a fresh DOM before processing each request
                        # This handles cases where accepting one request might change the list.
                        await page.goto(initial_inbox_url, timeout=60000) # Go to main inbox
                        await page.wait_for_url(initial_inbox_url, timeout=10000)
                        await page.wait_for_timeout(2000)
                        await page.locator(request_tab_xpath).first.click(timeout=5000) # Re-click requests tab
                        await page.wait_for_timeout(3000)

                        # Re-locate the specific request button using XPath with text content
                        # This is the most critical part: robustly finding the *exact* thread
                        target_req_button_xpath = (
                            f'//div[contains(@class, "x13dflua") and contains(@class, "x19991ni")]'
                            f'//div[@role="button" and @tabindex="0"]'
                            f'[.//span[contains(text(), "{req_data["name"]}")]]' # Match name
                            f'[.//span[contains(text(), "{req_data["message"]}")]]' # Match message
                        )
                        target_req_button_locator = page.locator(target_req_button_xpath).first

                        try:
                            await target_req_button_locator.wait_for(state="visible", timeout=5000)
                            processed_data = await process_message_thread(page, target_req_button_locator, initial_inbox_url, is_request=True)
                            if processed_data:
                                final_extracted_chat_data.append(processed_data)
                                print(f"  [✅] Successfully processed message request {k+1}.")
                            else:
                                print(f"  [❌] Failed to fully process message request {k+1}. Skipping.")
                        except PlaywrightTimeoutError:
                            print(f"  [❌] Timed out re-locating request from '{req_data['name']}'. It might have been processed or moved. Skipping.")
                        except Exception as e:
                            print(f"  [❌] Unexpected error re-locating or processing request from '{req_data['name']}': {e}. Skipping.")
                else:
                    print("[ℹ️] No identifiable request threads found after initial scan despite tab count.")
            else:
                print("[ℹ️] Request tab found but has no visible requests to process.")
        except PlaywrightTimeoutError:
            print("[ℹ️] No 'Request' tab found within timeout. Assuming no pending requests.")
        except Exception as e:
            print(f"[❌] Error checking for message requests: {e}")
        
        # --- PROCESS REGULAR INBOX MESSAGES ---
        print("\n--- Checking for Regular Inbox Messages ---")
        outer_thread_wrapper_selector = 'div.x13dflua.x19991ni' 
        
        # Ensure we are back on main inbox before processing regular messages
        await page.goto(initial_inbox_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        await page.locator(outer_thread_wrapper_selector).first.wait_for(state="visible", timeout=10000)
        
        # Phase 1: Collect Identifiers for regular inbox threads
        all_regular_thread_identifiers_to_process = [] 
        seen_regular_identifiers_set = set()

        for _ in range(3): 
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
        
        current_thread_wrappers = await page.locator(outer_thread_wrapper_selector).all()
        print(f"[📋] Found {len(current_thread_wrappers)} potential regular message entries for initial scan.")

        for i, thread_wrapper_element in enumerate(current_thread_wrappers):
            thread_button_locator = thread_wrapper_element.locator('div[role="button"][tabindex="0"]').first

            user_group_name = "N/A"
            last_message_text = "N/A"
            timestamp = "N/A"
            status_during_scan = "N/A" 
            
            try:
                name_element = thread_button_locator.locator(
                    'span[dir="auto"] > span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft'
                ).first
                await name_element.wait_for(state="visible", timeout=100)
                user_group_name = (await name_element.text_content()).strip()

                message_preview_locator = thread_button_locator.locator(
                    'div.x6s0dn4.x78zum5 div.html-div.xmix8c7 span[dir="auto"] > span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft'
                ).first
                await message_preview_locator.wait_for(state="visible", timeout=100)
                last_message_text = (await message_preview_locator.text_content()).strip()

                timestamp_element = thread_button_locator.locator('abbr[aria-label]').first
                await timestamp_element.wait_for(state="visible", timeout=100)
                timestamp = await timestamp_element.get_attribute('aria-label')
                
                try:
                    unread_indicator_locator = thread_button_locator.locator(
                        'span[data-visualcompletion="ignore"]:has-text("Unread")'
                    ).first
                    await unread_indicator_locator.wait_for(state="visible", timeout=100) 
                    if await unread_indicator_locator.is_visible():
                        status_during_scan = "UNREAD"
                    else:
                        status_during_scan = "Read"
                except PlaywrightTimeoutError:
                    status_during_scan = "Read"
                except Exception as e:
                    status_during_scan = f"Error: {e}"

                chat_unique_key = (user_group_name, last_message_text, timestamp)
                
                if chat_unique_key not in seen_regular_identifiers_set:
                    all_regular_thread_identifiers_to_process.append({
                        "name": user_group_name,
                        "message": last_message_text,
                        "timestamp": timestamp,
                        "status_initial": status_during_scan
                    })
                    seen_regular_identifiers_set.add(chat_unique_key)
                    
            except PlaywrightTimeoutError:
                pass
            except Exception as e:
                print(f"  [⚠️] Error collecting identifier for regular thread {i+1}: {e}")
            
        if not all_regular_thread_identifiers_to_process:
            print("[ℹ️] No identifiable regular message threads found after initial scan.")
        else:
            print(f"[✅] Identified {len(all_regular_thread_identifiers_to_process)} unique regular chat threads to process.")

            # Phase 2: Process each regular inbox message
            for j, identifier_data in enumerate(all_regular_thread_identifiers_to_process):
                user_group_name = identifier_data['name']
                last_message_text = identifier_data['message']
                timestamp = identifier_data['timestamp']
                initial_status = identifier_data['status_initial']

                # Navigate back to inbox first for a fresh list of locators
                await page.goto(initial_inbox_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)

                # Re-locate the specific thread to click using XPath with text content
                target_thread_button_xpath = (
                    f'//div[contains(@class, "x13dflua") and contains(@class, "x19991ni")]'
                    f'//div[@role="button" and @tabindex="0"]'
                    f'[.//span[contains(text(), "{user_group_name}")]]'
                    f'[.//span[contains(text(), "{last_message_text}")]]'
                )
                target_thread_button_locator = page.locator(target_thread_button_xpath).first

                try:
                    await target_thread_button_locator.wait_for(state="visible", timeout=5000)
                    processed_data = await process_message_thread(page, target_thread_button_locator, initial_inbox_url, is_request=False)
                    if processed_data:
                        final_extracted_chat_data.append(processed_data)
                        print(f"  [✅] Processed regular message {j+1}.")
                    else:
                        print(f"  [❌] Failed to fully process regular message {j+1}. Skipping.")
                except PlaywrightTimeoutError:
                    print(f"  [❌] Timed out re-locating regular message '{user_group_name}'. It might have changed or been processed already. Skipping.")
                except Exception as e:
                    print(f"  [❌] Unexpected error re-locating or processing regular message '{user_group_name}': {e}. Skipping.")
        
        # --- Final Summary ---
        if final_extracted_chat_data:
            print("\n--- All Processed Chat Threads ---")
            for k, chat_data in enumerate(final_extracted_chat_data):
                print(f"\n--- Chat Thread {k+1} ---")
                print(f"User/Group: {chat_data['User/Group']}")
                print(f"Last Message: {chat_data['Last Message']}")
                print(f"Initial Status: {chat_data['Initial Status']}")
                print(f"Outcome Status: {chat_data['Outcome Status']}")
                print(f"Timestamp: {chat_data['Timestamp']}")
                print(f"Chat URL: {chat_data['Chat URL']}")
        else:
            print("[ℹ️] No active chat threads (including requests) with extractable content were found after scanning and processing.")


        await page.wait_for_timeout(2000)
        await browser.close()
        print("[✅] Message listing and processing complete.")

# === ENTRYPOINT ===
if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--manual":
        asyncio.run(manual_mode())
    elif len(sys.argv) == 2 and sys.argv[1] == "--messages":
        asyncio.run(list_messages())
    elif len(sys.argv) == 2 and sys.argv[1].startswith("https://www.instagram.com/"):
        post_url = sys.argv[1]
        asyncio.run(interact_with_post(post_url))
    else:
        print("Usage:")
        print("  Manual login mode: python instagram.py --manual")
        print("  List messages:     python instagram.py --messages")
        print("  Auto post mode:    python instagram.py <instagram_post_url>")
        sys.exit(1)
