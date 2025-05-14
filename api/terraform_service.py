from fastapi import FastAPI, HTTPException
import uvicorn
import subprocess
import os
import json

app = FastAPI()

# Set working directory for Terraform operations
TERRAFORM_DIR = "/shared"

# Create a required_providers.tf file
def create_required_providers():
    providers_content = """
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0.0"
    }
  }
}
"""
    with open(os.path.join(TERRAFORM_DIR, "required_providers.tf"), "w") as f:
        f.write(providers_content)

@app.post("/validate")
async def validate_terraform():
    # Change to the shared directory
    os.chdir(TERRAFORM_DIR)
    
    # Create required providers file
    create_required_providers()
    
    # Initialize Terraform (required before validation)
    init_result = subprocess.run(
        ["terraform", "init", "-no-color"],
        capture_output=True, text=True
    )
    
    if init_result.returncode != 0:
        return {
            "success": False, 
            "stage": "init", 
            "output": init_result.stderr
        }
    
    # Validate the Terraform code
    validate_result = subprocess.run(
        ["terraform", "validate", "-no-color"],
        capture_output=True, text=True
    )
    
    # Check if validation was successful
    if validate_result.returncode != 0:
        return {
            "success": False, 
            "stage": "validate", 
            "output": validate_result.stderr
        }
    
    # Generate execution plan (dry run)
    plan_result = subprocess.run(
        ["terraform", "plan", "-no-color"],
        capture_output=True, text=True
    )
    
    return {
        "success": True,
        "init_output": init_result.stdout,
        "validate_output": validate_result.stdout,
        "plan_output": plan_result.stdout
    }

@app.post("/deploy")
async def deploy_terraform():
    # Change to the shared directory
    os.chdir(TERRAFORM_DIR)
    
    # Create required providers file if it doesn't exist
    create_required_providers()
    
    # Initialize if needed
    if not os.path.exists(os.path.join(TERRAFORM_DIR, ".terraform")):
        init_result = subprocess.run(
            ["terraform", "init", "-no-color"],
            capture_output=True, text=True
        )
        if init_result.returncode != 0:
            return {
                "success": False,
                "output": init_result.stderr
            }
    
    # Run terraform apply with auto-approve
    apply_result = subprocess.run(
        ["terraform", "apply", "-auto-approve", "-no-color"],
        capture_output=True, text=True
    )
    
    if apply_result.returncode != 0:
        return {
            "success": False,
            "output": apply_result.stderr
        }
    
    return {
        "success": True,
        "output": apply_result.stdout
    }

@app.post("/destroy")
async def destroy_terraform():
    # Change to the shared directory
    os.chdir(TERRAFORM_DIR)
    
    # Run terraform destroy with auto-approve
    destroy_result = subprocess.run(
        ["terraform", "destroy", "-auto-approve", "-no-color"],
        capture_output=True, text=True
    )
    
    if destroy_result.returncode != 0:
        return {
            "success": False,
            "output": destroy_result.stderr
        }
    
    return {
        "success": True,
        "output": destroy_result.stdout
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)