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
import requests # <-- NEW: Import the requests library

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
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    else:
        logging.warning("Invalid API Key received.")
        raise HTTPException(status_code=403, detail="Could not validate credentials")

# --- Pydantic Models ---
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

# <-- NEW: A model for link submissions -->
class LinkSubmission(BaseModel):
    submission_link: str

class ReviewData(BaseModel):
    task_id: str; score: int; done_well: List[str]; missing: List[str]; submission_summary: str

class NextTask(BaseModel):
    title: str; objectives: List[str]; deliverables: str

class ReviewHistory(BaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    review_id: str = Field(default_factory=lambda: str(ObjectId()))
    task_id: str; review_data: ReviewData; feedback_note: str; next_task: NextTask
    feedback_sentiment: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    class Config: populate_by_name = True; arbitrary_types_allowed = True; json_encoders = {ObjectId: str}

class Feedback(BaseModel): sentiment: str

# --- LangChain Setup ---
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite-preview-09-2025", temperature=0.2, convert_system_message_to_human=True)
# ... (rest of LangChain setup is the same)
review_parser = PydanticOutputParser(pydantic_object=ReviewData)
review_prompt_template = PromptTemplate.from_template(
    """
    ROLE: You are an expert code and task reviewer...
    TASK: Compare the user's SUBMISSION against the original TASK DESCRIPTION...
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
    ROLE: You are a supportive mentor providing feedback...
    TASK: Write a short, 2-3 sentence feedback note...
    ---
    REVIEW DATA:
    - Score: {score}/100
    - What was done well: {done_well}
    - What to improve: {missing}
    ---
    Please generate the feedback note now:
    """
)
note_chain = note_prompt_template | model | StrOutputParser()
next_task_parser = PydanticOutputParser(pydantic_object=NextTask)
next_task_prompt_template = PromptTemplate.from_template(
    """
    ROLE: You are an intelligent project manager...
    TASK: Based on the following review, generate a new, logical follow-up task...
    {format_instructions}
    ---
    PREVIOUS TASK REVIEW DATA:
    - Score: {score}
    - What went well: {done_well}
    - What to improve: {missing}
    ---
    Now, generate the next task:
    """,
    partial_variables={"format_instructions": next_task_parser.get_format_instructions()}
)
next_task_chain = next_task_prompt_template | model | next_task_parser

# --- MongoDB Connection ---
client_mongo = MongoClient("mongodb://localhost:27017/")
db = client_mongo["task_reviewer_db"]
tasks_collection = db["tasks"]
reviews_collection = db["reviews"]

# --- FastAPI App ---
app = FastAPI(title="Intelligent Task Reviewer Agent", version="6.0.0-links")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

def _run_review_and_note_logic(task_id: str, submission_text: str) -> dict:
    # ... (this function is the same as before)
    task = tasks_collection.find_one({"task_id": task_id})
    if not task:
        logging.error(f"Task lookup failed for task_id: {task_id}")
        raise HTTPException(status_code=404, detail=f"Task with id '{task_id}' not found.")
    try:
        review_data = review_chain.invoke({"task_description": task.get("description", ""),"submission_text": submission_text, "task_id": task_id})
        note = note_chain.invoke(review_data.model_dump())
    except Exception as e:
        logging.error(f"Error during LangChain processing for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process review with AI model.")
    history_record = ReviewHistory(task_id=task_id, review_data=review_data, feedback_note=note, next_task=NextTask(title="", objectives=[], deliverables=""))
    history_dict = history_record.model_dump(by_alias=True, exclude=["id"])
    reviews_collection.insert_one(history_dict)
    review_id = history_dict.get("review_id")
    logging.info(f"Review and Note created for task_id: {task_id} with review_id: {review_id}")
    return {"review": review_data, "feedback_note": {"note": note}, "review_id": review_id, "history_saved": True}

# --- API Endpoints ---
@app.post("/tasks", dependencies=[Depends(get_api_key)])
def create_task(task: Task):
    task_dict = task.model_dump(by_alias=True, exclude=["id"])
    if tasks_collection.find_one({"task_id": task_dict["task_id"]}):
        raise HTTPException(status_code=400, detail=f"Task with id '{task_dict['task_id']}' already exists.")
    tasks_collection.insert_one(task_dict)
    logging.info(f"Task created with task_id: {task.task_id}")
    return {"status": "success", "message": "Task created successfully", "task_id": task.task_id}

@app.post("/full-review-text/{task_id}", dependencies=[Depends(get_api_key)])
def full_review_workflow_text(task_id: str, submission: ReviewSubmission):
    logging.info(f"Starting text review for task_id: {task_id}")
    return _run_review_and_note_logic(task_id, submission.submission_text)

@app.post("/full-review-file/{task_id}", dependencies=[Depends(get_api_key)])
async def full_review_workflow_file(task_id: str, submission_file: UploadFile = File(...)):
    logging.info(f"Starting file review for task_id: {task_id}")
    try:
        content_bytes = await submission_file.read()
        submission_text = content_bytes.decode('utf-8')
    except Exception as e:
        logging.error(f"Error reading uploaded file for task {task_id}: {e}")
        raise HTTPException(status_code=400, detail="Could not read or decode the uploaded file.")
    return _run_review_and_note_logic(task_id, submission_text)

# <-- NEW: Endpoint to handle GitHub link submissions -->
@app.post("/full-review-link/{task_id}", dependencies=[Depends(get_api_key)])
def full_review_workflow_link(task_id: str, submission: LinkSubmission):
    logging.info(f"Starting link review for task_id: {task_id}")
    github_url = submission.submission_link

    # Convert standard GitHub URL to raw content URL
    if "github.com" in github_url:
        raw_url = github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    else:
        # Assuming it's already a raw link or another direct link
        raw_url = github_url
    
    try:
        response = requests.get(raw_url)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        submission_text = response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch content from URL {raw_url}: {e}")
        raise HTTPException(status_code=400, detail=f"Could not fetch content from the provided link. Please check the URL.")
    
    # Reuse the existing logic to run the review
    return _run_review_and_note_logic(task_id, submission_text)


@app.post("/feedback/{review_id}", dependencies=[Depends(get_api_key)])
def provide_feedback(review_id: str, feedback: Feedback):
    if feedback.sentiment not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Sentiment must be 'up' or 'down'.")
    result = reviews_collection.update_one({"review_id": review_id}, {"$set": {"feedback_sentiment": feedback.sentiment}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Review with id '{review_id}' not found.")
    logging.info(f"Feedback '{feedback.sentiment}' received for review_id: {review_id}")
    updated_record = reviews_collection.find_one({"review_id": review_id})
    if updated_record and '_id' in updated_record:
        updated_record['_id'] = str(updated_record['_id'])
    return {"status": "success", "message": f"Feedback recorded for review {review_id}.", "updated_record": updated_record}

@app.post("/generate-next-task/{review_id}", dependencies=[Depends(get_api_key)])
def generate_next_task(review_id: str):
    logging.info(f"Generating next task for review_id: {review_id}")
    review_record = reviews_collection.find_one({"review_id": review_id})
    if not review_record:
        raise HTTPException(status_code=404, detail=f"Review with id '{review_id}' not found.")
    try:
        next_task = next_task_chain.invoke(review_record.get("review_data", {}))
        reviews_collection.update_one({"review_id": review_id}, {"$set": {"next_task": next_task.model_dump()}})
        return {"next_task": next_task}
    except Exception as e:
        logging.error(f"Error generating next task for review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate next task with AI model.")
