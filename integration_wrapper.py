import requests
import json
import os
from dotenv import load_dotenv
import sys

class TaskReviewerClient:
    """A client to interact with the Task Reviewer Agent API."""
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Helper method to handle GET and POST requests."""
        url = f"{self.base_url}/{endpoint}"
        try:
            if method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data if data else {})
            elif method.upper() == 'GET':
                response = requests.get(url, headers=self.headers)
            else:
                raise ValueError("Unsupported HTTP method")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"🔴 HTTP Error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"🔴 Request failed: {e}")
        return None

    # --- Functions required by the Task 3 PDF ---

    def trigger_review(self, task_id: str, submission_link: str) -> dict:
        """Triggers a review by submitting a link to the agent."""
        payload = {"submission_link": submission_link}
        return self._request('POST', f"review/link/{task_id}", data=payload)

    def get_feedback(self, review_id: str) -> dict:
        """Fetches the full review details, including scores and feedback."""
        return self._request('GET', f"review/{review_id}")

    def mark_done(self, review_id: str) -> dict:
        """Marks a task as fully completed after review and feedback."""
        return self._request('POST', f"mark-done/{review_id}")

    # --- Other Helper Functions ---
    
    def create_task_definition(self, task_id: str, title: str, description: str) -> dict:
        """Creates the initial task definition in the agent's database."""
        payload = {"task_id": task_id, "title": title, "description": description}
        return self._request('POST', "tasks", data=payload)

    def send_feedback_with_dhi(self, review_id: str, sentiment: str, dhi_scores: dict) -> dict:
        """Sends admin feedback, including DHI scores, to unlock the workflow."""
        payload = {"sentiment": sentiment, "dhi_scores": dhi_scores}
        return self._request('POST', f"feedback/{review_id}", data=payload)

    def generate_next_task(self, review_id: str) -> dict:
        """Generates the next task after a successful review and feedback."""
        return self._request('POST', f"generate-next-task/{review_id}")


# --- Example End-to-End Workflow ---
if __name__ == '__main__':
    load_dotenv()
    AGENT_URL = "http://127.0.0.1:8000"
    API_KEY = os.getenv("AGENT_API_KEY", "default-secret-key")
    
    # Use a dynamic task_id for each run to avoid conflicts
    from datetime import datetime
    task_id_from_command = f"cli-task-{datetime.now().strftime('%H%M%S')}"
    
    print(f"✅ Using Task ID: {task_id_from_command}")
    client = TaskReviewerClient(base_url=AGENT_URL, api_key=API_KEY)

    # 1. Create the task definition
    print("\n--- 1. Creating task definition... ---")
    task_data = client.create_task_definition(
        task_id=task_id_from_command, 
        title="Create a simple Python function", 
        description="Write a function that returns the string 'hello'."
    )
    if not task_data: sys.exit(1)
    print(json.dumps(task_data, indent=2))

    # 2. Trigger the review
    print("\n--- 2. Submitting for review... ---")
    # This must be a link to a raw file, like a GitHub Gist's "Raw" link.
    link = "https://gist.githubusercontent.com/siddhesh-suresh-test/912c75f0a0e5c9a0c6a583e74a625a72/raw/4c0c4519967272847c2e0b115ba923380442e61c/test_submission.py"
    review_result = client.trigger_review(task_id_from_command, submission_link=link)
    if not review_result: sys.exit(1)
    print("✅ Initial review received. Status is 'pending_feedback'.")
    review_id = review_result["review_id"]
    
    # 3. (Pre-feedback) Try to generate the next task - THIS SHOULD FAIL
    print(f"\n--- 3. Trying to generate next task for review {review_id} (should be locked)... ---")
    client.generate_next_task(review_id) # Expected to print an HTTP 423 Error

    # 4. Send feedback with DHI scores to unlock the workflow
    print(f"\n--- 4. Sending feedback for review {review_id} to unlock... ---")
    dhi_payload = {"dignity": 8, "honesty": 9, "integrity": 8}
    feedback_response = client.send_feedback_with_dhi(review_id, "up", dhi_payload)
    if not feedback_response: sys.exit(1)
    print("✅ Feedback sent. Status is now 'feedback_provided'.")

    # 5. Generate the next task - THIS SHOULD SUCCEED
    print(f"\n--- 5. Generating next task for review {review_id} (should succeed)... ---")
    next_task_response = client.generate_next_task(review_id)
    if not next_task_response: sys.exit(1)
    print(json.dumps(next_task_response, indent=2))

    # 6. Get the final, complete review data
    print(f"\n--- 6. Fetching final review record for review {review_id}... ---")
    final_record = client.get_feedback(review_id)
    if not final_record: sys.exit(1)
    print(json.dumps(final_record, indent=2))

    # 7. Mark the task as done
    print(f"\n--- 7. Marking review {review_id} as complete... ---")
    done_response = client.mark_done(review_id)
    if not done_response: sys.exit(1)
    print(json.dumps(done_response, indent=2))