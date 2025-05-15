from fastapi import FastAPI, HTTPException, Depends
import uvicorn
import subprocess
import os
import json
import re
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel

# Models - Single Responsibility
class ValidationResult(BaseModel):
    success: bool
    stage: Optional[str] = None
    output: Optional[str] = None
    init_output: Optional[str] = None
    validate_output: Optional[str] = None
    plan_output: Optional[str] = None

class DeploymentResult(BaseModel):
    success: bool
    output: str

# Repository interfaces - Dependency Inversion
class IFileRepository(ABC):
    @abstractmethod
    def save_file(self, path: str, content: str) -> None:
        pass
    
    @abstractmethod
    def read_file(self, path: str) -> str:
        pass
    
    @abstractmethod
    def file_exists(self, path: str) -> bool:
        pass

# Commands - Command Pattern
class ICommand(ABC):
    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        pass

# Service interfaces - Open/Closed and Interface Segregation
class IProviderConfigService(ABC):
    @abstractmethod
    def create_required_providers(self, directory: str) -> None:
        pass
    
    @abstractmethod
    def clean_terraform_file(self, file_path: str) -> None:
        pass

class ITerraformExecutor(ABC):
    @abstractmethod
    def init(self, directory: str) -> subprocess.CompletedProcess:
        pass
    
    @abstractmethod
    def validate(self, directory: str) -> subprocess.CompletedProcess:
        pass
    
    @abstractmethod
    def plan(self, directory: str) -> subprocess.CompletedProcess:
        pass
    
    @abstractmethod
    def apply(self, directory: str, auto_approve: bool = True) -> subprocess.CompletedProcess:
        pass
    
    @abstractmethod
    def destroy(self, directory: str, auto_approve: bool = True) -> subprocess.CompletedProcess:
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
    
    def file_exists(self, path: str) -> bool:
        return os.path.exists(path)

# Concrete Service Implementations
class DockerProviderConfigService(IProviderConfigService):
    def create_required_providers(self, directory: str) -> None:
        providers_content = """
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0.0"
    }
  }
}

provider "docker" {
  host = "unix:///var/run/docker.sock"
}
"""
        with open(os.path.join(directory, "required_providers.tf"), "w") as f:
            f.write(providers_content)
    
    def clean_terraform_file(self, file_path: str) -> None:
        try:
            with open(file_path, "r") as f:
                content = f.read()
            
            # Remove any provider blocks
            provider_pattern = r'provider\s+"[^"]+"\s+\{[^}]*\}'
            cleaned_content = re.sub(provider_pattern, '', content)
            
            # Remove any terraform blocks
            terraform_pattern = r'terraform\s+\{[^}]*\}'
            cleaned_content = re.sub(terraform_pattern, '', cleaned_content)
            
            # Fix incorrect resource types
            if 'source "docker_container"' in cleaned_content:
                cleaned_content = cleaned_content.replace('source "docker_container"', 'resource "docker_container"')
            
            # Fix typo in "reresource"
            if 'reresource "docker_container"' in cleaned_content:
                cleaned_content = cleaned_content.replace('reresource "docker_container"', 'resource "docker_container"')
            
            # Fix any other "reresource" typos
            if 'reresource "' in cleaned_content:
                cleaned_content = cleaned_content.replace('reresource "', 'resource "')
            
            # Fix incorrect environment variable syntax
            if 'environment = [' in cleaned_content:
                cleaned_content = cleaned_content.replace('environment = [', 'env = [')
            
            # Save cleaned content back
            with open(file_path, "w") as f:
                f.write(cleaned_content)
        except Exception as e:
            print(f"Error cleaning terraform file: {str(e)}")

class TerraformCommandLineExecutor(ITerraformExecutor):
    def init(self, directory: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["terraform", "init", "-no-color"],
            capture_output=True, text=True,
            cwd=directory
        )
    
    def validate(self, directory: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["terraform", "validate", "-no-color"],
            capture_output=True, text=True,
            cwd=directory
        )
    
    def plan(self, directory: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["terraform", "plan", "-no-color"],
            capture_output=True, text=True,
            cwd=directory
        )
    
    def apply(self, directory: str, auto_approve: bool = True) -> subprocess.CompletedProcess:
        cmd = ["terraform", "apply"]
        if auto_approve:
            cmd.append("-auto-approve")
        cmd.append("-no-color")
        
        return subprocess.run(
            cmd,
            capture_output=True, text=True,
            cwd=directory
        )
    
    def destroy(self, directory: str, auto_approve: bool = True) -> subprocess.CompletedProcess:
        cmd = ["terraform", "destroy"]
        if auto_approve:
            cmd.append("-auto-approve")
        cmd.append("-no-color")
        
        return subprocess.run(
            cmd,
            capture_output=True, text=True,
            cwd=directory
        )

# Command implementations - Command Pattern
class ValidateCommand(ICommand):
    def __init__(
        self, 
        terraform_dir: str,
        provider_service: IProviderConfigService,
        terraform_executor: ITerraformExecutor
    ):
        self.terraform_dir = terraform_dir
        self.provider_service = provider_service
        self.terraform_executor = terraform_executor
    
    def execute(self) -> Dict[str, Any]:
        # Create required providers file
        self.provider_service.create_required_providers(self.terraform_dir)
        
        # Clean the main.tf file
        self.provider_service.clean_terraform_file(os.path.join(self.terraform_dir, "main.tf"))
        
        # Initialize Terraform
        init_result = self.terraform_executor.init(self.terraform_dir)
        
        if init_result.returncode != 0:
            return ValidationResult(
                success=False,
                stage="init",
                output=init_result.stderr
            ).dict()
        
        # Validate the Terraform code
        validate_result = self.terraform_executor.validate(self.terraform_dir)
        
        if validate_result.returncode != 0:
            return ValidationResult(
                success=False,
                stage="validate",
                output=validate_result.stderr
            ).dict()
        
        # Generate execution plan (dry run)
        plan_result = self.terraform_executor.plan(self.terraform_dir)
        
        return ValidationResult(
            success=True,
            init_output=init_result.stdout,
            validate_output=validate_result.stdout,
            plan_output=plan_result.stdout
        ).dict()

class DeployCommand(ICommand):
    def __init__(
        self, 
        terraform_dir: str,
        provider_service: IProviderConfigService,
        terraform_executor: ITerraformExecutor,
        file_repository: IFileRepository
    ):
        self.terraform_dir = terraform_dir
        self.provider_service = provider_service
        self.terraform_executor = terraform_executor
        self.file_repository = file_repository
    
    def execute(self) -> Dict[str, Any]:
        # Create required providers file if it doesn't exist
        self.provider_service.create_required_providers(self.terraform_dir)
        
        # Clean the main.tf file
        self.provider_service.clean_terraform_file(os.path.join(self.terraform_dir, "main.tf"))
        
        # Initialize if needed
        terraform_dir = os.path.join(self.terraform_dir, ".terraform")
        if not self.file_repository.file_exists(terraform_dir):
            init_result = self.terraform_executor.init(self.terraform_dir)
            if init_result.returncode != 0:
                return DeploymentResult(
                    success=False,
                    output=init_result.stderr
                ).dict()
        
        # Run terraform apply
        apply_result = self.terraform_executor.apply(self.terraform_dir)
        
        if apply_result.returncode != 0:
            return DeploymentResult(
                success=False,
                output=apply_result.stderr
            ).dict()
        
        return DeploymentResult(
            success=True,
            output=apply_result.stdout
        ).dict()

class DestroyCommand(ICommand):
    def __init__(
        self, 
        terraform_dir: str,
        terraform_executor: ITerraformExecutor
    ):
        self.terraform_dir = terraform_dir
        self.terraform_executor = terraform_executor
    
    def execute(self) -> Dict[str, Any]:
        # Run terraform destroy
        destroy_result = self.terraform_executor.destroy(self.terraform_dir)
        
        if destroy_result.returncode != 0:
            return DeploymentResult(
                success=False,
                output=destroy_result.stderr
            ).dict()
        
        return DeploymentResult(
            success=True,
            output=destroy_result.stdout
        ).dict()

# Service Factory - Factory pattern for dependency injection
class ServiceFactory:
    @staticmethod
    def get_file_repository() -> IFileRepository:
        return FileSystemRepository()
    
    @staticmethod
    def get_provider_config_service() -> IProviderConfigService:
        return DockerProviderConfigService()
    
    @staticmethod
    def get_terraform_executor() -> ITerraformExecutor:
        return TerraformCommandLineExecutor()
    
    @staticmethod
    def get_validate_command(terraform_dir: str) -> ICommand:
        return ValidateCommand(
            terraform_dir,
            ServiceFactory.get_provider_config_service(),
            ServiceFactory.get_terraform_executor()
        )
    
    @staticmethod
    def get_deploy_command(terraform_dir: str) -> ICommand:
        return DeployCommand(
            terraform_dir,
            ServiceFactory.get_provider_config_service(),
            ServiceFactory.get_terraform_executor(),
            ServiceFactory.get_file_repository()
        )
    
    @staticmethod
    def get_destroy_command(terraform_dir: str) -> ICommand:
        return DestroyCommand(
            terraform_dir,
            ServiceFactory.get_terraform_executor()
        )

# Dependency Injection Container
def get_validate_command(terraform_dir: str = "/shared") -> ICommand:
    return ServiceFactory.get_validate_command(terraform_dir)

def get_deploy_command(terraform_dir: str = "/shared") -> ICommand:
    return ServiceFactory.get_deploy_command(terraform_dir)

def get_destroy_command(terraform_dir: str = "/shared") -> ICommand:
    return ServiceFactory.get_destroy_command(terraform_dir)

# FastAPI Application
app = FastAPI()

@app.post("/validate")
async def validate_terraform(command: ICommand = Depends(get_validate_command)):
    return command.execute()

@app.post("/deploy")
async def deploy_terraform(command: ICommand = Depends(get_deploy_command)):
    return command.execute()

@app.post("/destroy")
async def destroy_terraform(command: ICommand = Depends(get_destroy_command)):
    return command.execute()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)