#!/bin/sh
set -eu

: "${AWS_REGION:?Set AWS_REGION}"
: "${BEDROCK_MODEL_ID:?Set BEDROCK_MODEL_ID}"
: "${S3_BUCKET:?Set S3_BUCKET}"
: "${DYNAMODB_TABLE:?Set DYNAMODB_TABLE}"
: "${SQS_QUEUE_URL:?Set SQS_QUEUE_URL}"

printf '%s\n' '1/5 Checking AWS identity (read only)...'
aws sts get-caller-identity --output table
printf '%s\n' '2/5 Checking Bedrock catalog access (no model invocation)...'
aws bedrock list-foundation-models --region "$AWS_REGION" --by-output-modality TEXT \
  --query 'length(modelSummaries)' --output text
printf '%s\n' '3/5 Checking the S3 bucket...'
aws s3api head-bucket --bucket "$S3_BUCKET"
printf '%s\n' '4/5 Checking the DynamoDB table...'
aws dynamodb describe-table --region "$AWS_REGION" --table-name "$DYNAMODB_TABLE" \
  --query 'Table.TableStatus' --output text
printf '%s\n' '5/5 Checking the SQS queue...'
aws sqs get-queue-attributes --region "$AWS_REGION" --queue-url "$SQS_QUEUE_URL" \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text
printf '%s\n' 'AWS read-only preflight passed. No resources were created and no model was invoked.'
