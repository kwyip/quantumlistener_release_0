# AWS Console setup — no local AWS CLI required

This walkthrough uses the **AWS Management Console** and its browser-based **CloudShell**. You only need a local terminal if you prefer it. It creates billable resources, so read each confirmation screen and use one region throughout.

## Before clicking Create

Write these values down:

| Setting | Suggested first-demo value |
|---|---|
| Region | A region where your chosen Bedrock model and Polly voice are available |
| DynamoDB table | `quantumlistener` |
| S3 bucket | `quantumlistener-media-ACCOUNT-REGION` |
| SQS queue | `quantumlistener-weekly` |
| Dead-letter queue | `quantumlistener-dlq` |
| EC2 type | `t3.medium` on x86_64 |
| EC2 disk | 30 GiB encrypted gp3 |
| EC2 role | `QuantumListenerEc2Role` |

The instance type is a starting point, not a known equivalent of the old Google VM. Open the AWS Billing console first and create a small monthly budget with email alerts if you do not already have one.

## 1. Pick one region

1. Sign in to the AWS Management Console.
2. Use the region selector at the upper right.
3. Pick a region and keep every service in that region.
4. Record it as `AWS_REGION`—for example, `us-east-1`.

## 2. Select the Bedrock model

1. Search for **Amazon Bedrock**.
2. Open **Model catalog**.
3. Filter for text/chat models.
4. Choose a model that shows support in your selected region.
5. Complete any provider access or use-case form shown by Bedrock.
6. Copy the exact **model ID** or **inference profile ID**. Save it as `BEDROCK_MODEL_ID`.
7. If the console offers a playground, send one very small test prompt. This may be billable, but it distinguishes model-access problems from application problems.

Do not copy an example model ID from documentation. Model availability, access, and inference-profile requirements vary by region and account.

## 3. Create a private S3 bucket

1. Search for **S3** and choose **Create bucket**.
2. Enter a globally unique name, such as `quantumlistener-media-ACCOUNT-REGION`.
3. Confirm the selected AWS region.
4. Leave **Block all public access** enabled.
5. Leave bucket versioning disabled for the lowest-cost MVP, or enable it if rollback history is worth the additional storage.
6. Under default encryption, choose **Amazon S3 managed keys (SSE-S3)**.
7. Choose **Create bucket**.
8. Open the new bucket and record its name as `S3_BUCKET`.

Do not upload prompts, secrets, or private intermediate files to a public prefix. QuantumListener drafts should remain private.

## 4. Create the DynamoDB table

1. Search for **DynamoDB**.
2. Choose **Tables → Create table**.
3. Table name: `quantumlistener`.
4. Partition key: `PK`, type **String**.
5. Sort key: `SK`, type **String**.
6. Under table settings, choose **Customize settings**.
7. Select **On-demand** capacity for the MVP.
8. Keep encryption enabled with the AWS-owned key unless your policy requires a customer-managed key.
9. Choose **Create table** and wait for status **Active**.
10. Record the name as `DYNAMODB_TABLE`.

QuantumListener uses the same table for paper versions, agent runs, locks, episodes, chapters, claims, corrections, and the atomic publication pointer.

## 5. Create SQS queues

Create the dead-letter queue first:

1. Search for **Simple Queue Service** or **SQS**.
2. Choose **Create queue → Standard**.
3. Name it `quantumlistener-dlq`.
4. Set message retention to 14 days.
5. Create the queue.

Then create the weekly queue:

1. Choose **Create queue → Standard**.
2. Name it `quantumlistener-weekly`.
3. Set visibility timeout to 15 minutes for the first deployment.
4. Expand **Dead-letter queue** and enable it.
5. Select `quantumlistener-dlq` and set maximum receives to `3`.
6. Create the queue.
7. Open it and copy both its **URL** (`SQS_QUEUE_URL`) and **ARN**.

Do not send a message yet—the worker should not run before the EC2 role and configuration exist.

## 6. Create the EC2 IAM role

1. Search for **IAM**.
2. Choose **Roles → Create role**.
3. Trusted entity: **AWS service**.
4. Use case: **EC2**.
5. Attach `AmazonSSMManagedInstanceCore` so you can connect through the browser without exposing SSH.
6. Name the role `QuantumListenerEc2Role` and create it.
7. Open the role and choose **Add permissions → Create inline policy → JSON**.
8. Paste `deployment/iam/runtime-policy.json` from the repository.
9. Replace `REPLACE_BUCKET` with your actual S3 bucket name.
10. If you changed the default DynamoDB or SQS names, update those ARNs too.
11. Name the policy `QuantumListenerRuntime` and save it.

For a first test, the checked-in policy permits Bedrock invocation broadly because the selected model is configurable. Before public production, restrict it to your model or inference-profile ARN wherever Bedrock supports resource-level restriction.

Never create an IAM user access key for the VM. The EC2 role supplies short-lived credentials automatically.

> IAM action-name note: `TransactWriteItems` is a DynamoDB API operation, but its transaction members authorize through item actions such as `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem`, and `dynamodb:ConditionCheckItem`; it is not an IAM action to paste into a policy. Likewise, S3 `HeadObject` requests authorize with `s3:GetObject`, so `s3:HeadObject` is not an IAM action. The checked-in policy uses the authorization actions rather than the API operation names.

## 7. Launch the EC2 virtual machine

1. Search for **EC2**.
2. Choose **Instances → Launch instances**.
3. Name: `quantumlistener`.
4. Application and OS image: current **Amazon Linux 2023**.
5. Architecture: **64-bit (x86)** for the simplest first run.
6. Instance type: `t3.medium`.
7. Key pair: choose **Proceed without a key pair** if you will use Session Manager; otherwise create one and store it securely.
8. Under network settings:
   - choose a VPC and public subnet;
   - enable auto-assign public IPv4;
   - create a security group named `quantumlistener-web`;
   - allow HTTP TCP 80 from `0.0.0.0/0` only when you are ready for public demo access;
   - do not expose port 8080;
   - add SSH 22 only from **My IP** if you need SSH.
9. Configure 30 GiB **gp3**, encrypted.
10. Expand **Advanced details** and select `QuantumListenerEc2Role` as the IAM instance profile.
11. Choose **Launch instance**.
12. Wait for both instance status checks to pass.

EC2, EBS, public IPv4, and outbound data can incur charges while the instance exists or runs.

## 8. Connect entirely in the browser

1. Select the instance in EC2.
2. Choose **Connect**.
3. Select **Session Manager**.
4. Choose **Connect**.

If Session Manager says the instance is not connected, verify that the role includes `AmazonSSMManagedInstanceCore`, the instance has outbound internet/NAT access, and the SSM agent is running.

In the browser terminal:

```bash
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
sudo mkdir -p /opt/quantumlistener
sudo chown ec2-user:ec2-user /opt/quantumlistener
```

Reconnect the Session Manager terminal so group membership refreshes. Then check:

```bash
docker version
if ! docker compose version; then
  sudo dnf install -y docker-compose-plugin
fi
docker compose version
aws sts get-caller-identity
```

The final command should show the EC2 role, not an IAM user.

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


## 9. Put the code on EC2

### Option A — browser terminal and GitHub

In Session Manager:

```bash
cd /opt
git clone <YOUR_QUANTUMLISTENER_REPOSITORY_URL> quantumlistener
cd quantumlistener
```

For a private repository, use a short-lived GitHub credential or an approved deploy key. Do not put it in the application environment file.

### Option B — CloudShell and S3 transfer

Use the **CloudShell** icon in the console header to open a browser shell. Package the repository there, upload it to a private S3 deployment key, and use the instance role to download it. Delete the deployment archive after extraction. Do not make it public.

## 10. Create the application environment file

In the Session Manager terminal:

```bash
cd /opt/quantumlistener
cp .env.production.example .env.production
python -c 'import secrets; print(secrets.token_urlsafe(48))'
nano .env.production
```

Fill in:

```dotenv
AWS_REGION=<the one selected console region>
BEDROCK_MODEL_ID=<exact model or inference-profile ID>
S3_BUCKET=<bucket name>
DYNAMODB_TABLE=quantumlistener
SQS_QUEUE_URL=<weekly queue URL>
PUBLIC_SITE_URL=http://<EC2-public-DNS>
PODCAST_OWNER_EMAIL=<contact address>
POLLY_VOICE_ID=Joanna
POLLY_ENGINE=neural
MAX_BEDROCK_CALLS=50
MAX_POLLY_CHARACTERS=50000
MAX_RUN_COST_USD=10
ADMIN_TOKEN=<paste the generated random value>
QUANTUMLISTENER_DATA=/var/lib/quantumlistener
```

Save the file and protect it:

```bash
chmod 600 .env.production
```

There should be no AWS access key, secret key, Bedrock bearer token, or GitHub credential in this file.

## 11. Start the application

```bash
cd /opt/quantumlistener
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=100 backend
```

Open the EC2 instance details page, copy **Public IPv4 DNS**, and visit:

```text
http://EC2-PUBLIC-DNS/
```

If it does not open, check the Nginx container logs, the port-80 security-group rule, and the Compose service status.

## 12. Prove local behavior before using Bedrock

Run the deterministic fixture without AWS generation:

```bash
docker compose -f docker-compose.production.yml exec backend \
  python -m scripts.run_digest --fixture --dry-run
```

This should report five papers and require no model or speech charge.

## 13. Run the Strands Agent

QuantumListener creates the Strands agent only in `--aws` mode. The Weekly Editor constructs a Strands `BedrockModel`, registers category and evidence tools, invokes the agent for each paper, and records concise activity rather than private reasoning.

Run the small fixture first:

```bash
docker compose -f docker-compose.production.yml exec backend \
  python -m scripts.run_digest --fixture --aws --approve
```

This can incur Bedrock and Polly charges. If it fails:

- **model ID required:** correct `.env.production` and recreate the containers;
- **AccessDeniedException:** recheck the instance profile, inline policy, model access, region, and inference-profile requirements;
- **no credentials:** run `aws sts get-caller-identity` and verify the role is attached;
- **Polly access denied:** confirm the role permits `polly:SynthesizeSpeech`.

## 14. Publish the fixture and inspect it

```bash
docker compose -f docker-compose.production.yml exec backend \
  python -m scripts.publish_episode 2026-W37
curl -fsS http://localhost/api/v1/episodes/current | python -m json.tool
curl -fsS http://localhost/feed.xml | head
```

Refresh the public page and use the native audio player and chapter buttons.

## 15. Create EventBridge Scheduler only after the manual run

1. In IAM, create a role trusted by `scheduler.amazonaws.com` with only `sqs:SendMessage` permission for the weekly queue ARN.
2. Search for **Amazon EventBridge Scheduler**.
3. Choose **Create schedule**.
4. Name it `quantumlistener-weekly`.
5. Choose a recurring cron schedule, verify its timezone, and use a flexible window only if desired.
6. Target: **Amazon SQS SendMessage**.
7. Choose the `quantumlistener-weekly` queue.
8. Message body:

```json
{"type":"weekly_digest","human_approval":true}
```

9. Select the Scheduler execution role.
10. Initially leave the schedule disabled, review the summary, then enable it only when ready.

The application pauses for approval by default; do not change that for the first public deployment.

## 16. Monitor through the console

- **EC2 → Instance → Monitoring:** CPU, network, and status checks.
- **Systems Manager → Session Manager:** browser shell access.
- **SQS → Monitoring:** visible/in-flight messages and DLQ growth.
- **DynamoDB → Explore items:** run and episode records.
- **S3 → bucket:** published and private object keys.
- **Bedrock → usage/cost views:** model request use.
- **CloudWatch → Log groups:** after configuring the container/CloudWatch log driver.
- **Billing → Budgets:** actual and forecast alerts.

Do not expose raw prompts, model messages, or private run logs on the public site.

## 17. Stop costs safely

When the demonstration is over:

1. Disable the EventBridge schedule.
2. Stop the EC2 instance; note that EBS and public IPv4-related charges may remain.
3. Inspect the DLQ and save any failure details you need.
4. Back up published podcast files.
5. Delete resources only when you are certain their data is no longer needed.
6. Check **Billing → Cost Explorer** the next day for unexpected usage.

QuantumListener intentionally provides no automatic destructive cleanup command.
