import os
import google.generativeai as genai
import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, File, UploadFile, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pymongo import MongoClient
from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Any, List
from pydantic_core import core_schema
from dotenv import load_dotenv
import requests
import numpy as np 

# --- Load Environment Variables ---
load_dotenv()

# --- LangChain Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- LLM Client Setup ---
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    logging.warning("GOOGLE_API_KEY environment variable not set.")

# --- API Key Security Setup ---
API_KEY = os.environ.get("AGENT_API_KEY", "default-secret-key")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "supersecret") 
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    else:
        logging.warning("Invalid API Key received.")
        raise HTTPException(status_code=403, detail="Could not validate credentials")

# --- Pydantic Models (Unchanged) ---
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _s, _h) -> core_schema.CoreSchema:
        def v(v: Any) -> ObjectId:
            if not ObjectId.is_valid(v): raise ValueError("Invalid ObjectId")
            return ObjectId(v)
        return core_schema.json_or_python_schema(
            python_schema=core_schema.with_info_plain_validator_function(v),
            json_schema=core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

class Task(BaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    task_id: str; title: str; description: str
    class Config: populate_by_name = True; arbitrary_types_allowed = True; json_encoders = {ObjectId: str}

class ReviewSubmission(BaseModel): submission_text: str
class LinkSubmission(BaseModel): submission_link: str

class DHIScores(BaseModel):
    dignity: int = Field(..., ge=1, le=10)
    honesty: int = Field(..., ge=1, le=10)
    integrity: int = Field(..., ge=1, le=10)

class ReviewData(BaseModel):
    task_id: str
    score: int = Field(..., description="AI-generated technical score out of 10")
    done_well: List[str]
    missing: List[str]
    submission_summary: str
    dhi_scores: DHIScores | None = None
    overall_score: float | None = None

class NextTask(BaseModel):
    title: str; objectives: List[str]; deliverables: str

class ReviewHistory(BaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    review_id: str = Field(default_factory=lambda: str(ObjectId()))
    username: str
    task_id: str
    review_data: ReviewData
    feedback_note: str
    next_task: NextTask
    feedback_sentiment: str | None = None
    dhi_scores: DHIScores | None = None
    overall_score: float | None = None
    status: str = Field(default="pending_feedback")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    class Config: populate_by_name = True; arbitrary_types_allowed = True; json_encoders = {ObjectId: str}

class Feedback(BaseModel):
    sentiment: str
    dhi_scores: DHIScores

class AdminLogin(BaseModel):
    password: str

# --- LangChain Setup ---
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite-preview-09-2025", temperature=0.2, convert_system_message_to_human=True)
review_parser = PydanticOutputParser(pydantic_object=ReviewData)

review_prompt_template = PromptTemplate.from_template(
    """
    ROLE: You are an expert code and task reviewer.
    TASK: Compare the user's SUBMISSION against the original TASK DESCRIPTION. Provide a structured review.
    The 'score' must be a technical score out of 10.
    {format_instructions}
    ---
    ORIGINAL TASK DESCRIPTION: {task_description}
    ---
    USER'S SUBMISSION: {submission_text}
    ---
    Now, provide your structured review. For the 'task_id', use the following ID: {task_id}
    """,
    partial_variables={"format_instructions": review_parser.get_format_instructions()}
)
review_chain = review_prompt_template | model | review_parser

note_prompt_template = PromptTemplate.from_template(
    """
    ROLE: You are a supportive mentor providing feedback.
    TASK: Write a short, 2-3 sentence feedback note based on the review data.
    ---
    REVIEW DATA:
    - Score: {score}/10
    - What was done well: {done_well}
    - What to improve: {missing}
    ---
    Please generate the feedback note now:
    """
)
note_chain = note_prompt_template | model | StrOutputParser()

next_task_parser = PydanticOutputParser(pydantic_object=NextTask)
# BUG FIX 2: Re-engineered the prompt for better quality output.
next_task_prompt_template = PromptTemplate.from_template(
    """
    ROLE: You are an intelligent and creative project manager responsible for mentoring a developer.
    TASK: Based on the provided review of the developer's previous task, devise a new, logical follow-up task.
    The new task should be a clear step forward, building on what they did well and addressing areas for improvement.

    {format_instructions}

    ---
    PREVIOUS TASK REVIEW DATA:
    - Score: {score}/10
    - What went well: {done_well}
    - What to improve: {missing}
    ---
    
    Now, generate the next task. Ensure the 'title' is concise and motivating. For the 'objectives', write them as a list of clear, user-friendly, and actionable steps (e.g., as bullet points). For the 'deliverables', describe the expected final output in a single, clear sentence.
    """,
    partial_variables={"format_instructions": next_task_parser.get_format_instructions()}
)
next_task_chain = next_task_prompt_template | model | next_task_parser

# --- MongoDB Connection (Unchanged) ---
client_mongo = MongoClient("mongodb://localhost:27017/")
db = client_mongo["task_reviewer_db_v1"] 
tasks_collection = db["tasks"]
reviews_collection = db["reviews"]

# --- FastAPI App ---
app = FastAPI(title="Role-Based Task Reviewer Agent", version="3.0.1") # Incremented version
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Core Logic & Endpoints (Unchanged) ---

def _run_review_and_note_logic(task_id: str, submission_text: str, username: str) -> dict:
    task = tasks_collection.find_one({"task_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with id '{task_id}' not found.")
    try:
        review_data = review_chain.invoke({"task_description": task.get("description", ""),"submission_text": submission_text, "task_id": task_id})
        note = note_chain.invoke(review_data.model_dump())
    except Exception as e:
        logging.error(f"Error during LangChain processing for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process review with AI model.")
    
    history_record = ReviewHistory(
        task_id=task_id,
        username=username,
        review_data=review_data,
        feedback_note=note,
        next_task=NextTask(title="", objectives=[], deliverables=""),
        status="pending_feedback"
    )
    history_dict = history_record.model_dump(by_alias=True, exclude=["id"])
    reviews_collection.insert_one(history_dict)
    
    review_id = history_dict.get("review_id")
    logging.info(f"Review created for user '{username}' on task '{task_id}' with review_id: {review_id}.")
    
    history_dict["_id"] = str(history_dict["_id"])
    return history_dict

@app.post("/auth/admin", tags=["Authentication"])
def admin_login(login_data: AdminLogin):
    if login_data.password == ADMIN_PASSWORD:
        return {"status": "success", "message": "Admin authenticated successfully."}
    raise HTTPException(status_code=401, detail="Invalid admin password.")

@app.post("/tasks", dependencies=[Depends(get_api_key)], tags=["Admin"])
def create_task(task: Task):
    task_dict = task.model_dump(by_alias=True, exclude=["id"])
    if tasks_collection.find_one({"task_id": task_dict["task_id"]}):
        raise HTTPException(status_code=400, detail=f"Task with id '{task_dict['task_id']}' already exists.")
    tasks_collection.insert_one(task_dict)
    return {"status": "success", "task_id": task.task_id}

@app.post("/review/text/{task_id}/{username}", dependencies=[Depends(get_api_key)], tags=["Review"])
def full_review_workflow_text(task_id: str, username: str, submission: ReviewSubmission):
    return _run_review_and_note_logic(task_id, submission.submission_text, username)

@app.post("/review/file/{task_id}/{username}", dependencies=[Depends(get_api_key)], tags=["Review"])
async def full_review_workflow_file(task_id: str, username: str, submission_file: UploadFile = File(...)):
    try:
        content_bytes = await submission_file.read()
        submission_text = content_bytes.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail="Could not read or decode the uploaded file.")
    return _run_review_and_note_logic(task_id, submission_text, username)

@app.post("/review/link/{task_id}/{username}", dependencies=[Depends(get_api_key)], tags=["Review"])
def full_review_workflow_link(task_id: str, username: str, submission: LinkSubmission):
    github_url = submission.submission_link
    raw_url = github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        submission_text = response.text
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch content from the provided link.")
    return _run_review_and_note_logic(task_id, submission_text, username)

@app.post("/feedback/{review_id}", dependencies=[Depends(get_api_key)], tags=["Admin"])
def provide_feedback(review_id: str, feedback: Feedback):
    review_record = reviews_collection.find_one({"review_id": review_id})
    if not review_record:
        raise HTTPException(status_code=404, detail="Review not found.")
    
    ai_score = review_record["review_data"]["score"]
    dhi = feedback.dhi_scores
    overall_score = np.mean([ai_score, dhi.dignity, dhi.honesty, dhi.integrity])

    update_data = {
        "feedback_sentiment": feedback.sentiment, "dhi_scores": dhi.model_dump(),
        "overall_score": round(overall_score, 2), "status": "feedback_provided"
    }
    reviews_collection.update_one({"review_id": review_id}, {"$set": update_data})
    
    updated_record = reviews_collection.find_one({"review_id": review_id})
    updated_record['_id'] = str(updated_record['_id'])
    return {"status": "success", "updated_record": updated_record}

@app.post("/generate-next-task/{review_id}", dependencies=[Depends(get_api_key)], tags=["User"])
def generate_next_task(review_id: str):
    review_record = reviews_collection.find_one({"review_id": review_id})
    if not review_record:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review_record.get("status") != "feedback_provided":
        raise HTTPException(status_code=423, detail="Admin feedback must be provided first.")

    full_review_context = review_record.get("review_data", {})
    next_task = next_task_chain.invoke(full_review_context)
    reviews_collection.update_one({"review_id": review_id}, {"$set": {"next_task": next_task.model_dump()}})
    
    updated_record = reviews_collection.find_one({"review_id": review_id})
    updated_record['_id'] = str(updated_record['_id'])
    return {"status": "success", "updated_record": updated_record}

@app.get("/review/{review_id}", dependencies=[Depends(get_api_key)], tags=["Data Retrieval"])
def get_review_details(review_id: str):
    review_record = reviews_collection.find_one({"review_id": review_id})
    if not review_record:
        raise HTTPException(status_code=404, detail=f"Review not found.")
    review_record['_id'] = str(review_record['_id'])
    return review_record

@app.get("/tasks/all", dependencies=[Depends(get_api_key)], tags=["Data Retrieval"])
def get_all_tasks():
    tasks = list(tasks_collection.find({}, {"_id": 0}))
    return tasks

@app.get("/admin/pending-reviews", dependencies=[Depends(get_api_key)], tags=["Admin"])
def get_pending_reviews():
    reviews = list(reviews_collection.find({"status": "pending_feedback"}))
    for r in reviews:
        r["_id"] = str(r["_id"])
    return reviews

@app.get("/user/{username}/reviews", dependencies=[Depends(get_api_key)], tags=["User"])
def get_user_reviews(username: str):
    reviews = list(reviews_collection.find({"username": username}))
    for r in reviews:
        r["_id"] = str(r["_id"])
    return reviews
