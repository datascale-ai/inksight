# Configure API Key

This guide is intentionally written for **end users using the website**. It does not cover backend deployment or environment variables.

If your goal is simply to make your device or previews use your own model account, everything happens in **Profile**.

## 1. Correct place to configure keys

If you want to configure:

- text model provider
- text model name
- text API key
- image model provider
- image model name
- image API key

go to **Profile**, not the **Device Configuration** page.

![Profile page screenshot](/images/docs/profile-en-full.png)

This is the signed-in Profile page in the current build. It shows your account info, remaining free quota, and the AI configuration area.

Current product structure:

- **Device Configuration** manages device modes, preferences, sharing, and status
- **Profile** manages models, API keys, quota, and access mode

## 2. First decide whether you need your own key

Inside Profile, you currently have two options:

- **Use platform free quota**: best if you just want to try the product
- **Use your own model key (BYOK)**: best if you want to use your own provider, your own quota, or your own compatible API endpoint

If you only want a quick first experience, platform quota is enough.
If you already have DeepSeek, Alibaba DashScope, or another OpenAI-compatible service, choose **BYOK**.

## 3. How to fill in your own API key

After you click **Use your own model key (BYOK)**, the page expands into a form like this:

![BYOK form screenshot](/images/docs/profile-en-byok.png)

This section has two parts:

- **Text generation settings** for briefings, weather commentary, quotes, and other text-based modes
- **Image generation settings** for image modes such as `ARTWALL`

### 3.1 Text model settings

There are two common ways to configure text models:

- **Preset provider**
  - good for providers such as DeepSeek or Alibaba DashScope
  - choose the provider, choose the model, then paste your API key
- **Custom OpenAI-compatible**
  - good for third-party services that expose an OpenAI-style API
  - fill in the model name, API key, and Base URL

### 3.2 Image model settings

If you want to use image modes such as `ARTWALL`, continue with the image section:

- choose the image provider
- choose the image model
- paste the image API key

Even if you mainly use text modes today, it is worth filling this section once so image modes work later without another setup pass.

## 4. Recommended filling order

The easiest sequence is:

1. Open **Profile**
2. Switch to **BYOK**
3. Finish the **text model** section
4. Finish the **image model** section
5. Click **Save configuration**
6. Validate the result from **No-device Demo** or **Device Configuration**

After saving, the system prefers the settings stored in **Profile**.

## 5. How to verify it worked

Two quick checks:

- use **No-device Demo** to preview a text-based mode and confirm text generation works
- preview `ARTWALL` in **No-device Demo** or **Device Configuration** to confirm image generation works

If both text and image generation work, your setup is in good shape.

## 6. Common mistakes

- **You only filled the text key**
  - text modes may work, but image modes like `ARTWALL` will still fail
- **You selected OpenAI-compatible mode but left Base URL empty**
  - Base URL is required in that mode
- **You filled everything but forgot to save**
  - make sure you click **Save configuration**
- **You pasted the key under the wrong provider**
  - that usually shows up as an auth failure right away

## 7. Related docs

- Web configuration: [`config.md`](config.md)
- Website guide: [`website.md`](website.md)
- Local deployment: [`deploy.md`](deploy.md)
- FAQ: [`faq.md`](faq.md)
