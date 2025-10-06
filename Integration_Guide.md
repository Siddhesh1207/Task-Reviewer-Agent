# Task Reviewer Agent - Integration Guide

This guide explains how to integrate the Task Reviewer Agent into the main Task Manager platform. The agent exposes a REST API for creating tasks, submitting work for review, and providing feedback.

**Team Contacts:**

  * **Agent Logic:** Siddhesh
  * **Backend Processes:** Vijay
  * **Frontend UI/UX:** Nikhil

-----

## **API Configuration**

  * **Base URL**: `http://<AGENT_HOST>:<AGENT_PORT>` (e.g., `http://127.0.0.1:8000`)
  * **Authentication**: All endpoints require an API key sent in the `X-API-Key` header.

-----

## **Core Workflow**

The integration follows a state-driven process centered around user and admin roles. The `status` field in the response object dictates the available actions.

1.  **ADMIN: (Optional) Create Task Definition**: If a task doesn't exist, an admin creates it via `POST /tasks`.
2.  **USER: Submit for AI Review**: A user submits their work against a `task_id`. This call **must include a `username`**. The agent returns an initial AI review and a unique `review_id`. The initial status will be `pending_feedback`.
3.  **ADMIN: Provide Feedback & DHI Scores**: An admin fetches pending reviews and provides feedback for a specific `review_id`. This call is mandatory and updates the status to `feedback_provided`.
4.  **USER: Generate Next Task**: After admin feedback is provided, the user can call this endpoint. This action provides a suggestion for the user's next task and implicitly marks the current review cycle as `completed`.

-----

## **Endpoints**

### 1\. Admin: Create a Task

  * **Endpoint**: `POST /tasks`
  * **Description**: Registers a new task definition with the agent.
  * **Request Body**:
    ```json
    {
      "task_id": "unique-task-string-001",
      "title": "Create a User Login Form",
      "description": "Develop an HTML form with email and password fields, and a submit button."
    }
    ```

### 2\. User: Submit for AI Review

  * **Endpoint**: `POST /review/link/{task_id}/{username}`
  * **Description**: Submits a link for an initial AI review. **Note the required `username` path parameter.**
  * **Other Submission Endpoints**:
      * `POST /review/text/{task_id}/{username}`
      * `POST /review/file/{task_id}/{username}`
  * **Request Body** (for link):
    ```json
    {
      "submission_link": "https://link.to/raw/submission/file.py"
    }
    ```
  * **Success Response** (`200 OK`): Returns the full `ReviewHistory` object with the initial status set to `pending_feedback`.

### 3\. Admin: Provide Feedback & DHI Scores

  * **Endpoint**: `POST /feedback/{review_id}`
  * **Description**: Submits admin feedback. This unlocks the workflow for the user.
  * **Request Body**:
    ```json
    {
      "sentiment": "up",
      "dhi_scores": { "dignity": 8, "honesty": 9, "integrity": 10 }
    }
    ```
  * **Success Response** (`200 OK`):
    ```json
    {
      "status": "success",
      "updated_record": { "... full updated review history object with status: 'feedback_provided' ..." }
    }
    ```

### 4\. User: Generate Next Task

  * **Endpoint**: `POST /generate-next-task/{review_id}`
  * **Description**: Can only be called after the status is `feedback_provided`. Calling this endpoint updates the review record with the next task and sets its status to `completed`.
  * **Success Response** (`200 OK`):
    ```json
    {
      "status": "success",
      "updated_record": { "... full updated review history object with next_task populated and status: 'completed' ..." }
    }
    ```

### 5\. Utility Endpoints

  * **Admin Login**: `POST /auth/admin`
      * Authenticates an admin using a password.
  * **Get All Tasks**: `GET /tasks/all`
      * Fetches a list of all available task definitions.
  * **Get Pending Reviews (Admin)**: `GET /admin/pending-reviews`
      * Returns a list of all reviews with the status `pending_feedback`.
  * **Get User Reviews (User)**: `GET /user/{username}/reviews`
      * Fetches the complete submission history for a specific user.
  * **Get Review Details**: `GET /review/{review_id}`
      * Fetches the complete, up-to-date record for a given `review_id`.

-----

## **Using the Python Wrapper (for Vijay)**

For backend integration, the `integration_wrapper.py` script provides a `TaskReviewerClient` class that acts as an SDK, simplifying all API interactions.

  * **Do not run the script directly.** Instead, import the `TaskReviewerClient` class into the main Task Manager backend code.

  * Instantiate the client with the agent's URL and API key.

  * Use the client's methods to programmatically interact with the agent. Key method signatures have been updated:

      * `client.admin_login(password)`
      * `client.create_task_definition(task_id, title, desc)`
      * `client.get_all_tasks()`
      * `client.trigger_review_with_link(task_id, username, link)`
      * `client.get_pending_reviews()`
      * `client.send_feedback_with_dhi(review_id, sentiment, scores)`
      * `client.get_user_reviews(username)`
      * `client.generate_next_task(review_id)`