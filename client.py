#!/usr/bin/env python3
import requests
import json
import sys
import time

# API endpoint
API_URL = "http://localhost:8000"

def main():
    print("Welcome to the Terraform LLM Assistant")
    print("======================================")
    print("Describe the infrastructure you want to create.")
    print("Type your description and end with EOF on a new line.\n")
    
    # Collect user input
    lines = []
    while True:
        line = input()
        if line == "EOF":
            break
        lines.append(line)
    
    # Join the lines to form the complete description
    description = "\n".join(lines)
    
    # Send the initial request
    print("\nSending request to LLM...\n")
    response = requests.post(
        f"{API_URL}/generate", 
        json={"description": description}
    )
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    
    result = response.json()
    
    # Handle clarification if needed
    while result.get("needs_clarification", False):
        print(f"LLM needs clarification: {result['question']}")
        answer = input("Your answer: ")
        
        # Send clarification
        try:
            response = requests.post(
                f"{API_URL}/clarify", 
                json={"answer": answer}
            )
            
            if response.status_code != 200:
                print(f"Error: {response.text}")
                return
                
            result = response.json()
        except Exception as e:
            print(f"Error sending clarification: {str(e)}")
            return
    
    # Display the generated Terraform code
    print("\nGenerated Terraform Code:")
    print("=========================")
    print(result["terraform_code"])
    
    # Ask if user wants to validate
    validate = input("\nDo you want to validate this code? (y/n): ")
    if validate.lower() == "y":
        print("\nValidating Terraform code...")
        response = requests.post(f"{API_URL}/validate")
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
            
        validate_result = response.json()
        
        if validate_result["success"]:
            print("\nValidation successful!")
            print(validate_result["validate_output"])
            print("\nTerraform Plan:")
            print(validate_result["plan_output"])
            
            # Ask if user wants to deploy
            deploy = input("\nDo you want to deploy this infrastructure? (y/n): ")
            if deploy.lower() == "y":
                print("\nDeploying infrastructure...")
                response = requests.post(f"{API_URL}/deploy")
                
                if response.status_code != 200:
                    print(f"Error: {response.text}")
                    return
                    
                deploy_result = response.json()
                
                if deploy_result["success"]:
                    print("\nDeployment successful!")
                    print(deploy_result["output"])
                else:
                    print("\nDeployment failed:")
                    print(deploy_result["output"])
            
        else:
            print("\nValidation failed:")
            print(validate_result["output"])
            
            # Ask if user wants to regenerate
            regenerate = input("\nDo you want the LLM to fix and regenerate the code? (y/n): ")
            if regenerate.lower() == "y":
                # Here you would implement the regeneration logic
                print("\nRegenerating code...")
                # Call the regenerate endpoint (not implemented in this example)
    
    print("\nThank you for using the Terraform LLM Assistant!")

if __name__ == "__main__":
    main()