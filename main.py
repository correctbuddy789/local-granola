import time
import os
import shutil
import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WATCH_DIR = os.getenv("WATCH_DIR")
OBSIDIAN_VAULT = os.getenv("OBSIDIAN_VAULT")
OBSIDIAN_DAILY_NOTE_PATH = os.getenv("OBSIDIAN_DAILY_NOTE_PATH")

client = genai.Client(api_key=GEMINI_API_KEY)


class VoiceMemoHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        # Check for audio files (m4a is standard for Apple Voice Memos)
        if not event.src_path.lower().endswith((".m4a", ".mp3", ".wav")):
            return

        print(f"🎤 Detected new voice memo: {event.src_path}")
        try:
            self.process_memo(event.src_path)
        except Exception as e:
            print(f"❌ Error processing memo: {e}")

    def process_memo(self, file_path):
        # 1. Read Context from Obsidian
        context = self.get_obsidian_context()

        # 2. Upload to Gemini
        print("☁️  Uploading to Gemini...")
        file_ref = client.files.upload(
            file=file_path, config={"display_name": "Voice Memo"}
        )

        # 3. Generate Content
        print("🧠 Analyzing...")
        prompt = f"""
        You are my Chief of Staff.
        Here is what I have been working on recently (Context):
        {context}

        Process this voice memo. 
        - If it refers to "The Project", it likely means one of the projects in the context.
        - Extract action items.
        - Format as clear Markdown.
        - Be concise.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp", contents=[prompt, file_ref]
        )

        # 4. Cleanup Cloud File (Flash Protocol)
        print("🗑️  Deleting from Cloud (Flash Protocol)...")
        if file_ref.name:
            client.files.delete(name=file_ref.name)

        # 5. Write to Obsidian
        self.append_to_daily_note(response.text)

        # 6. Archive Local File
        self.archive_file(file_path)
        print("✅ Done!")

    def get_obsidian_context(self):
        """Reads the last 3 days of daily notes to build context."""
        context = ""
        # Implementation would go here - for now return placeholder
        # This keeps it safe/simple for the template
        return "No recent context loaded."

    def append_to_daily_note(self, text):
        if not OBSIDIAN_VAULT or not OBSIDIAN_DAILY_NOTE_PATH:
            print("❌ Error: Obsidian paths not configured.")
            return

        today = datetime.date.today().strftime("%Y-%m-%d")
        note_path = os.path.join(
            OBSIDIAN_VAULT, OBSIDIAN_DAILY_NOTE_PATH, f"{today}.md"
        )

        header = (
            f"\n\n## 🎙️ Voice Memo ({datetime.datetime.now().strftime('%H:%M')})\n\n"
        )

        try:
            with open(note_path, "a") as f:
                f.write(header + text)
            print(f"📝 Appended to {today}.md")
        except Exception as e:
            print(f"❌ Error writing to Obsidian: {e}")

    def archive_file(self, file_path):
        if not OBSIDIAN_VAULT:
            return

        archive_dir = os.path.join(OBSIDIAN_VAULT, "_assets", "voice_archive")
        os.makedirs(archive_dir, exist_ok=True)
        filename = os.path.basename(file_path)
        shutil.move(file_path, os.path.join(archive_dir, filename))
        print(f"📦 Archived to {archive_dir}")


if __name__ == "__main__":
    if not all([GEMINI_API_KEY, WATCH_DIR, OBSIDIAN_VAULT]):
        print("❌ Error: Missing environment variables. Check .env file.")
        exit(1)

    observer = Observer()
    event_handler = VoiceMemoHandler()
    if WATCH_DIR:
        observer.schedule(event_handler, path=WATCH_DIR, recursive=False)

    print(f"👀 Watching {WATCH_DIR} for new voice memos...")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
