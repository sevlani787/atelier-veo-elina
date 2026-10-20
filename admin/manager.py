import subprocess
import os
import signal
import sys
import logging

class BotManager:
    def __init__(self):
        self.process = None
        self.log_file = "bot.log"

    def start_bot(self):
        if self.is_running():
            return False, "Bot is already running."

        try:
            # Construct the command to run the bot
            # We use sys.executable to ensure we use the same python interpreter
            cmd = [sys.executable, "-m", "bot.main"]
            
            # Start the process and redirect output to a log file
            with open(self.log_file, "a", encoding="utf-8") as f:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=f,
                    stderr=f,
                    env=os.environ.copy(),
                    cwd=os.getcwd()
                )
            logging.info(f"Bot started with PID: {self.process.pid}")
            return True, "Bot started successfully."
        except Exception as e:
            logging.error(f"Failed to start bot: {e}")
            return False, str(e)

    def stop_bot(self):
        if not self.is_running():
            return False, "Bot is not running."

        try:
            # On Windows, we need a special way to terminate
            if sys.platform == "win32":
                self.process.terminate()
            else:
                os.kill(self.process.pid, signal.SIGTERM)
            
            self.process.wait(timeout=5)
            self.process = None
            return True, "Bot stopped successfully."
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process = None
            return True, "Bot killed after timeout."
        except Exception as e:
            logging.error(f"Failed to stop bot: {e}")
            return False, str(e)

    def is_running(self):
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_status(self):
        if self.is_running():
            return "running", self.process.pid
        return "stopped", None

    def get_logs(self, lines=50):
        if not os.path.exists(self.log_file):
            return "Log file not found."
        
        try:
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.readlines()
                return "".join(content[-lines:])
        except Exception as e:
            return f"Error reading logs: {e}"

# Singleton instance
bot_manager = BotManager()
