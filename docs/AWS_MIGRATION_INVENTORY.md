# AWS migration inventory

Audit date: 2026-09-14. The pre-migration repository files, deployment records, schemas, tests, build specifications, and environment templates were inspected. No cloud environment was queried or modified.

| Existing service | Configuration found in repository | AWS replacement | Proposed configuration | Status | Data requiring migration | Behavior differences | Cost-sensitive areas |
|---|---|---|---|---|---|---|---|
| Compute Engine VM | systemd/native and Compose guides existed, but **no authoritative machine type, disk, memory, architecture, project, or deployed region record** | EC2 | Configurable AMI, subnet/VPC, `InstanceType` default `t3.medium`, architecture and encrypted gp3 size parameters | IaC target present; not deployed | Existing publication volume, only if owner elects | Instance profile replaces service account; operator owns patching | uptime, instance family, gp3, transfer |
| Cloud Run | `cloudbuild.yaml` deployed one Gunicorn service in `us-central1` | EC2 Compose; AgentCore target | backend, worker, frontend, Nginx on EC2 | Replaced | Published metadata/assets if live | Always-on host vs scale-to-zero | EC2 uptime |
| Gemini API | `google-genai`, model env vars, smoke test | Amazon Bedrock | `BEDROCK_MODEL_ID` required; no hardcoded model | Replaced in production | None | Converse/Strands invocation and regional model access | input/output tokens |
| Google ADK | `google-adk`, root agent topology tests | Strands Agents SDK | Weekly Editor with registered category/evidence tools | Replaced | None | Strands tool loop; concise activity log | model tool-loop calls |
| Firestore | collections for papers/issues/renders/pointers | DynamoDB | single table, documented PK/SK and transactional pointer | Adapter/IaC policy present | paper/version/episode records if live | access-pattern design; conditional locks | read/write capacity |
| Cloud Storage | public weekly film assets | S3 | private bucket; only published podcast keys retrievable | Adapter present | approved legacy media only if wanted | object ACLs avoided; policy/presigning preferred | storage, requests, egress |
| Cloud Scheduler | weekly timer/config | EventBridge Scheduler | Monday 09:00 UTC to SQS; disabled by default | Template present | None | AWS cron and target role | invocations negligible |
| Cloud Tasks | media task queue | SQS | weekly queue, 900s visibility, three attempts, DLQ | Template/worker present | outstanding jobs should not migrate | pull/visibility model vs HTTP push | requests, long polling |
| Secret Manager | Google secret-name variables | AWS Secrets Manager | `quantumlistener/*`; instance role | IAM boundary present | rotate/re-enter values, never export to Git | AWS credential chain | secret/API calls |
| Logging/Trace | Google structured logging/trace libraries | CloudWatch + OpenTelemetry | container logs; CloudWatch role; OTel extension point | CloudWatch ready; OTel target documented | Retention only if required | log groups/retention differ | ingestion and retention |
| Google TTS | Google voice adapter | Amazon Polly | neural `POLLY_VOICE_ID`, SSML, character ceiling | Adapter present | pronunciation lexicon if one existed | voice/SSML differences | characters synthesized |
| Artifact Registry | Cloud Build image URL | Amazon ECR | optional `ECR_IMAGE` | Configurable | container images need rebuild, not copy | auth/lifecycle differences | image storage/scanning |
| Cloud Build | Google Docker build/deploy | GitHub Actions | tests and image build workflow | Replaced | None | deployment requires explicit operator action | runner/ECR storage |
| Nginx | reverse proxy configuration | Nginx on EC2 | backend/frontend proxy | Replaced | domain/cert config | TLS recommended at ALB | ALB/cert/transfer |
| Google video services | Imagen/Veo/render pipelines | Removed | podcast audio only | Removed from MVP | No generated video migrated | no video output | avoids major generation/render costs |

## Unknown legacy VM details

Because the repository does not establish the live VM settings, the AWS template keeps sizing configurable. An authorized owner can inspect the old environment without changing it:

```bash
gcloud compute instances describe INSTANCE_NAME --zone=ZONE --project=PROJECT_ID \
  --format='yaml(machineType,zone,disks,networkInterfaces,serviceAccounts,labels,metadata.items)'
```

Do not run that command without authorized Google credentials. Do not stop or modify the Google deployment during this migration.
