from fastapi import FastAPI, HTTPException
import uvicorn
import requests
import subprocess
import os
import json
from pydantic import BaseModel

app = FastAPI()

# Model for receiving infrastructure requests
class InfraRequest(BaseModel):
    description: str
    
# Model for sending clarification requests
class ClarificationRequest(BaseModel):
    question: str
    
# Model for receiving clarification responses
class ClarificationResponse(BaseModel):
    answer: str

# Store the current conversation state
conversation_state = {
    "current_description": "",
    "needs_clarification": False,
    "question": ""
}

# Endpoint to generate Terraform code
@app.post("/generate")
async def generate_terraform(request: InfraRequest):
    # Store the description for later use
    conversation_state["current_description"] = request.description
    
    # Prepare prompt for the LLM
    prompt = f"""
    You are a Terraform expert. Generate Terraform code based on the following infrastructure requirements:
    {request.description}
    
    If you need any clarification, respond with a JSON object with a 'needs_clarification' field set to true 
    and a 'question' field containing your question.
    
    Otherwise, respond with a JSON object with 'needs_clarification' set to false and 'terraform_code' 
    containing the complete Terraform code.
    """
    
    # Call Ollama API
    result = subprocess.run(
        ["ollama", "run", "codellama", prompt],
        capture_output=True, text=True
    )
    
    # Parse the result
    try:
        response_text = result.stdout
        # Try to extract JSON from the response (it might be surrounded by markdown code blocks)
        if "```json" in response_text:
            json_content = response_text.split("```json")[1].split("```")[0].strip()
            response = json.loads(json_content)
        else:
            # Attempt to parse the whole response as JSON
            response = json.loads(response_text)
            
        if response.get("needs_clarification", False):
            # Store the state for clarification
            conversation_state["needs_clarification"] = True
            conversation_state["question"] = response["question"]
            return {"needs_clarification": True, "question": response["question"]}
        else:
            # Reset clarification state
            conversation_state["needs_clarification"] = False
            terraform_code = response["terraform_code"]
            
            # Save the code to the shared volume
            with open("/shared/main.tf", "w") as f:
                f.write(terraform_code)
                
            return {"needs_clarification": False, "terraform_code": terraform_code}
    except json.JSONDecodeError:
        # Handle case where LLM did not return valid JSON
        return {"error": "Failed to parse LLM response", "raw_response": result.stdout}

# Endpoint to handle clarification responses
@app.post("/clarify")
async def handle_clarification(response: ClarificationResponse):
    if not conversation_state["needs_clarification"]:
        raise HTTPException(status_code=400, detail="No clarification was requested")
    
    # Prepare a new prompt with the clarification
    prompt = f"""
    You are a Terraform expert. Generate Terraform code based on the following infrastructure requirements:
    {conversation_state["current_description"]}
    
    I asked for clarification: {conversation_state["question"]}
    You answered: {response.answer}
    
    Based on this information, respond with a JSON object with 'needs_clarification' set to false and 'terraform_code' 
    containing the complete Terraform code. If you still need more clarification, respond with a JSON object with
    'needs_clarification' set to true and a 'question' field with your follow-up question.
    """
    
    # Call Ollama API
    result = subprocess.run(
        ["ollama", "run", "codellama", prompt],
        capture_output=True, text=True
    )
    
    # Parse the result
    try:
        response_text = result.stdout
        # Try to extract JSON from the response (it might be surrounded by markdown code blocks)
        if "```json" in response_text:
            json_content = response_text.split("```json")[1].split("```")[0].strip()
            response = json.loads(json_content)
        else:
            # Attempt to parse the whole response as JSON
            response = json.loads(response_text)
            
        if response.get("needs_clarification", False):
            # Update the state for the new clarification
            conversation_state["question"] = response["question"]
            return {"needs_clarification": True, "question": response["question"]}
        else:
            # Reset clarification state
            conversation_state["needs_clarification"] = False
            terraform_code = response["terraform_code"]
            
            # Save the code to the shared volume
            with open("/shared/main.tf", "w") as f:
                f.write(terraform_code)
                
            return {"needs_clarification": False, "terraform_code": terraform_code}
    except json.JSONDecodeError:
        # Handle case where LLM did not return valid JSON
        return {"error": "Failed to parse LLM response", "raw_response": result.stdout}

# Endpoint to validate Terraform code
@app.post("/validate")
async def validate_terraform():
    try:
        # Call Terraform container API to validate
        response = requests.post("http://terraform:8001/validate")
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Terraform service: {str(e)}")

# Endpoint to deploy Terraform code
@app.post("/deploy")
async def deploy_terraform():
    try:
        # Call Terraform container API to deploy
        response = requests.post("http://terraform:8001/deploy")
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Terraform service: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)