# 📲 Social Media Like & Comment Tool

This bot automates liking and commenting on social media posts using **Playwright**. It's designed to work similarly for both **Facebook** and **Instagram**, letting you manually log in once for each, and then automate interactions with specific post URLs.

---

## ⚙️ How It Works

The `facebook.py` and `instagram.py` bots operate in two main modes:

### 🔐 Manual Login Mode (`--manual`)

This mode opens a browser window so you can **manually log in** to your Facebook or Instagram account. Once logged in and the window is closed, the bot saves session cookies and local storage to a dedicated folder:

- **Facebook:**  
  `./user_data/facebook_agent/session_storage.json`

- **Instagram:**  
  `./user_data/instagram_agent/session_storage.json`

✅ This prevents you from needing to log in again each time.

---

### 🤖 Automation Mode (with Post URL)

After a successful manual login, you can run the bot with a **specific post URL**. For both Facebook and Instagram, the bot will:

- Load your saved session.
- Navigate to the post URL.
- Wait a random delay (**30–60 seconds**) to mimic human behavior.
- Check if the post is already liked.
  - If not, it clicks the "Like" button.
- Locate the comment box and choose a random message from a list.
- Attempt to post the comment.
- Close the browser.

---

## 🧰 Requirements

Before running the bot, make sure you have:

- ✅ Python 3.7+
- ✅ Playwright
- ✅ Playwright browser binaries

---

### 📦 Installation Steps

1. **Clone the repo (if needed):**

   ```bash
   git clone <your_repository_url>
   cd <your_repository_name>
   ```

2. **Create a virtual environment (recommended):**

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install Playwright and browser binaries:**

   ```bash
   pip install playwright
   playwright install
   ```

---

## 🚀 How to Run

### 🔑 Step 1: Manual Login (Only Once Per Platform)

You only need to do this once for each platform. It saves your login session:

```bash
python3 facebook.py --manual
python3 instagram.py --manual
```

➡️ A browser window will open. Log in manually, then close the tab or window.

Example success message:
```
[✅] Session saved to ./user_data/facebook_agent/session_storage.json
```

---

### 🎯 Step 2: Automate Like + Comment

Once your session is saved, run the bot with a post URL:

#### ✅ Facebook Post Example

```bash
python3 facebook.py https://www.facebook.com/ExamplePage/posts/1234567890
```

#### ✅ Instagram Post Example

```bash
python3 instagram.py https://www.instagram.com/p/some_post_id_here/
```

---

## 🛠️ Troubleshooting & Tips

### 🧱 `Frame.is_visible()` Error

If you see:
```
Frame.is_visible() got an unexpected keyword argument 'timeout'
```

Run:

```bash
pip install --upgrade playwright
playwright install
```

---

### 🖱️ Clicking Wrong Element?

DOMs change often. If the bot clicks an image or wrong element:

- Adjust the **selectors** inside `facebook.py` or `instagram.py`.
- This script uses robust `aria-label`, `role`, and class-based selectors.

---

### 💬 Comment Box Not Found?

Update the list of selectors like:

```python
'textarea[aria-label*="Comment"]',
'textarea[placeholder*="Comment"]',
'div[role="textbox"]'
```

---

### 🎭 Headless Mode?

For debugging, the script uses:

```python
headless=False
```

To run invisibly (for performance), change to:

```python
headless=True
```

---

### ⏱️ Adjust Delays

To tweak the wait time between actions:

```python
MIN_DELAY = 30
MAX_DELAY = 60
```

Increase for more "human-like" behavior.

---

### 💡 Customize Comments

Edit the `COMMENT_OPTIONS` list:

```python
COMMENT_OPTIONS = ["🔥🔥🔥", "Love this!", "Amazing post!", "💯", "So good!"]
```

---

Happy Automating! 🤖💬🔥
