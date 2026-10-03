# [START OF SECTION: API_KEY]

### 🔑 How to Get and Set a Google API Key

An API key is your personal free access key to the Google Gemini neural network. The bot operates on a **BYOK (Bring Your Own Key)** model: requests are sent directly to Google on your behalf, and the bot encrypts and securely stores your key in the database without ever sharing it with third parties.

#### ❗ Important Note for Users from Restricted Regions

Access to Google AI Studio may be restricted depending on your geographical location. If you see a regional unavailability error when following the links below:
* **Use a VPN or proxy service** or dedicated browser extensions (Chrome, Firefox, etc.).
* Recommended locations: United States, European countries (Germany, Netherlands, etc.).
* Once activated, refresh the Google AI Studio page. The bot server itself runs unrestricted — VPN is only required once during key generation in your browser.

#### Step-by-Step Instructions

1. **Go to Google AI Studio:**
   Navigate to [https://aistudio.google.com/](https://aistudio.google.com/) and sign in with your Google account.

2. **Navigate to API Key section:**
   In the left sidebar, click **"Get API key"** or use the direct link:
   👉 [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)

3. **Create the Key:**
   Click the blue button **"Create API key"** (or "Create API key in new project").

   ![Create key button](https://i.ibb.co/hJm9HHhM/Screenshot-of-Chat-Google-AI-Studio.jpg)

4. **Copy the Key:**
   In the dialog window, click the copy icon next to your new key (starts with `AIzaSy...`).

   ![Copy key](https://i.ibb.co/Kc0cbTmL/Screenshot-of-Get-API-key-Google-AI-Studio.jpg)

5. **Set the Key in the Bot:**
   You can set your key in any of the following ways:
   * **Fastest way:** simply paste and send the key directly into the chat. The bot instantly deletes your message for security, encrypts the key, and saves it to your profile.
   * **Via command:** send the `/set_api_key` command and enter your key.
   * **Via settings menu:** open `/settings` (or the "⚙️ Settings" button) ➔ click "🔑 Manage API Key".

Once verified, the bot will notify you and all capabilities will be instantly unlocked!

# [END OF SECTION: API_KEY]

---

# [START OF SECTION: FEATURES]

### 🚀 Bot Capabilities and Tooling

MyGemini is a full-featured intelligent assistant powered by state-of-the-art Google Gemini models.

#### 🧠 Real-time Streaming Chat
* Responses appear incrementally in real time, word by word, without long waiting periods.
* A **[⏹️ Stop]** button is available during generation, allowing you to abort output at any moment.
* Context headers and HUD lines display response time and exact token usage (e.g., `⚡ 4.1s • 📊 1790 tokens`).

#### ⚡ Quick Actions under Responses
Interactive buttons under completed answers:
* **🔄 Retry:** Regenerate the model's response with the same prompt.
* **↩️ Undo turn:** Cancel the last conversation step (removes the last response and user prompt, rolling back context).
* **🐍 To Sandbox:** Jump directly into the isolated Python sandbox for computational tasks.
* **📥 Export .md:** Download the entire conversation as a clean GitHub Markdown file (`dialog_X.md`).

#### 🐍 Isolated Python Sandbox (Code Execution)
* Physical code execution within a secure Google cloud environment.
* Delivers **100% computational accuracy** with zero hallucinations: factorials, complex formulas, combinatorics, exact letter and word counts, pattern matching, data filtering.
* **Two ways to use:**
  1. Global toggle in `⚙️ Settings` (sandbox is always available to the model when calculations are needed).
  2. Dedicated isolated mode via `[🐍 To Sandbox]` button — clean slate execution without prior dialogue interference, saving verified results back to dialogue history.

#### 🌐 Real-Time Google Search Grounding
* Toggle live web search in `⚙️ Settings ➔ 🌐 Google Search`.
* Ground responses in up-to-date internet data: breaking world news, currency rates, sports scores, and official documentation.

#### 🧠 Configurable Thinking Budget
* For Gemini 2.5/3 thinking models, configure reasoning depth:
  * **⚡ Instant (0):** Maximum speed without expanded reasoning.
  * **⚖️ Balanced (1024 tokens):** Optimal balance between speed and analytical depth (default).
  * **🔬 Deep Analysis (4096 tokens):** Maximum logical depth for intricate code and complex research.

#### 🖼️ Multimodal Image Analysis
* Send photos or screenshots to the bot.
* Add captions with your prompt (e.g., "Extract text from this image", "Solve the whiteboard problem", "List ingredients").

#### 🎙️ Voice Notes Support
* Send voice messages — the bot natively processes your speech, grasps intent, and generates a structured reply.

#### 🗂️ Dialogue Management (`/dialogs`)
* Create unlimited independent conversation threads (e.g., "Work", "Coding", "Study").
* Contexts remain strictly isolated.
* Easily switch, rename, delete, and export dialogues to `.md`.

#### 📜 History Calendar (`/history`)
* Interactive calendar with monthly navigation.
* Review all messages in the active dialogue for any selected date in expandable blockquotes.

#### 📊 Usage & Cost Statistics (`/usage`)
* Detailed tracking of prompt and completion tokens for today and the current month.
* Automatic USD cost estimation based on official Google API pricing.

#### 👤 Personal Account (`/account`)
* View your profile, message count, user tier, API key status, and topic analytics.

#### 🇷🇺/🇬🇧 Quick Translator (`/translate`)
* Fast translation tool for major world languages.

#### 📋 Complete Command Reference
* `/start` — Restart bot and initialize session
* `/help` — Quick command reference
* `/help_guide` (or `/guide`) — Full user manual
* `/apikey_info` (or `/key_info`) — Instructions on getting a Google API key
* `/set_api_key` — Set or update API key
* `/settings` — Configure models, personas, and features
* `/dialogs` — Dialogue management menu
* `/history` — View conversation history by date
* `/usage` — Token usage and cost statistics
* `/translate` — Built-in text translator
* `/account` (or `/profile`) — Personal account overview
* `/reset` — Reset context in the active dialogue
* `/feedback` — Send message or feedback to developers

# [END OF SECTION: FEATURES]

---

# [START OF SECTION: SETTINGS]

### ⚙️ Settings Menu (`/settings`)

Fine-tune MyGemini to match your workflow.

#### 🧠 Gemini Model Selection
* **gemini-2.5-flash:** Flagship fast model with tool use, thinking, and multimodal support (default).
* **gemini-2.5-pro:** Most capable model for advanced reasoning, complex code refactoring, and deep analysis.
* **gemini-2.5-flash-lite:** Ultra-fast model with automatic quota fallback on 429 errors.
* **gemini-3.1-flash-lite / gemini-3-flash / gemini-3-pro:** Next-generation model family.
* **gemini-1.5-flash / gemini-1.5-pro:** Established previous-generation models for backward compatibility.

#### 🎭 Assistant Persona
Selecting a specialized persona tailors the bot's expertise and tone:
* **🤖 Default Assistant** — General-purpose daily assistant.
* **🐍 Senior Python Developer** — Architecture, clean code, asyncio, and refactoring.
* **📊 Data Scientist & ML** — Data analysis, statistics, and machine learning models.
* **✍️ Expert Copywriter** — Engaging prose, copywriting, and clear writing.
* **💼 Business Consultant** — Strategy, financial models, SWOT analysis, and marketing.
* **🧠 Learning Mentor** — Step-by-step Feynman technique explanations.

#### 👔 Communication Style
*(Applies when "Default Assistant" persona is chosen)*
* **Formal:** Professional, academic tone.
* **Informal:** Friendly, casual language.
* **Concise:** Bullet points, no fluff.
* **Detailed:** Thorough explanations with examples.

#### 💬 Context Header Style
* **Blockquote:** Expandable Telegram quote showing dialogue, persona, and model.
* **Compact:** Single-line header (`💬 Dialogue • ⚡ Model`).
* **Hidden:** Clean output with no header.

#### 📄 Message Format
* **Rich:** Full formatting with HUD metrics and quick action buttons.
* **Plain:** Minimalist text output.

#### 🧠 Thinking Budget
* Adjust reasoning tokens (0, 1024, or 4096 tokens).

#### 🐍 Python Sandbox
* Toggle `🟢 On` / `🔴 Off`. Enables the model to physically execute Python code in real time.

#### 🌐 Google Search
* Toggle `🟢 On` / `🔴 Off`. Enables real-time web search grounding.

#### 🌐 Interface Language
* Switch UI buttons and system messages between Russian (`ru`) and English (`en`).

#### 🔑 Manage API Key
* Check current key status, validate, or safely replace your key.

# [END OF SECTION: SETTINGS]