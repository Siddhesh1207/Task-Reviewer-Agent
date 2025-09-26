# Intelligent Task Reviewer Agent

This is a full-stack Generative AI application that acts as an automated mentor. It reviews task submissions, provides feedback, and generates follow-up tasks using a Large Language Model.

## Features
- **Intelligent Reviews**: Uses an LLM to compare submissions against task requirements.
- **Automated Feedback**: Generates human-friendly, constructive feedback notes.
- **Dynamic Task Generation**: Creates logical follow-up tasks based on performance.
- **Dual Submission Methods**: Accepts submissions via direct text input or file upload.
- **History Tracking**: Saves a complete record of each review to a MongoDB database.
- **Full-Stack**: Complete with a FastAPI backend, MongoDB database, and a simple HTML/JS frontend.

## Tech Stack
- **Backend**: FastAPI, LangChain, Pydantic, Uvicorn
- **AI**: Google Gemini API (`gemini-2.0-flash`)
- **Database**: MongoDB, PyMongo
- **Frontend**: HTML, CSS, JavaScript

---

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
    You need a Google Gemini API key. Set it in your terminal before running the application. For example, in Windows PowerShell:
    ```powershell
    $env:GOOGLE_API_KEY="Your-Google-API-Key"
    ```

---

## How to Run

1.  **Start the Backend Server:**
    Run the FastAPI server using Uvicorn from your project's root directory:
    ```bash
    uvicorn agent:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`. You can view the interactive documentation at `http://127.0.0.1:8000/docs`.

2.  **Use the Frontend UI:**
    Simply open the `index.html` file in your web browser to interact with the application.