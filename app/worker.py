import json
import os
import time


def main():
    import boto3

    queue = os.environ["SQS_QUEUE_URL"]
    sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "us-east-1"))
    while True:
        response = sqs.receive_message(QueueUrl=queue, WaitTimeSeconds=20, MaxNumberOfMessages=1)
        for message in response.get("Messages", []):
            payload = json.loads(message["Body"])
            os.system(
                f"python -m scripts.run_digest {'--fixture' if payload.get('fixture') else ''}"
            )
            sqs.delete_message(QueueUrl=queue, ReceiptHandle=message["ReceiptHandle"])
        time.sleep(1)


if __name__ == "__main__":
    main()
