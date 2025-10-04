Of course. Your old `README.md` is for a simple prototype, but you've built a much more advanced, production-ready application.

Here is a completely updated `README.md` that accurately reflects all the new features, the improved tech stack, and the correct setup instructions for your final project.

-----

# Production-Ready Task Reviewer Agent

This is a full-stack, stateful Generative AI application that acts as an intelligent mentor with a human-in-the-loop feedback system. It reviews task submissions, provides scaffolded feedback, and generates follow-up tasks, enforcing a structured workflow from submission to completion.

## Features

  - **Intelligent Reviews**: Uses a Large Language Model to compare user submissions against task requirements.
  - **Reinforcement Loop & DHI Scoring**: Captures human feedback (👍/👎) and **Dignity, Honesty, Integrity (DHI)** scores to evaluate and improve the review process.
  - **Stateful, Locked Workflow**: The backend API enforces a strict workflow, requiring human feedback before unlocking subsequent actions like generating a new task.
  - **Multiple Submission Methods**: Accepts submissions via direct text input, file upload, or a direct link to a raw file (e.g., GitHub Gist).
  - **Integration-Ready**: Includes a Python wrapper (`integration_wrapper.py`) for easy backend integration and a `/metadata` endpoint for service discovery by an orchestrator.
  - **Full-Stack**: Complete with a FastAPI backend, MongoDB database, and a dynamic HTML/JS frontend dashboard.

## Tech Stack

  - **Backend**: FastAPI, LangChain, Pydantic, Uvicorn, Requests, python-dotenv
  - **AI**: Google Gemini API (`gemini-2.5-flash-lite-preview-09-2025`)
  - **Database**: MongoDB, PyMongo
  - **Frontend**: HTML, CSS, JavaScript

-----

## Project Structure

```
.
├── agent.py                  # The core FastAPI backend server
├── index.html                # The interactive frontend dashboard UI
├── integration_wrapper.py    # Python client/SDK for backend integration and testing
├── requirements.txt          # Project dependencies
└── .env                      # Environment variables (you will create this)
```

-----

## Setup and Installation

1.  **Clone the repository:**

    ```bash
    git clone <your-repo-link>
    cd <your-repo-name>
    ```

2.  **Create a Conda environment:**

    ```bash
    conda create --name reviewer_env python=3.10
    conda activate reviewer_env
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Environment Variables:**
    Create a new file named `.env` in the root of your project directory. This file will store your secret keys. Add the following content to it, replacing the placeholder values with your actual keys:

    **.env**

    ```env
    GOOGLE_API_KEY="Your-Google-Gemini-API-Key"
    AGENT_API_KEY="a-strong-secret-key-you-create"
    ```

      - `GOOGLE_API_KEY`: Your key for the Gemini API.
      - `AGENT_API_KEY`: A secret password you create. It must be sent in the `X-API-Key` header to use the agent's API. The default in the frontend/wrapper is `default-secret-key`.

-----

## How to Run

### 1\. Run the Full Application (Backend + Frontend)

First, start the backend server. Then, open the frontend in your browser.

  - **Start the Backend Server:**
    Run the FastAPI server using Uvicorn from your project's root directory:

    ```bash
    uvicorn agent:app --reload
    ```

    The API will be available at `http://127.0.0.1:8000`. You can view the interactive documentation at `http://127.0.0.1:8000/docs`.

  - **Use the Frontend UI:**
    Simply open the `frontend.html` file in your web browser to interact with the application. Remember to set the `API_KEY` variable in the script tag of the HTML file if you changed it from the default.

### 2\. Test the Full Workflow via Command Line

The `integration_wrapper.py` script can be run directly to test the entire end-to-end API workflow from your terminal.

  - **Run the Wrapper:**
    Make sure the backend server is running, then execute the script in your terminal:
    ```bash
    python integration_wrapper.py
    ```
    This script will automatically:
    1.  Create a task.
    2.  Submit a link for review.
    3.  Attempt (and fail) to get the next task before feedback.
    4.  Provide feedback with DHI scores to unlock the workflow.
    5.  Successfully generate the next task.
    6.  Fetch the final record and mark the task as complete.
