Of course. A good `README.md` is essential for any project.

I have updated the documentation to accurately reflect the final, role-based version of your application. The new `README.md` includes the new `ADMIN_PASSWORD` requirement, corrects the project structure, and provides much clearer instructions on how to run and use both the admin and user features.

Here is the updated, production-ready `README.md` file.

-----

# Production-Ready Task Reviewer Agent

This is a full-stack, stateful Generative AI application that acts as an intelligent mentor with a human-in-the-loop feedback system. It features distinct role-based dashboards for admins and users, reviews task submissions, provides scaffolded feedback, and generates follow-up tasks, enforcing a structured workflow from submission to completion.

## Features

  - **Intelligent Reviews**: Uses a Large Language Model to compare user submissions against task requirements, providing a technical score and qualitative feedback.
  - **Admin-in-the-Loop & DHI Scoring**: Captures human admin feedback and **Dignity, Honesty, Integrity (DHI)** scores to calculate a final overall score and unlock the workflow for the user.
  - **Role-Based Dashboards**: A complete frontend UI with separate, secure dashboards for Admins (task creation, feedback) and Users (task submission, review history).
  - **Stateful, Locked Workflow**: The backend API enforces a strict workflow, requiring admin feedback before a user can generate a follow-up task.
  - **Multiple Submission Methods**: Accepts submissions via direct text input, file upload, or a direct link to a raw file (e.g., GitHub Gist).
  - **Integration-Ready**: Includes a Python wrapper (`integration_wrapper.py`) for easy backend integration and testing.
  - **Full-Stack**: Complete with a FastAPI backend, MongoDB database, and a dynamic HTML/JS frontend.

## Tech Stack

  - **Backend**: FastAPI, LangChain, Pydantic, Uvicorn, Requests, python-dotenv
  - **AI**: Google Gemini API (`gemini-2.5-flash-lite-preview-09-2025`)
  - **Database**: MongoDB, PyMongo
  - **Frontend**: HTML, CSS, JavaScript

-----

## Project Structure

```
.
├── agent.py                 # The core FastAPI backend server
├── frontend.html            # The interactive frontend dashboard UI
├── integration_wrapper.py   # Python client/SDK for backend integration and testing
├── requirements.txt         # Project dependencies
└── .env                     # Environment variables (you will create this)
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
    AGENT_API_KEY="BHIV"
    ADMIN_PASSWORD="a-strong-admin-password"
    ```

      - `GOOGLE_API_KEY`: Your key for the Gemini API.
      - `AGENT_API_KEY`: A secret key you create. It must be sent in the `X-API-Key` header to use the agent's API. The default in `frontend.html` and the wrapper is `BHIV`.
      - `ADMIN_PASSWORD`: A secret password for the admin dashboard.

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
    Simply open the `frontend.html` file in your web browser to interact with the application.

      - **Login:** You will be prompted to log in as either a User or an Admin.
          - **User:** Enter any username to access the user dashboard.
          - **Admin:** Enter the password you set in the `.env` file to access the admin dashboard.
      - **Admin View:** Admins can create new tasks and view all pending submissions from users to provide DHI feedback.
      - **User View:** Users can see available tasks, submit their work, and view their submission history, including AI feedback and final scores after admin review.

### 2\. Test the Full Workflow via Command Line

The `integration_wrapper.py` script can be run directly to test the entire end-to-end API workflow from your terminal.

  - **Run the Wrapper:**
    Make sure the backend server is running, then execute the script in your terminal:
    ```bash
    python integration_wrapper.py
    ```
    This script will simulate a full interaction between an admin and a user:
    1.  An **admin** authenticates.
    2.  The **admin** creates a new task definition.
    3.  A **user** submits their work for review.
    4.  The **admin** fetches the list of pending reviews and provides DHI feedback for the user's submission, unlocking the workflow.
    5.  The **user** can now successfully generate a follow-up task.
