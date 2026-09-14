# AWS setup: baby steps

This guide takes QuantumListener from a laptop to one Amazon EC2 virtual machine. It deliberately separates **read-only checks**, **resource creation**, and **deployment** so nothing billable is created by surprise.

> AWS names and screens evolve. The commands below are reproducible, but confirm current service availability and pricing in your selected region. The repository never needs an AWS access key on the VM: EC2 receives temporary credentials through an instance profile.

## What you will build

```text
Browser -> EC2 public DNS -> Nginx -> Flask API / static site
                                  -> Strands Weekly Editor -> Amazon Bedrock
                                  -> Amazon Polly
EventBridge Scheduler -> SQS -> worker
DynamoDB stores records and locks; S3 stores podcast assets
```

For a first smoke test, stop after Step 8. Do not enable the weekly schedule until the manual run works and you understand the cost ceilings.

## Step 0 — choose names and a region

Use one AWS region for the first deployment. `us-east-1` is shown only as an example; choose a region where your desired Bedrock model and Polly voice are available.

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export QL_TABLE=quantumlistener
export QL_BUCKET="quantumlistener-media-${AWS_ACCOUNT_ID}-${AWS_REGION}"
export QL_QUEUE=quantumlistener-weekly
```

Confirm that `AWS_ACCOUNT_ID` prints your account number. If this command fails, install AWS CLI v2 and authenticate your administrator/deployment shell before continuing.

## Step 1 — select a Bedrock model

1. In the AWS console, switch to `$AWS_REGION` and open **Amazon Bedrock**.
2. Open **Model catalog** and choose a text model that supports on-demand invocation in that region.
3. Complete any provider access or use-case form that the console requests.
4. Copy the exact model ID or inference-profile ID; do not guess it.
5. Check visibility from your shell:

```bash
aws bedrock list-foundation-models \
  --region "$AWS_REGION" \
  --by-output-modality TEXT \
  --query 'modelSummaries[].{name:modelName,id:modelId}' \
  --output table

export BEDROCK_MODEL_ID='<copy the enabled model or inference-profile ID>'
```

QuantumListener passes this value to the Strands `BedrockModel`; the repository has no hardcoded model. A model appearing in the catalog does not necessarily prove your role can invoke it, so Step 8 performs the real application check.

## Step 2 — create private storage

Create one private, encrypted S3 bucket. Public access remains blocked; Nginx serves the local MVP, while a later deployment can proxy or sign only published assets.

```bash
aws s3api create-bucket \
  --bucket "$QL_BUCKET" \
  --region "$AWS_REGION" \
  $( [ "$AWS_REGION" = us-east-1 ] || printf '%s' "--create-bucket-configuration LocationConstraint=$AWS_REGION" )
aws s3api put-public-access-block --bucket "$QL_BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$QL_BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

Create the DynamoDB single table with on-demand billing:

```bash
aws dynamodb create-table \
  --region "$AWS_REGION" \
  --table-name "$QL_TABLE" \
  --attribute-definitions AttributeName=PK,AttributeType=S AttributeName=SK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
aws dynamodb wait table-exists --region "$AWS_REGION" --table-name "$QL_TABLE"
```

The key layout and atomic publication pointer are documented in `docs/DATA_MODEL.md`.

## Step 3 — create SQS and its dead-letter queue

The checked-in CloudFormation template creates both queues but does not start a schedule:

```bash
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name quantumlistener-queues \
  --template-file deployment/sqs/cloudformation.yaml
export SQS_QUEUE_URL="$(aws sqs get-queue-url \
  --region "$AWS_REGION" --queue-name "$QL_QUEUE" --query QueueUrl --output text)"
```

Leave EventBridge Scheduler for Step 10. The worker can otherwise begin polling immediately and incur requests.

## Step 4 — create the EC2 role (no access keys)

In **IAM → Roles → Create role**:

1. Select **AWS service**, then **EC2**.
2. Name the role `QuantumListenerEc2Role`.
3. Attach `AmazonSSMManagedInstanceCore` so you can use Session Manager without opening SSH.
4. Create an inline policy from `deployment/iam/runtime-policy.json` after replacing:
   - `REPLACE_BUCKET` with `$QL_BUCKET`;
   - the DynamoDB table and SQS ARNs if you changed their default names.
5. Restrict the Bedrock `Resource` entry to the selected model or inference profile where the model supports resource-level permissions.
6. Create an instance profile for the role if the console did not do so automatically.

Do **not** put `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in `.env.production`.

> IAM action-name note: `TransactWriteItems` is a DynamoDB API operation, but its transaction members authorize through item actions such as `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem`, and `dynamodb:ConditionCheckItem`; it is not an IAM action to paste into a policy. Likewise, S3 `HeadObject` requests authorize with `s3:GetObject`, so `s3:HeadObject` is not an IAM action. The checked-in policy uses the authorization actions rather than the API operation names.

## Step 5 — launch the EC2 virtual machine

The simplest console path is **EC2 → Instances → Launch instances**:

1. **Name:** `quantumlistener`.
2. **AMI:** current Amazon Linux 2023 for your architecture.
3. **Instance type:** start with `t3.medium` for x86_64. This is a configurable starting point, not a claim about the old Google VM.
4. **Key pair:** optional if using Session Manager; otherwise create and protect one.
5. **Network:** select your VPC and a public subnet. Enable a public IPv4 address for this direct MVP path.
6. **Security group:** allow inbound TCP 80 from your demo audience. If using SSH, allow TCP 22 only from your own IP. Never expose application port 8080 directly.
7. **Storage:** 30 GiB encrypted gp3 is a reasonable configurable starting point because Docker layers and audio segments consume disk.
8. **Advanced details → IAM instance profile:** select the profile containing `QuantumListenerEc2Role`.
9. Launch the instance. EC2, storage, public IPv4, and data transfer can incur charges.

The alternative CloudFormation starting point is `deployment/ec2/cloudformation.yaml`; review every parameter before deploying it.

## Step 6 — connect and install Docker

Connect with **EC2 Instance Connect** or **Systems Manager → Session Manager**, then run:

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
sudo mkdir -p /opt/quantumlistener
sudo chown ec2-user:ec2-user /opt/quantumlistener
```

Sign out and back in after changing group membership. Confirm:

```bash
docker version
if ! docker compose version; then
  sudo dnf install -y docker-compose-plugin
fi
docker compose version
```

If the Compose plugin is not present in your current Amazon Linux repositories, install the official Docker Compose plugin appropriate for that operating system before proceeding.

### If `docker compose -f ...` says `unknown shorthand flag: 'f'`

This error means the Docker Engine is installed but the **Compose v2 CLI plugin is not**. The `-f` flag belongs to Compose; without the plugin, the base `docker` command receives it and rejects it.

Check which command exists:

```bash
docker compose version
docker-compose version
```

Use the first applicable fix:

1. If `docker compose version` works, rerun the original command.
2. If only `docker-compose version` works, use:

   ```bash
   docker-compose -f docker-compose.production.yml up -d --build
   ```

3. If neither works, try the Amazon Linux package and verify it:

   ```bash
   sudo dnf install -y docker-compose-plugin
   docker compose version
   ```

4. If `dnf` reports that the package is unavailable, install the current Docker Compose CLI plugin using [Docker's official Linux plugin instructions](https://docs.docker.com/compose/install/linux/#install-the-plugin-manually). Choose the binary matching `uname -m`, install it in `/usr/local/lib/docker/cli-plugins/docker-compose`, make it executable, and rerun `docker compose version`. Do not paste an unverified third-party binary or an old version copied from a blog.

QuantumListener also provides a compatibility wrapper that automatically chooses Compose v2 or the legacy `docker-compose` executable:

```bash
./scripts/compose.sh -f docker-compose.production.yml up -d --build
```

If neither implementation is installed, the wrapper exits with installation guidance instead of the confusing `-f` error.


## Step 7 — deploy the repository and environment

From your laptop, set the VM public DNS and copy the repository:

```bash
export EC2_HOST=ec2-203-0-113-10.compute-1.amazonaws.com
export EC2_USER=ec2-user
./scripts/deploy_aws.sh
```

Alternatively clone the repository directly into `/opt/quantumlistener`. On the VM create `/opt/quantumlistener/.env.production`:

```dotenv
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=<exact enabled model or inference-profile ID>
S3_BUCKET=<your private bucket>
DYNAMODB_TABLE=quantumlistener
SQS_QUEUE_URL=<your queue URL>
PUBLIC_SITE_URL=http://<EC2_PUBLIC_DNS>
PODCAST_OWNER_EMAIL=<your podcast contact>
POLLY_VOICE_ID=Joanna
POLLY_ENGINE=neural
MAX_BEDROCK_CALLS=50
MAX_POLLY_CHARACTERS=50000
MAX_RUN_COST_USD=10
ADMIN_TOKEN=<generate a long random value outside Git>
QUANTUMLISTENER_DATA=/var/lib/quantumlistener
```

Protect it and start the stack:

```bash
cd /opt/quantumlistener
chmod 600 .env.production
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=100 backend
```

Open `http://EC2_PUBLIC_DNS/`. Add HTTPS through an Application Load Balancer or an audited Nginx certificate before treating this as a public production service.

## Step 8 — understand and test Strands Agents

The production agent is created only when `--aws` is used. `WeeklyEditor`:

1. loads `BEDROCK_MODEL_ID`;
2. constructs a Strands `BedrockModel` in `AWS_REGION`;
3. registers `category_editor` and `evidence_editor` tools;
4. gives Strands a grounding/delegation system prompt;
5. invokes the Strands loop for every paper;
6. caps calls with `MAX_BEDROCK_CALLS`;
7. records tool names/statuses without recording chain-of-thought.

First prove the deterministic workflow without AWS calls:

```bash
docker compose -f docker-compose.production.yml exec backend \
  python -m scripts.run_digest --fixture --dry-run
```

Then run a small fixture through **Strands + Bedrock + Polly**:

```bash
docker compose -f docker-compose.production.yml exec backend \
  python -m scripts.run_digest --fixture --aws --approve
```

Watch the concise activity log:

```bash
docker compose -f docker-compose.production.yml logs -f backend worker
```

Common errors:

- `BEDROCK_MODEL_ID is required`: add the exact ID to `.env.production` and recreate the containers.
- `AccessDeniedException`: confirm the instance profile, region, provider access, model/inference-profile ARN, and `bedrock:InvokeModel` permission.
- Polly access denied: add `polly:SynthesizeSpeech` to the instance role.
- No credentials: confirm an IAM role is attached with `aws sts get-caller-identity` from the VM; do not solve it by adding static keys.

## Step 9 — publish and verify

The workflow pauses for human approval by default. For the fixed fixture week:

```bash
docker compose -f docker-compose.production.yml exec backend \
  python -m scripts.publish_episode 2026-W37
curl -fsS http://localhost/api/v1/episodes/current | python -m json.tool
curl -fsS http://localhost/feed.xml | head
```

For a current live arXiv run, omit `--fixture`. Review the paper count, evidence warnings, character limit, and estimated model use before approval.

## Step 10 — add weekly scheduling last

Only after the manual workflow succeeds:

1. Create a Scheduler execution role allowed to call `sqs:SendMessage` on the weekly queue.
2. Obtain the queue ARN.
3. Deploy `deployment/eventbridge/cloudformation.yaml` with `QueueArn` and `SchedulerRoleArn`.
4. Inspect the schedule expression and timezone behavior.
5. Change the schedule state from `DISABLED` to `ENABLED` explicitly.
6. Send one test SQS message and confirm the worker deletes it only after a successful run.

## Step 11 — read-only preflight

After setting the environment variables, run:

```bash
./scripts/check_aws_setup.sh
```

It checks identity, Bedrock catalog visibility, S3, DynamoDB, and SQS without creating, deleting, or updating resources. It does not invoke a paid model or synthesize paid speech.

## Cleanup when the demo is over

Disable Scheduler first, stop the EC2 instance when not needed, and inspect S3/EBS retention before deletion. CloudFormation stacks, buckets containing objects, DynamoDB tables, public IPv4 addresses, and retained logs may need separate cleanup. Back up published episodes before deleting anything. No cleanup command is automated in this repository.
