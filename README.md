# QuantumListener

QuantumListener turns each week of arXiv `quant-ph` updates into an evidence-grounded,
five-chapter podcast. It collects a precise weekly interval, deduplicates revisions,
classifies and summarizes every paper, generates narration, waits for human approval,
and atomically publishes a website and RSS feed.

> Summaries are generated from arXiv metadata and abstracts, not peer-review or independent reproduction. Author claims remain explicitly attributed. Scientific judgment belongs to the listener.

## Run locally

Python 3.12+ is required. FFmpeg is recommended; the Docker image includes it. Without FFmpeg the fixture writes a playable WAV-container fallback under the `.mp3` demo path and reports the limitation.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
make demo
python -m app.web.server
# open http://localhost:8080
```

`make demo` uses five deterministic fixture records and does not contact AWS. It writes
the episode, transcript, show notes, records, and RSS feed under `.quantumlistener/`.

## Agent architecture

The **Weekly Editor** is a Strands Agent in AWS mode, backed by a configurable Amazon Bedrock model. It exposes Category Editor and Evidence Editor tools and coordinates arXiv Scout, Paper Listener, Podcast Writer, Audio Producer, and Publisher stages. The orchestration layer records only tool name, status, counters, and evidence warnings—not private reasoning. The fixture provider follows the same interfaces without an LLM so the offline demo is deterministic.

See the [architecture diagram](docs/architecture.svg),
[AWS deployment guide](docs/AWS_SETUP_GUIDE.md), and [data model](docs/DATA_MODEL.md).

## AWS configuration

Copy `.env.example`; do not add access keys. On EC2 use an instance profile; on AgentCore use its execution role. Choose a Bedrock text model enabled in your account and region—there is deliberately no hardcoded model ID.

```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID='<enabled Bedrock model ID>'
export S3_BUCKET='<private-by-default media bucket>'
export DYNAMODB_TABLE=quantumlistener
export SQS_QUEUE_URL='<weekly queue URL>'
make demo-aws
```

`make demo-aws` uses the AWS credential chain and requires Bedrock model access. It does
not provision resources. Deployment templates are under `deployment/`.

## Production deployment on EC2

1. Review and deploy `deployment/{iam,sqs,eventbridge,ec2}` with your VPC, subnet, AMI, domain, architecture, instance type, and disk size. The EventBridge schedule is **disabled by default**.
2. Install Docker and Compose on the host, create `/opt/quantumlistener/.env.production` with resource names (not keys), and use the EC2 instance profile.
3. Deploy without provisioning anything:

```bash
export EC2_HOST='<host>' EC2_USER=ec2-user
./scripts/deploy_aws.sh
ssh "$EC2_USER@$EC2_HOST" 'cd /opt/quantumlistener && ./scripts/compose.sh -f docker-compose.production.yml ps'
```

Put TLS at an ALB or configure an audited certificate in Nginx before public use. ECR is optional: set `ECR_IMAGE`. CloudFront is optional. Enable the Scheduler only after a manual dry run and budget review.

## Operations

```bash
# Human-review draft, exact current UTC week
python -m scripts.run_digest --fixture
# Approved fixture narration
python -m scripts.run_digest --fixture --approve
# Resume marker and no narration/publication
python -m scripts.run_digest --fixture --dry-run --resume-from summaries
# Atomic local publish
python -m scripts.publish_episode 2026-W37
# Test
make test
```

The manual API requires `Authorization: Bearer $ADMIN_TOKEN` and supports `approve`, `dry_run`, and `resume_from`. Public APIs read only the publication pointer. The default flow pauses for approval.

## Routes

The server exposes `/`, `/episodes`, `/episodes/{week}`, `/papers`,
`/papers/{arxiv_id}`, `/feed.xml`, public `/api/v1` reads, and protected
digest/approve/publish controls.

## Safety and limits

- Exact half-open UTC interval `[start,end)`, official arXiv export API, pagination, stable user agent, three-second pacing, timeout, exponential retry, and newest-version deduplication.
- Claims use `Metadata fact`, `Author-reported claim`, or `QuantumListener inference`; unsupported evidence creates a human-review warning.
- `MAX_BEDROCK_CALLS`, `MAX_POLLY_CHARACTERS`, and `MAX_RUN_COST_USD` are operator ceilings. IAM is least privilege; SQS has a DLQ; DynamoDB locks use a conditional write.
- No full text, paywall bypass, copyrighted music, credentials, or personal data are included.

## Testing

```bash
pip install -e '.[dev]'
pytest -q
ruff check app tests scripts
```

The suite covers weekly boundaries, pagination, versions, schemas, grounded claims, retries, repositories/adapters, atomic publishing, RSS, media, routes, audio controls, chapter seeking, accessibility, and fixture end to end.
