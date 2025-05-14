from fastapi import FastAPI, HTTPException
import uvicorn
import requests
import subprocess
import os
import json
import re
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

# Model for regeneration requests
class RegenerateRequest(BaseModel):
    error_message: str

# Store the current conversation state
conversation_state = {
    "current_description": "",
    "needs_clarification": False,
    "question": "",
    "clarification_answers": []
}

# Helper function to extract JSON from LLM responses
def extract_json_from_response(response_text):
    # Try to extract JSON from markdown code blocks
    json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    matches = re.findall(json_pattern, response_text)
    
    if matches:
        # Try each match until we find valid JSON
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # If no JSON found in code blocks, try parsing the whole response
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        # If all else fails, try to find anything that looks like JSON
        try:
            # Find anything between curly braces
            json_candidate = re.search(r"\{[\s\S]*\}", response_text)
            if json_candidate:
                return json.loads(json_candidate.group(0))
        except (json.JSONDecodeError, AttributeError):
            pass
    
    # If we can't parse JSON, create a structured response
    if "needs_clarification" in response_text.lower() and "question" in response_text.lower():
        lines = response_text.strip().split('\n')
        for line in lines:
            if "?" in line:
                return {
                    "needs_clarification": True,
                    "question": line.strip()
                }
    
    # Best guess at whether it contains terraform code
    if "resource" in response_text and "{" in response_text and "}" in response_text:
        # Extract what looks like Terraform code
        return {
            "needs_clarification": False,
            "terraform_code": response_text.strip()
        }
    
    # Default fallback
    return {
        "error": "Could not parse LLM response",
        "raw_response": response_text
    }

# Endpoint to generate Terraform code
@app.post("/generate")
async def generate_terraform(request: InfraRequest):
    # Store the description for later use
    conversation_state["current_description"] = request.description
    conversation_state["clarification_answers"] = []
    
    # Prepare prompt for the LLM
    prompt = f"""
    You are a Terraform expert. Generate Terraform code based on the following infrastructure requirements:
    {request.description}
    
    Create code for the "kreuzwerker/docker" provider, not "hashicorp/docker".
    
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
    response_text = result.stdout
    response = extract_json_from_response(response_text)
            
    if response.get("needs_clarification", False):
        # Store the state for clarification
        conversation_state["needs_clarification"] = True
        conversation_state["question"] = response["question"]
        return {"needs_clarification": True, "question": response["question"]}
    else:
        # Reset clarification state
        conversation_state["needs_clarification"] = False
        terraform_code = response.get("terraform_code", "")
        
        # Save the code to the shared volume
        with open("/shared/main.tf", "w") as f:
            f.write(terraform_code)
            
        return {"needs_clarification": False, "terraform_code": terraform_code}

# Endpoint to handle clarification responses
@app.post("/clarify")
async def handle_clarification(response: ClarificationResponse):
    if not conversation_state.get("needs_clarification", False):
        raise HTTPException(status_code=400, detail="No clarification was requested")
    
    # Store the clarification answer
    conversation_state["clarification_answers"].append({
        "question": conversation_state["question"],
        "answer": response.answer
    })
    
    # Prepare clarification context
    clarification_context = ""
    for qa in conversation_state["clarification_answers"]:
        clarification_context += f"Q: {qa['question']}\nA: {qa['answer']}\n\n"
    
    # Prepare a new prompt with the clarification
    prompt = f"""
    You are a Terraform expert. Generate Terraform code based on the following infrastructure requirements:
    {conversation_state["current_description"]}
    
    Previous clarifications:
    {clarification_context}
    
    Create code for the "kreuzwerker/docker" provider, not "hashicorp/docker".
    
    If you still need more clarification, respond with a JSON object with 'needs_clarification' set to true and
    a 'question' field with your follow-up question.
    
    Otherwise, respond with a JSON object with 'needs_clarification' set to false and 'terraform_code' 
    containing the complete Terraform code.
    """
    
    # Call Ollama API
    result = subprocess.run(
        ["ollama", "run", "codellama", prompt],
        capture_output=True, text=True
    )
    
    # Parse the result
    response_text = result.stdout
    response = extract_json_from_response(response_text)
            
    if response.get("needs_clarification", False):
        # Update the state for the new clarification
        conversation_state["question"] = response["question"]
        return {"needs_clarification": True, "question": response["question"]}
    else:
        # Reset clarification state
        conversation_state["needs_clarification"] = False
        terraform_code = response.get("terraform_code", "")
        
        # Save the code to the shared volume
        with open("/shared/main.tf", "w") as f:
            f.write(terraform_code)
            
        return {"needs_clarification": False, "terraform_code": terraform_code}

# Endpoint to regenerate code after validation failure
@app.post("/regenerate")
async def regenerate_code(request: RegenerateRequest = None):
    # Get the error message if provided
    error_message = ""
    if request and request.error_message:
        error_message = request.error_message
    
    # Prepare clarification context
    clarification_context = ""
    for qa in conversation_state.get("clarification_answers", []):
        clarification_context += f"Q: {qa['question']}\nA: {qa['answer']}\n\n"
    
    # Read the current code if it exists
    current_code = ""
    try:
        with open("/shared/main.tf", "r") as f:
            current_code = f.read()
    except FileNotFoundError:
        pass
    
    # Prepare a prompt for regeneration
    prompt = f"""
    You are a Terraform expert. The following Terraform code failed validation:
    
    ```terraform
    {current_code}
    ```
    
    The error message was:
    {error_message}
    
    Original requirement:
    {conversation_state.get("current_description", "")}
    
    Previous clarifications:
    {clarification_context}
    
    Please fix the code and provide a corrected version. Make sure to:
    1. Use the "kreuzwerker/docker" provider, not "hashicorp/docker"
    2. Fix any syntax or validation errors
    3. Include all necessary provider configurations
    
    Respond with a JSON object with 'terraform_code' containing the complete fixed Terraform code.
    """
    
    # Call Ollama API
    result = subprocess.run(
        ["ollama", "run", "codellama", prompt],
        capture_output=True, text=True
    )
    
    # Parse the result
    response_text = result.stdout
    response = extract_json_from_response(response_text)
    
    terraform_code = response.get("terraform_code", "")
    
    # Save the code to the shared volume
    with open("/shared/main.tf", "w") as f:
        f.write(terraform_code)
        
    return {"terraform_code": terraform_code}

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