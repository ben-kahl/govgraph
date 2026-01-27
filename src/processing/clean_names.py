import boto3
import json
import os

# Configuration
BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0" 
REGION_NAME = "us-east-1"

def get_bedrock_client():
    """Initializes and returns a boto3 Bedrock client."""
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=REGION_NAME
    )

def standardize_name(messy_name):
    """
    Standardizes a vendor name using Amazon Bedrock (Claude 3).
    
    Args:
        messy_name (str): The inconsistent vendor name (e.g., "L.M. Corp").
        
    Returns:
        str: The standardized name (e.g., "Lockheed Martin Corporation").
    """
    client = get_bedrock_client()
    
    prompt = f"""
    You are an expert data analyst specializing in federal procurement.
    Your task is to standardize the following company name to its canonical legal form.
    
    Input Name: "{messy_name}"
    
    Rules:
    1. Return ONLY the standardized name. No explanations, no quotes, no extra text.
    2. Expand common abbreviations (e.g., "Corp" -> "Corporation", "Co" -> "Company", "Inc" -> "Incorporated").
    3. If the name is already standard, return it as is.
    4. If you are unsure, return the input name exactly as provided.
    
    Standardized Name:
    """
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    })
    
    try:
        response = client.invoke_model(
            body=body,
            modelId=BEDROCK_MODEL_ID,
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get("body").read())
        cleaned_name = response_body["content"][0]["text"].strip()
        return cleaned_name
        
    except Exception as e:
        print(f"Error calling Bedrock: {e}")
        return messy_name

if __name__ == "__main__":
    # Test cases
    test_names = [
        "L.M. Corp",
        "Boeing Co.",
        "Amazon Web Svcs",
        "Raytheon Tech"
    ]
    
    print("Running Entity Resolution Tests...")
    for name in test_names:
        clean = standardize_name(name)
        print(f"Original: '{name}' -> Cleaned: '{clean}'")
