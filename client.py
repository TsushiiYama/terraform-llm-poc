#!/usr/bin/env python3
import sys
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests

# Models - Single Responsibility
class InfrastructureRequest:
    def __init__(self, description: str):
        self.description = description

class TerraformCode:
    def __init__(self, code: str, needs_clarification: bool = False, question: str = ""):
        self.code = code
        self.needs_clarification = needs_clarification
        self.question = question

class ValidationResult:
    def __init__(self, success: bool, output: str, plan_output: str = ""):
        self.success = success
        self.output = output
        self.plan_output = plan_output

class DeploymentResult:
    def __init__(self, success: bool, output: str):
        self.success = success
        self.output = output

# Service Interfaces - Dependency Inversion & Interface Segregation
class IUserInterface(ABC):
    @abstractmethod
    def display_welcome(self) -> None:
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        pass
    
    @abstractmethod
    def display_code(self, code: str) -> None:
        pass
    
    @abstractmethod
    def ask_for_clarification(self, question: str) -> str:
        pass
    
    @abstractmethod
    def confirm_action(self, message: str) -> bool:
        pass
    
    @abstractmethod
    def display_info(self, message: str) -> None:
        pass
    
    @abstractmethod
    def display_error(self, message: str) -> None:
        pass
    
    @abstractmethod
    def display_success(self, message: str) -> None:
        pass

class IApiClient(ABC):
    @abstractmethod
    def generate_terraform(self, description: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def clarify(self, answer: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def validate(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def deploy(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def regenerate(self, error_message: str) -> Dict[str, Any]:
        pass

# Concrete Implementations
class ConsoleUserInterface(IUserInterface):
    def display_welcome(self) -> None:
        print("Welcome to the Terraform LLM Assistant")
        print("======================================")
        print("Describe the infrastructure you want to create.")
        print("Type your description and end with EOF on a new line.\n")
    
    def get_description(self) -> str:
        lines = []
        while True:
            try:
                line = input()
                if line == "EOF":
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)
    
    def display_code(self, code: str) -> None:
        print("\nGenerated Terraform Code:")
        print("=========================")
        print(code)
    
    def ask_for_clarification(self, question: str) -> str:
        print(f"LLM needs clarification: {question}")
        return input("Your answer: ")
    
    def confirm_action(self, message: str) -> bool:
        response = input(f"\n{message} (y/n): ")
        return response.lower() == "y"
    
    def display_info(self, message: str) -> None:
        print(message)
    
    def display_error(self, message: str) -> None:
        print(f"Error: {message}")
    
    def display_success(self, message: str) -> None:
        print(f"\nSuccess: {message}")

class TerraformApiClient(IApiClient):
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def generate_terraform(self, description: str) -> Dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}/generate",
                json={"description": description}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Error generating Terraform code: {str(e)}")
    
    def clarify(self, answer: str) -> Dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}/clarify",
                json={"answer": answer}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Error sending clarification: {str(e)}")
    
    def validate(self) -> Dict[str, Any]:
        try:
            response = requests.post(f"{self.base_url}/validate")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Error validating Terraform code: {str(e)}")
    
    def deploy(self) -> Dict[str, Any]:
        try:
            response = requests.post(f"{self.base_url}/deploy")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Error deploying infrastructure: {str(e)}")
    
    def regenerate(self, error_message: str) -> Dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}/regenerate",
                json={"error_message": error_message}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Error regenerating Terraform code: {str(e)}")

# Command Pattern
class ICommand(ABC):
    @abstractmethod
    def execute(self) -> None:
        pass

class GenerateCommand(ICommand):
    def __init__(self, ui: IUserInterface, api_client: IApiClient):
        self.ui = ui
        self.api_client = api_client
    
    def execute(self) -> TerraformCode:
        # Get infrastructure description
        description = self.ui.get_description()
        
        # Request code generation
        self.ui.display_info("\nSending request to LLM...\n")
        result = self.api_client.generate_terraform(description)
        
        # Handle clarification if needed
        while result.get("needs_clarification", False):
            answer = self.ui.ask_for_clarification(result["question"])
            result = self.api_client.clarify(answer)
        
        # Return the generated code
        if "terraform_code" in result:
            return TerraformCode(result["terraform_code"])
        else:
            error_message = "No Terraform code was generated."
            if "error" in result:
                error_message += f" Error details: {result['error']}"
            self.ui.display_error(error_message)
            
            if "raw_response" in result:
                self.ui.display_info("Raw LLM response:")
                self.ui.display_info(result["raw_response"])
            
            return TerraformCode("")

class ValidateCommand(ICommand):
    def __init__(self, ui: IUserInterface, api_client: IApiClient):
        self.ui = ui
        self.api_client = api_client
    
    def execute(self) -> ValidationResult:
        self.ui.display_info("\nValidating Terraform code...")
        result = self.api_client.validate()
        
        if result["success"]:
            return ValidationResult(
                True, 
                result["validate_output"],
                result["plan_output"]
            )
        else:
            return ValidationResult(
                False,
                result.get("output", "Unknown validation error")
            )

class DeployCommand(ICommand):
    def __init__(self, ui: IUserInterface, api_client: IApiClient):
        self.ui = ui
        self.api_client = api_client
    
    def execute(self) -> DeploymentResult:
        self.ui.display_info("\nDeploying infrastructure...")
        result = self.api_client.deploy()
        
        if result["success"]:
            return DeploymentResult(True, result["output"])
        else:
            return DeploymentResult(False, result["output"])

class RegenerateCommand(ICommand):
    def __init__(self, ui: IUserInterface, api_client: IApiClient, error_message: str):
        self.ui = ui
        self.api_client = api_client
        self.error_message = error_message
    
    def execute(self) -> TerraformCode:
        self.ui.display_info("\nRegenerating code...")
        result = self.api_client.regenerate(self.error_message)
        
        if "terraform_code" in result:
            return TerraformCode(result["terraform_code"])
        else:
            self.ui.display_error("Failed to regenerate code.")
            return TerraformCode("")

# Facade Pattern - Simplifies the interaction with the system
class TerraformLLMAssistant:
    def __init__(self, ui: IUserInterface, api_client: IApiClient):
        self.ui = ui
        self.api_client = api_client
    
    def run(self) -> None:
        # Welcome user
        self.ui.display_welcome()
        
        # Generate initial code
        generate_command = GenerateCommand(self.ui, self.api_client)
        terraform_code = generate_command.execute()
        
        if not terraform_code.code:
            return
        
        # Display the generated code
        self.ui.display_code(terraform_code.code)
        
        # Ask if user wants to validate
        if self.ui.confirm_action("Do you want to validate this code?"):
            validate_command = ValidateCommand(self.ui, self.api_client)
            validation_result = validate_command.execute()
            
            if validation_result.success:
                self.ui.display_success("Validation successful!")
                self.ui.display_info(validation_result.output)
                self.ui.display_info("\nTerraform Plan:")
                self.ui.display_info(validation_result.plan_output)
                
                # Ask if user wants to deploy
                if self.ui.confirm_action("Do you want to deploy this infrastructure?"):
                    deploy_command = DeployCommand(self.ui, self.api_client)
                    deployment_result = deploy_command.execute()
                    
                    if deployment_result.success:
                        self.ui.display_success("Deployment successful!")
                        self.ui.display_info(deployment_result.output)
                    else:
                        self.ui.display_error("Deployment failed:")
                        self.ui.display_info(deployment_result.output)
            else:
                self.ui.display_error("Validation failed:")
                self.ui.display_info(validation_result.output)
                
                # Ask if user wants to regenerate
                if self.ui.confirm_action("Do you want the LLM to fix and regenerate the code?"):
                    regenerate_command = RegenerateCommand(self.ui, self.api_client, validation_result.output)
                    regenerated_code = regenerate_command.execute()
                    
                    if regenerated_code.code:
                        self.ui.display_code(regenerated_code.code)
                        
                        # Ask if user wants to validate the regenerated code
                        if self.ui.confirm_action("Do you want to validate this code?"):
                            validate_command = ValidateCommand(self.ui, self.api_client)
                            validation_result = validate_command.execute()
                            
                            if validation_result.success:
                                self.ui.display_success("Validation successful!")
                                self.ui.display_info(validation_result.output)
                                self.ui.display_info("\nTerraform Plan:")
                                self.ui.display_info(validation_result.plan_output)
                                
                                # Ask if user wants to deploy
                                if self.ui.confirm_action("Do you want to deploy this infrastructure?"):
                                    deploy_command = DeployCommand(self.ui, self.api_client)
                                    deployment_result = deploy_command.execute()
                                    
                                    if deployment_result.success:
                                        self.ui.display_success("Deployment successful!")
                                        self.ui.display_info(deployment_result.output)
                                    else:
                                        self.ui.display_error("Deployment failed:")
                                        self.ui.display_info(deployment_result.output)
                            else:
                                self.ui.display_error("Validation of regenerated code failed:")
                                self.ui.display_info(validation_result.output)
        
        self.ui.display_info("\nThank you for using the Terraform LLM Assistant!")

# Main function
def main():
    # Create dependencies
    ui = ConsoleUserInterface()
    api_client = TerraformApiClient()
    
    # Create and run the assistant
    assistant = TerraformLLMAssistant(ui, api_client)
    
    try:
        assistant.run()
    except Exception as e:
        ui.display_error(str(e))
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())