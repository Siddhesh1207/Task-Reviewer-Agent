import os
import google.generativeai as genai
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Any, List
from pydantic_core import core_schema

# --- LangChain Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser

# --- LLM Client Setup ---
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    print("WARNING: GOOGLE_API_KEY environment variable not set.")

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
class ReviewData(BaseModel):
    task_id: str; score: int; done_well: List[str]; missing: List[str]; submission_summary: str
class NextTask(BaseModel): title: str; objectives: List[str]; deliverables: str
class ReviewHistory(BaseModel):
    id: PyObjectId | None = Field(default=None, alias="_id")
    task_id: str; review_data: ReviewData; feedback_note: str; next_task: NextTask
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    class Config: populate_by_name = True; arbitrary_types_allowed = True; json_encoders = {ObjectId: str}

# --- LangChain Setup ---

model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2, convert_system_message_to_human=True)

review_parser = PydanticOutputParser(pydantic_object=ReviewData)
review_prompt_template = PromptTemplate.from_template(
    """
    ROLE: You are an expert code and task reviewer...
    TASK: Compare the user's SUBMISSION against the original TASK DESCRIPTION...
    {format_instructions}
    ---
    ORIGINAL TASK DESCRIPTION:
    {task_description}
    ---
    USER'S SUBMISSION:
    {submission_text}
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
app = FastAPI(title="Intelligent Task Reviewer Agent", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

def _run_full_review_logic(task_id: str, submission_text: str) -> dict:
    task = tasks_collection.find_one({"task_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with id '{task_id}' not found.")
    
    review_data = review_chain.invoke({
        "task_description": task.get("description", ""),
        "submission_text": submission_text,
        "task_id": task_id
    })
    
    note = note_chain.invoke(review_data.model_dump())
    next_task = next_task_chain.invoke(review_data.model_dump())

    history_record = ReviewHistory(
        task_id=task_id, review_data=review_data, feedback_note=note, next_task=next_task
    )
    history_dict = history_record.model_dump(by_alias=True, exclude=["id"])
    reviews_collection.insert_one(history_dict)

    return {"review": review_data, "feedback_note": {"note": note}, "next_task": next_task, "history_saved": True}

# --- API Endpoints ---
@app.post("/tasks")
def create_task(task: Task):
    task_dict = task.model_dump(by_alias=True, exclude=["id"])
    if tasks_collection.find_one({"task_id": task_dict["task_id"]}):
        raise HTTPException(status_code=400, detail=f"Task with id '{task_dict['task_id']}' already exists.")
    tasks_collection.insert_one(task_dict)
    return {"status": "success", "message": "Task created successfully", "task_id": task.task_id}

@app.post("/full-review-text/{task_id}")
def full_review_workflow_text(task_id: str, submission: ReviewSubmission):
    """Runs the entire review workflow from a TEXT submission."""
    return _run_full_review_logic(task_id, submission.submission_text)

@app.post("/full-review-file/{task_id}")
async def full_review_workflow_file(task_id: str, submission_file: UploadFile = File(...)):
    """Runs the entire review workflow from an UPLOADED FILE."""
    content_bytes = await submission_file.read()
    submission_text = content_bytes.decode('utf-8')
    return _run_full_review_logic(task_id, submission_text)