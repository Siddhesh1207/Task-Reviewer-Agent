import requests
import json
import os
from dotenv import load_dotenv
import sys

class TaskReviewerClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def _post(self, endpoint: str, data: dict = None, files: dict = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        headers = self.headers.copy()
        if files: del headers["Content-Type"]
        try:
            response = requests.post(url, headers=headers, json=data, files=files)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        return None

    def create_task(self, task_id: str, title: str, description: str) -> dict:
        payload = {"task_id": task_id, "title": title, "description": description}
        return self._post("tasks", data=payload)

    def trigger_review_with_text(self, task_id: str, submission_text: str) -> dict:
        payload = {"submission_text": submission_text}
        return self._post(f"full-review-text/{task_id}", data=payload)
    
    def send_feedback(self, review_id: str, sentiment: str) -> dict:
        payload = {"sentiment": sentiment}
        return self._post(f"feedback/{review_id}", data=payload)

    # <-- NEW: A function to call the new endpoint -->
    def generate_next_task(self, review_id: str) -> dict:
        """Generates the next task after a successful review and feedback."""
        return self._post(f"generate-next-task/{review_id}")

# --- vvv The example usage is updated to test the new function vvv ---
if __name__ == '__main__':
    load_dotenv()
    if len(sys.argv) < 2:
        print("🔴 ERROR: You must provide a Task ID.\n   Usage: python wrapper.py <your-task-id>")
        sys.exit(1)
        
    task_id_from_command = sys.argv[1]
    print(f"✅ Using Task ID: {task_id_from_command}")
    
    AGENT_URL = "http://127.0.0.1:8000"
    API_KEY = os.getenv("AGENT_API_KEY", "default-secret-key")
    
    client = TaskReviewerClient(base_url=AGENT_URL, api_key=API_KEY)

    print("\n--- Creating task... ---")
    task_data = client.create_task(task_id=task_id_from_command, title="Dynamic Task", description="A test task.")
    print(json.dumps(task_data, indent=2))

    if task_data and task_data.get("status") == "success":
        print("\n--- Submitting for review... ---")
        review_result = client.trigger_review_with_text(task_id_from_command, "def test_func(): return 1")
        print(json.dumps(review_result, indent=2))

        if review_result and "review_id" in review_result:
            review_id = review_result["review_id"]
            
            print(f"\n--- Sending 'up' feedback for review_id: {review_id} ---")
            feedback_response = client.send_feedback(review_id, "up")
            print(json.dumps(feedback_response, indent=2))
            
            if feedback_response and feedback_response.get("status") == "success":
                # <-- NEW: Test the final step in the workflow -->
                print(f"\n--- Generating next task for review_id: {review_id} ---")
                next_task_response = client.generate_next_task(review_id)
                print(json.dumps(next_task_response, indent=2))