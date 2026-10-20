import subprocess
import os
import signal
import sys
import logging
import shutil

class BotManager:
    def __init__(self):
        self.process = None
        self.log_file = "bot.log"
        # Проверяем, запущена ли система под Linux с systemd
        self.is_systemd = (sys.platform != "win32" and shutil.which("systemctl") is not None)

    def is_running(self):
        if self.is_systemd:
            try:
                res = subprocess.run(["systemctl", "is-active", "elina"], capture_output=True, text=True)
                return res.stdout.strip() == "active"
            except Exception as e:
                logging.error(f"Error checking systemctl: {e}")
        
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_status(self):
        if self.is_systemd:
            try:
                res = subprocess.run(["systemctl", "is-active", "elina"], capture_output=True, text=True)
                is_active = (res.stdout.strip() == "active")
                if is_active:
                    pid_res = subprocess.run(["systemctl", "show", "--property", "MainPID", "elina"], capture_output=True, text=True)
                    raw_pid = pid_res.stdout.strip().replace("MainPID=", "")
                    pid = raw_pid if raw_pid and raw_pid != "0" else "systemd"
                    return "running", pid
                return "stopped", None
            except Exception as e:
                logging.error(f"Error getting systemd status: {e}")

        if self.is_running():
            return "running", self.process.pid
        return "stopped", None

    def start_bot(self):
        if self.is_systemd:
            res = subprocess.run(["systemctl", "start", "elina"], capture_output=True, text=True)
            return (res.returncode == 0), (res.stderr.strip() or "Started via systemctl")
        
        if self.is_running():
            return False, "Bot is already running."

        try:
            cmd = [sys.executable, "-m", "bot.main"]
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
        if self.is_systemd:
            res = subprocess.run(["systemctl", "stop", "elina"], capture_output=True, text=True)
            return (res.returncode == 0), (res.stderr.strip() or "Stopped via systemctl")

        if not self.is_running():
            return False, "Bot is not running."

        try:
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

    def restart_bot(self):
        if self.is_systemd:
            res = subprocess.run(["systemctl", "restart", "elina"], capture_output=True, text=True)
            return (res.returncode == 0), (res.stderr.strip() or "Restarted via systemctl")
        
        self.stop_bot()
        return self.start_bot()

    def get_logs(self, lines=100):
        if self.is_systemd:
            try:
                res = subprocess.run(["journalctl", "-u", "elina", "-n", str(lines), "--no-pager"], capture_output=True, text=True)
                if res.stdout:
                    return res.stdout
            except Exception as e:
                return f"Error reading systemd journal: {e}"

        if not os.path.exists(self.log_file):
            return "Лог-файл пока не создан (бот еще не запускался локально)."
        
        try:
            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.readlines()
                return "".join(content[-lines:])
        except Exception as e:
            return f"Error reading logs: {e}"

bot_manager = BotManager()
