import json
import os


class BedrockModelProvider:
    """Amazon Bedrock Converse adapter; credentials come from the AWS credential chain."""

    def __init__(self, client=None):
        import boto3

        self.model_id = os.environ.get("BEDROCK_MODEL_ID")
        if not self.model_id:
            raise ValueError("BEDROCK_MODEL_ID is required for AWS mode")
        self.client = client or boto3.client(
            "bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1")
        )

    def complete_json(self, system: str, prompt: str) -> dict:
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1800, "temperature": 0.1},
        )
        return json.loads(response["output"]["message"]["content"][0]["text"])
