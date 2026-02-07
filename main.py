import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI

load_dotenv()

# 1. Setup Slack Credentials
bot_token = os.environ.get("SLACK_BOT_TOKEN")
app_token = os.environ.get("SLACK_APP_TOKEN")
gemini_key = os.environ.get("GEMINI_API_KEY")

if not all([bot_token, app_token, gemini_key]):
    raise ValueError("Missing environment variables. Check SLACK_BOT_TOKEN, SLACK_APP_TOKEN, and GEMINI_API_KEY.")

# 2. Initialize Gemini Client (using OpenAI compatibility layer)
client = OpenAI(
    api_key=gemini_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

app = App(token=bot_token)

@app.event("app_mention")
def handle_mention(body, say):
    event = body["event"]
    thread_ts = event.get("thread_ts", event["ts"])
    user_text = event.get("text") # This gets the message text

    try:
        # 3. Call Gemini to get a response
        # Note: We strip the bot's user ID from the text to get just the prompt
        response = client.chat.completions.create(
            model="gemini-2.5-flash", # Note: Changed to 1.5-flash as 2.5 isn't out yet!
            messages=[
                {"role": "system", "content": "You are a helpful Slack AI assistant."},
                {"role": "user", "content": user_text}
            ]
        )
        
        ai_response = response.choices[0].message.content

        # 4. Reply back in the thread
        say(text=ai_response, thread_ts=thread_ts)

    except Exception as e:
        print(f"Error calling Gemini: {e}")
        say(text="Sorry, I ran into an error processing that.", thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, app_token)
    handler.start()