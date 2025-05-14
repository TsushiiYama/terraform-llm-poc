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

# Endpoint to generate Terraform code
@app.post("/generate")
async def generate_terraform(request: InfraRequest):
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
        response = json.loads(result.stdout)
        if response.get("needs_clarification", False):
            return {"needs_clarification": True, "question": response["question"]}
        else:
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