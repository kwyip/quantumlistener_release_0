# AgentCore target

`WeeklyEditor._create_strands_agent` is the AgentCore-compatible Strands entry boundary. For the MVP it runs on EC2 because AgentCore packaging and live invocation cannot be verified without an AWS account. Containerize the same application, configure `BEDROCK_MODEL_ID`, attach the least-privilege execution role, and register the runtime through the current AgentCore starter toolkit. Human approval remains external to the runtime.
