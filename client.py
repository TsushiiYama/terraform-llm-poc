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
    try:
        response = requests.post(
            f"{API_URL}/generate", 
            json={"description": description}
        )
        
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
        
        result = response.json()
    except Exception as e:
        print(f"Error sending request: {str(e)}")
        return
    
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
    if "terraform_code" in result:
        print(result["terraform_code"])
    else:
        print("Error: No Terraform code was generated.")
        if "error" in result:
            print(f"Error details: {result['error']}")
        if "raw_response" in result:
            print("Raw LLM response:")
            print(result["raw_response"])
        return
    
    # Ask if user wants to validate
    validate = input("\nDo you want to validate this code? (y/n): ")
    if validate.lower() == "y":
        print("\nValidating Terraform code...")
        try:
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
                error_message = validate_result.get("output", "")
                print(error_message)
                
                # Ask if user wants to regenerate
                regenerate = input("\nDo you want the LLM to fix and regenerate the code? (y/n): ")
                if regenerate.lower() == "y":
                    print("\nRegenerating code...")
                    try:
                        response = requests.post(
                            f"{API_URL}/regenerate", 
                            json={"error_message": error_message}
                        )
                        
                        if response.status_code != 200:
                            print(f"Error: {response.text}")
                            return
                        
                        result = response.json()
                        
                        if "terraform_code" in result:
                            print("\nRegenerated Terraform Code:")
                            print("============================")
                            print(result["terraform_code"])
                            
                            # Ask if user wants to validate the regenerated code
                            validate_again = input("\nDo you want to validate this code? (y/n): ")
                            if validate_again.lower() == "y":
                                print("\nValidating regenerated Terraform code...")
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
                                    print("\nValidation of regenerated code failed:")
                                    print(validate_result["output"])
                        else:
                            print("Error: Failed to regenerate code.")
                    except Exception as e:
                        print(f"Error during regeneration: {str(e)}")
                        return
        except Exception as e:
            print(f"Error during validation: {str(e)}")
            return
    
    print("\nThank you for using the Terraform LLM Assistant!")

if __name__ == "__main__":
    main()