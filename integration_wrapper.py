import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime

class TaskReviewerClient:
    """A client to interact with the role-based Task Reviewer Agent API."""
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.json_headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
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

    # --- Authentication ---
    def admin_login(self, password: str) -> dict:
        """Authenticates as an admin."""
        payload = {"password": password}
        return self._request('POST', "auth/admin", data=payload)

    # --- Admin Functions ---
    def create_task_definition(self, task_id: str, title: str, description: str) -> dict:
        """Creates the initial task definition."""
        payload = {"task_id": task_id, "title": title, "description": description}
        return self._request('POST', "tasks", data=payload)

    def send_feedback_with_dhi(self, review_id: str, sentiment: str, dhi_scores: dict) -> dict:
        """Sends admin feedback with DHI scores."""
        payload = {"sentiment": sentiment, "dhi_scores": dhi_scores}
        return self._request('POST', f"feedback/{review_id}", data=payload)
        
    def get_pending_reviews(self) -> list:
        """(Admin) Fetches all reviews with status 'pending_feedback'."""
        return self._request('GET', "admin/pending-reviews")

    # --- User Functions ---
    def trigger_review_with_text(self, task_id: str, username: str, submission_text: str) -> dict:
        """(User) Triggers a review by submitting raw text."""
        payload = {"submission_text": submission_text}
        return self._request('POST', f"review/text/{task_id}/{username}", data=payload)

    def trigger_review_with_file(self, task_id: str, username: str, file_path: str) -> dict:
        """(User) Triggers a review by uploading a file."""
        if not os.path.exists(file_path):
            print(f"🔴 File not found at path: {file_path}")
            return None
        with open(file_path, 'rb') as f:
            files = {'submission_file': (os.path.basename(file_path), f)}
            # Note: For file uploads, we don't send a JSON payload, so 'data' is None
            return self._request('POST', f"review/file/{task_id}/{username}", files=files)

    def trigger_review_with_link(self, task_id: str, username: str, submission_link: str) -> dict:
        """(User) Triggers a review by submitting a link."""
        payload = {"submission_link": submission_link}
        return self._request('POST', f"review/link/{task_id}/{username}", data=payload)

    def generate_next_task(self, review_id: str) -> dict:
        """(User) Generates the next task after feedback has been provided."""
        return self._request('POST', f"generate-next-task/{review_id}")
        
    def get_user_reviews(self, username: str) -> list:
        """(User) Fetches all review submissions for a specific user."""
        return self._request('GET', f"user/{username}/reviews")

    # --- General Data Retrieval ---
    def get_all_tasks(self) -> list:
        """Fetches all available task definitions."""
        return self._request('GET', "tasks/all")

    def get_review_details(self, review_id: str) -> dict:
        """Fetches the full details for a specific review."""
        return self._request('GET', f"review/{review_id}")


# --- Example Usage ---
if __name__ == '__main__':
    load_dotenv()
    AGENT_URL = "http://127.0.0.1:8000"
    API_KEY = os.getenv("AGENT_API_KEY")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

    if not all([API_KEY, ADMIN_PASSWORD]):
        print("🔴 ERROR: AGENT_API_KEY and ADMIN_PASSWORD must be set in your .env file.")
        exit()
        
    client = TaskReviewerClient(base_url=AGENT_URL, api_key=API_KEY)

    print("--- 🚀 Kicking off a full Admin-User workflow simulation ---")

    # 1. ADMIN: Authenticate
    print("\n[1. ADMIN] Authenticating...")
    auth_result = client.admin_login(ADMIN_PASSWORD)
    if not auth_result:
        print("🔴 Admin login failed. Halting simulation.")
        exit()
    print("✅ Admin authenticated successfully.")

    # 2. ADMIN: Create a new task
    print("\n[2. ADMIN] Creating a new task definition...")
    task_id = f"cli-task-{datetime.now().strftime('%H%M%S')}"
    task_created = client.create_task_definition(
        task_id,
        "Refactor for Efficiency",
        "Take the provided Python function and refactor it to be more memory-efficient."
    )
    if task_created:
        print(f"✅ Task '{task_id}' created.")

    # 3. USER: A user named 'dev_01' submits their work for the task
    print("\n[3. USER] Submitting a task review as user 'dev_01'...")
    username = "dev_01"
    submission_text = "def efficient_function(data):\n    return [x * 2 for x in data] # Using a list comprehension"
    review_result = client.trigger_review_with_text(task_id, username, submission_text)
    if not review_result:
        print("🔴 Failed to trigger review. Halting simulation.")
        exit()
    
    review_id = review_result.get("review_id")
    print(f"✅ Submission successful! Review ID is: {review_id}")
    print("🤖 AI Feedback Note:", review_result.get("feedback_note"))

    # 4. ADMIN: Check for pending reviews and provide DHI feedback
    print("\n[4. ADMIN] Fetching pending reviews...")
    pending_reviews = client.get_pending_reviews()
    if pending_reviews and any(r['review_id'] == review_id for r in pending_reviews):
        print(f"✅ Found pending review {review_id}. Providing DHI feedback...")
        dhi_payload = {"dignity": 8, "honesty": 9, "integrity": 10}
        feedback_result = client.send_feedback_with_dhi(review_id, "up", dhi_payload)
        if feedback_result:
            print("✅ DHI feedback submitted successfully.")
            print("📈 Final Overall Score:", feedback_result.get("updated_record", {}).get("overall_score"))
    else:
        print("🔴 Could not find the pending review to provide feedback.")

    # 5. USER: Check their review status and generate the next task
    print("\n[5. USER] Checking review status...")
    user_review = client.get_review_details(review_id)
    if user_review and user_review.get("status") == "feedback_provided":
        print("✅ Admin feedback received! Generating the next task...")
        next_task_result = client.generate_next_task(review_id)
        if next_task_result:
            next_task = next_task_result.get("updated_record", {}).get("next_task", {})
            print("✅ Next task generated successfully:")
            print(json.dumps(next_task, indent=2))
    else:
        print("🔴 Review not yet ready for next task generation.")
        
    print("\n--- ✅ Workflow Simulation Complete ---")
