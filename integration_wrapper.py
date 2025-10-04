import requests
import json
import os
from dotenv import load_dotenv
import sys
from datetime import datetime # <-- FIXED: Added the missing import

class TaskReviewerClient:
    """A client to interact with the Task Reviewer Agent API."""
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        # Base headers for JSON requests
        self.json_headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        # Headers for other requests (e.g., file uploads)
        self.base_headers = {"X-API-Key": self.api_key}

    def _request(self, method: str, endpoint: str, data: dict = None, files: dict = None) -> dict:
        """Helper method to handle different types of requests."""
        url = f"{self.base_url}/{endpoint}"
        headers = self.json_headers if data else self.base_headers
        
        try:
            if method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, files=files)
            elif method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            else:
                raise ValueError("Unsupported HTTP method")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"🔴 HTTP Error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"🔴 Request failed: {e}")
        return None

    # --- Review Trigger Functions ---

    def trigger_review(self, task_id: str, submission_link: str) -> dict:
        """(Primary) Triggers a review by submitting a link."""
        payload = {"submission_link": submission_link}
        return self._request('POST', f"review/link/{task_id}", data=payload)

    def trigger_review_with_text(self, task_id: str, submission_text: str) -> dict:
        """Triggers a review by submitting raw text."""
        payload = {"submission_text": submission_text}
        return self._request('POST', f"review/text/{task_id}", data=payload)

    def trigger_review_with_file(self, task_id: str, file_path: str) -> dict:
        """Triggers a review by uploading a file."""
        if not os.path.exists(file_path):
            print(f"🔴 File not found at path: {file_path}")
            return None
        with open(file_path, 'rb') as f:
            files = {'submission_file': (os.path.basename(file_path), f)}
            return self._request('POST', f"review/file/{task_id}", files=files)

    # --- Other Functions (get_feedback, mark_done, etc.) ---
    
    def get_feedback(self, review_id: str) -> dict:
        """Fetches the full review details."""
        return self._request('GET', f"review/{review_id}")

    def mark_done(self, review_id: str) -> dict:
        """Marks a task as fully completed."""
        return self._request('POST', f"mark-done/{review_id}")

    def create_task_definition(self, task_id: str, title: str, description: str) -> dict:
        """Creates the initial task definition."""
        payload = {"task_id": task_id, "title": title, "description": description}
        return self._request('POST', "tasks", data=payload)

    def send_feedback_with_dhi(self, review_id: str, sentiment: str, dhi_scores: dict) -> dict:
        """Sends admin feedback with DHI scores."""
        payload = {"sentiment": sentiment, "dhi_scores": dhi_scores}
        return self._request('POST', f"feedback/{review_id}", data=payload)

    def generate_next_task(self, review_id: str) -> dict:
        """Generates the next task after feedback."""
        return self._request('POST', f"generate-next-task/{review_id}")


# --- Example Usage ---
if __name__ == '__main__':
    load_dotenv()
    AGENT_URL = "http://127.0.0.1:8000"
    API_KEY = os.getenv("AGENT_API_KEY", "default-secret-key")
    
    client = TaskReviewerClient(base_url=AGENT_URL, api_key=API_KEY)

    # Create a test file for the file upload example
    with open("temp_submission.py", "w") as f:
        f.write("def my_function():\n    return 'hello from file'")

    # --- Choose ONE of the examples below to run by uncommenting it ---

    # Example 1: Submit via Link (Primary Method)
    print("\n--- Testing Submission via Link ---")
    task_id_link = f"cli-task-link-{datetime.now().strftime('%H%M%S')}"
    client.create_task_definition(task_id_link, "Link Task", "A test task for link submission.")
    link = "https://gist.githubusercontent.com/siddhesh-suresh-test/912c75f0a0e5c9a0c6a583e74a625a72/raw/4c0c4519967272847c2e0b115ba923380442e61c/test_submission.py"
    review_result = client.trigger_review(task_id_link, submission_link=link)
    if review_result:
        print(json.dumps(review_result, indent=2))

    # Example 2: Submit via Text
    # print("\n--- Testing Submission via Text ---")
    # task_id_text = f"cli-task-text-{datetime.now().strftime('%H%M%S')}"
    # client.create_task_definition(task_id_text, "Text Task", "A test task for text submission.")
    # review_result = client.trigger_review_with_text(task_id_text, "def hello_world(): return 'hello'")
    # if review_result:
    #     print(json.dumps(review_result, indent=2))

    # Example 3: Submit via File
    # print("\n--- Testing Submission via File ---")
    # task_id_file = f"cli-task-file-{datetime.now().strftime('%H%M%S')}"
    # client.create_task_definition(task_id_file, "File Task", "A test task for file submission.")
    # review_result = client.trigger_review_with_file(task_id_file, "temp_submission.py")
    # if review_result:
    #     print(json.dumps(review_result, indent=2))

    # Clean up the created test file
    os.remove("temp_submission.py")
