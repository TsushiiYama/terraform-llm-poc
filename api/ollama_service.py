from fastapi import FastAPI, HTTPException, Depends
import uvicorn
import requests
import subprocess
import os
import json
import re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from abc import ABC, abstractmethod

# Models - Single Responsibility Principle
class InfraRequest(BaseModel):
    description: str
    
class ClarificationRequest(BaseModel):
    question: str
    
class ClarificationResponse(BaseModel):
    answer: str

class RegenerateRequest(BaseModel):
    error_message: str

class TerraformCode(BaseModel):
    terraform_code: str
    needs_clarification: bool = False
    question: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[str] = None

class ConversationState(BaseModel):
    current_description: str = ""
    needs_clarification: bool = False
    question: str = ""
    clarification_answers: List[Dict[str, str]] = []

# Repository interfaces - Dependency Inversion Principle
class IFileRepository(ABC):
    @abstractmethod
    def save_file(self, path: str, content: str) -> None:
        pass
    
    @abstractmethod
    def read_file(self, path: str) -> str:
        pass

# Concrete Repository Implementation
class FileSystemRepository(IFileRepository):
    def save_file(self, path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)
    
    def read_file(self, path: str) -> str:
        try:
            with open(path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return ""

# Service interfaces - Dependency Inversion & Interface Segregation
class ILLMService(ABC):
    @abstractmethod
    def generate_code(self, prompt: str) -> str:
        pass

class ICodeExtractor(ABC):
    @abstractmethod
    def extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def extract_terraform_code(self, text: str) -> str:
        pass
    
    @abstractmethod
    def clean_terraform_code(self, code: str) -> str:
        pass

class ITerraformService(ABC):
    @abstractmethod
    def validate(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def deploy(self) -> Dict[str, Any]:
        pass

# Concrete Service Implementations
class OllamaLLMService(ILLMService):
    def __init__(self, model_name: str = "codellama"):
        self.model_name = model_name
    
    def generate_code(self, prompt: str) -> str:
        result = subprocess.run(
            ["ollama", "run", self.model_name, prompt],
            capture_output=True, text=True
        )
        return result.stdout

class TerraformCodeExtractor(ICodeExtractor):
    def extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
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
            terraform_code = self.extract_terraform_code(response_text)
            if terraform_code:
                return {
                    "needs_clarification": False,
                    "terraform_code": terraform_code
                }
        
        # Default fallback
        return {
            "error": "Could not parse LLM response",
            "raw_response": response_text
        }

    def extract_terraform_code(self, text: str) -> str:
        # Try to extract terraform code from markdown code blocks
        code_pattern = r"```(?:terraform|hcl)?\s*([\s\S]*?)\s*```"
        matches = re.findall(code_pattern, text)
        
        if matches:
            # Join all code blocks and clean
            code = "\n\n".join([match.strip() for match in matches])
            return self.clean_terraform_code(code)
        
        # If no code blocks, try to extract just the terraform code parts
        lines = text.strip().split('\n')
        code_lines = []
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            
            # Check if this line looks like Terraform code
            if (stripped.startswith("resource ") or 
                stripped.startswith("provider ") or 
                stripped.startswith("terraform {") or
                stripped.startswith("module ") or
                stripped.startswith("variable ") or
                stripped.startswith("output ") or
                stripped.startswith("locals {") or
                stripped.startswith("data ")):
                in_code_block = True
                code_lines.append(line)
            # Continue capturing lines if we're in a code block
            elif in_code_block:
                if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
                    code_lines.append(line)
                    # Check for block end
                    if stripped == "}" and not any(c for c in stripped if c not in ['}', ' ', '\t']):
                        in_code_block = False
        
        if code_lines:
            return self.clean_terraform_code("\n".join(code_lines))
        
        # If all else fails, just return lines that look like they might be code
        potential_code_lines = []
        for line in lines:
            stripped = line.strip()
            if ('{' in stripped or '}' in stripped or '=' in stripped) and not stripped.startswith('#') and not stripped.startswith('//'):
                potential_code_lines.append(line)
        
        if potential_code_lines:
            return self.clean_terraform_code("\n".join(potential_code_lines))
        
        return ""

    def clean_terraform_code(self, code: str) -> str:
        # Replace incorrect provider references
        if 'provider "kreuzwerker"' in code:
            code = code.replace('provider "kreuzwerker"', 'provider "docker"')
        
        # Fix resource types
        if 'source "docker_container"' in code:
            code = code.replace('source "docker_container"', 'resource "docker_container"')
        
        # Fix typo in "reresource"
        if 'reresource "docker_container"' in code:
            code = code.replace('reresource "docker_container"', 'resource "docker_container"')
        
        # Fix any other "reresource" typos
        if 'reresource "' in code:
            code = code.replace('reresource "', 'resource "')
        
        # Remove any provider definition (we'll use our own)
        provider_pattern = r'provider\s+"docker"\s+\{[^}]*\}'
        code = re.sub(provider_pattern, '', code)
        
        # Remove any terraform block (we'll provide it)
        terraform_pattern = r'terraform\s+\{[^}]*\}'
        code = re.sub(terraform_pattern, '', code)
        
        return code.strip()

class TerraformServiceAPI(ITerraformService):
    def __init__(self, api_base_url: str = "http://terraform:8001"):
        self.api_base_url = api_base_url
    
    def validate(self) -> Dict[str, Any]:
        try:
            response = requests.post(f"{self.api_base_url}/validate")
            return response.json()
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Terraform service: {str(e)}")
    
    def deploy(self) -> Dict[str, Any]:
        try:
            response = requests.post(f"{self.api_base_url}/deploy")
            return response.json()
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Terraform service: {str(e)}")

# Prompt Template Service
class PromptTemplateService:
    def get_generation_prompt(self, description: str) -> str:
        return f"""
        You are a Terraform expert. Generate Terraform code based on the following infrastructure requirements:
        {description}
        
        CRITICAL INSTRUCTIONS:
        1. DO NOT define a terraform provider block or provider configuration - it will be added automatically.
        2. DO NOT define a 'provider "kreuzwerker"' block - this is incorrect.
        3. Use ONLY "resource" blocks (not "reresource" - avoid this typo).
        4. Use only "resource "docker_container"" and "resource "docker_image"" in your code.
        5. DO NOT specify host or other provider-specific configuration.
        6. Put your Terraform code inside ```terraform code blocks.
        7. Keep your code simple and to the point - no explanations or comments inside the code.
        
        Example of correct code format:
        ```terraform
        resource "docker_image" "nginx" {{
          name = "nginx:latest"
        }}
        
        resource "docker_container" "nginx" {{
          name  = "nginx-container"
          image = docker_image.nginx.name
          ports {{
            internal = 80
            external = 8080
          }}
        }}
        ```
        
        If you need any clarification, respond with a JSON object with a 'needs_clarification' field set to true 
        and a 'question' field containing your question.
        
        Otherwise, provide ONLY the complete Terraform code inside a ```terraform code block.
        """
    
    def get_clarification_prompt(self, description: str, clarification_context: str) -> str:
        return f"""
        You are a Terraform expert. Generate Terraform code based on the following infrastructure requirements:
        {description}
        
        Previous clarifications:
        {clarification_context}
        
        CRITICAL INSTRUCTIONS:
        1. DO NOT define a terraform provider block or provider configuration - it will be added automatically.
        2. DO NOT define a 'provider "kreuzwerker"' block - this is incorrect.
        3. Use ONLY "resource" blocks (not "reresource" - avoid this typo).
        4. Use only "resource "docker_container"" and "resource "docker_image"" in your code.
        5. DO NOT specify host or other provider-specific configuration.
        6. Put your Terraform code inside ```terraform code blocks.
        7. Keep your code simple and to the point - no explanations or comments inside the code.
        
        Example of correct code format:
        ```terraform
        resource "docker_image" "nginx" {{
          name = "nginx:latest"
        }}
        
        resource "docker_container" "nginx" {{
          name  = "nginx-container"
          image = docker_image.nginx.name
          ports {{
            internal = 80
            external = 8080
          }}
        }}
        ```
        
        If you still need more clarification, respond with a JSON object with 'needs_clarification' set to true and
        a 'question' field with your follow-up question.
        
        Otherwise, provide ONLY the complete Terraform code inside a ```terraform code block.
        """
    
    def get_regeneration_prompt(self, description: str, current_code: str, error_message: str, clarification_context: str) -> str:
        return f"""
        You are a Terraform expert. The following Terraform code failed validation:
        
        ```terraform
        {current_code}
        ```
        
        The error message was:
        {error_message}
        
        Original requirement:
        {description}
        
        Previous clarifications:
        {clarification_context}
        
        CRITICAL INSTRUCTIONS:
        1. DO NOT define a terraform provider block or provider configuration - it will be added automatically.
        2. DO NOT define a 'provider "kreuzwerker"' block - this is incorrect.
        3. Use ONLY "resource" blocks (not "reresource" - avoid this typo).
        4. Use only "resource "docker_container"" and "resource "docker_image"" in your code.
        5. DO NOT specify host or other provider-specific configuration.
        6. Put your Terraform code inside ```terraform code blocks.
        7. Keep your code simple and to the point - no explanations or comments inside the code.
        
        Example of correct code format:
        ```terraform
        resource "docker_image" "nginx" {{
          name = "nginx:latest"
        }}
        
        resource "docker_container" "nginx" {{
          name  = "nginx-container"
          image = docker_image.nginx.name
          ports {{
            internal = 80
            external = 8080
          }}
        }}
        ```
        
        Provide ONLY the complete fixed Terraform code inside a ```terraform code block.
        """

# Service Factory - Factory pattern for dependency injection
class ServiceFactory:
    @staticmethod
    def get_llm_service() -> ILLMService:
        return OllamaLLMService()
    
    @staticmethod
    def get_code_extractor() -> ICodeExtractor:
        return TerraformCodeExtractor()
    
    @staticmethod
    def get_terraform_service() -> ITerraformService:
        return TerraformServiceAPI()
    
    @staticmethod
    def get_file_repository() -> IFileRepository:
        return FileSystemRepository()
    
    @staticmethod
    def get_prompt_service() -> PromptTemplateService:
        return PromptTemplateService()

# Dependency Injection container
def get_llm_service() -> ILLMService:
    return ServiceFactory.get_llm_service()

def get_code_extractor() -> ICodeExtractor:
    return ServiceFactory.get_code_extractor()

def get_terraform_service() -> ITerraformService:
    return ServiceFactory.get_terraform_service()

def get_file_repository() -> IFileRepository:
    return ServiceFactory.get_file_repository()

def get_prompt_service() -> PromptTemplateService:
    return ServiceFactory.get_prompt_service()

# Global state - In a real app, this would be a database or distributed cache
conversation_state = ConversationState()

# FastAPI application
app = FastAPI()

# Endpoints - Open/Closed Principle
@app.post("/generate")
async def generate_terraform(
    request: InfraRequest,
    llm_service: ILLMService = Depends(get_llm_service),
    code_extractor: ICodeExtractor = Depends(get_code_extractor),
    file_repository: IFileRepository = Depends(get_file_repository),
    prompt_service: PromptTemplateService = Depends(get_prompt_service)
) -> TerraformCode:
    # Store the description for later use
    conversation_state.current_description = request.description
    conversation_state.clarification_answers = []
    
    # Get prompt from template service
    prompt = prompt_service.get_generation_prompt(request.description)
    
    # Call Ollama API through the LLM service
    response_text = llm_service.generate_code(prompt)
    
    # Extract and process the response
    response = code_extractor.extract_json_from_response(response_text)
            
    if response.get("needs_clarification", False):
        # Store the state for clarification
        conversation_state.needs_clarification = True
        conversation_state.question = response["question"]
        return TerraformCode(
            needs_clarification=True, 
            question=response["question"],
            terraform_code=""
        )
    else:
        # Reset clarification state
        conversation_state.needs_clarification = False
        terraform_code = response.get("terraform_code", "")
        
        # Save the code to the shared volume
        file_repository.save_file("/shared/main.tf", terraform_code)
            
        return TerraformCode(
            needs_clarification=False, 
            terraform_code=terraform_code
        )

@app.post("/clarify")
async def handle_clarification(
    response: ClarificationResponse,
    llm_service: ILLMService = Depends(get_llm_service),
    code_extractor: ICodeExtractor = Depends(get_code_extractor),
    file_repository: IFileRepository = Depends(get_file_repository),
    prompt_service: PromptTemplateService = Depends(get_prompt_service)
) -> TerraformCode:
    if not conversation_state.needs_clarification:
        raise HTTPException(status_code=400, detail="No clarification was requested")
    
    # Store the clarification answer
    conversation_state.clarification_answers.append({
        "question": conversation_state.question,
        "answer": response.answer
    })
    
    # Prepare clarification context
    clarification_context = ""
    for qa in conversation_state.clarification_answers:
        clarification_context += f"Q: {qa['question']}\nA: {qa['answer']}\n\n"
    
    # Get prompt from template service
    prompt = prompt_service.get_clarification_prompt(
        conversation_state.current_description, 
        clarification_context
    )
    
    # Call Ollama API through the LLM service
    response_text = llm_service.generate_code(prompt)
    
    # Extract and process the response
    response = code_extractor.extract_json_from_response(response_text)
            
    if response.get("needs_clarification", False):
        # Update the state for the new clarification
        conversation_state.question = response["question"]
        return TerraformCode(
            needs_clarification=True, 
            question=response["question"],
            terraform_code=""
        )
    else:
        # Reset clarification state
        conversation_state.needs_clarification = False
        terraform_code = response.get("terraform_code", "")
        
        # Save the code to the shared volume
        file_repository.save_file("/shared/main.tf", terraform_code)
            
        return TerraformCode(
            needs_clarification=False, 
            terraform_code=terraform_code
        )

@app.post("/regenerate")
async def regenerate_code(
    request: RegenerateRequest = None,
    llm_service: ILLMService = Depends(get_llm_service),
    code_extractor: ICodeExtractor = Depends(get_code_extractor),
    file_repository: IFileRepository = Depends(get_file_repository),
    prompt_service: PromptTemplateService = Depends(get_prompt_service)
) -> TerraformCode:
    # Get the error message if provided
    error_message = ""
    if request and request.error_message:
        error_message = request.error_message
    
    # Prepare clarification context
    clarification_context = ""
    for qa in conversation_state.clarification_answers:
        clarification_context += f"Q: {qa['question']}\nA: {qa['answer']}\n\n"
    
    # Read the current code if it exists
    current_code = file_repository.read_file("/shared/main.tf")
    
    # Get prompt from template service
    prompt = prompt_service.get_regeneration_prompt(
        conversation_state.current_description,
        current_code,
        error_message,
        clarification_context
    )
    
    # Call Ollama API through the LLM service
    response_text = llm_service.generate_code(prompt)
    
    # Extract and process the response
    response = code_extractor.extract_json_from_response(response_text)
    
    terraform_code = response.get("terraform_code", "")
    
    # Save the code to the shared volume
    file_repository.save_file("/shared/main.tf", terraform_code)
        
    return TerraformCode(
        needs_clarification=False,
        terraform_code=terraform_code
    )

@app.post("/validate")
async def validate_terraform(
    terraform_service: ITerraformService = Depends(get_terraform_service)
):
    return terraform_service.validate()

@app.post("/deploy")
async def deploy_terraform(
    terraform_service: ITerraformService = Depends(get_terraform_service)
):
    return terraform_service.deploy()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)