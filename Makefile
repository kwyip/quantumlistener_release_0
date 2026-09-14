.PHONY: demo demo-aws check-aws test

demo:
	python -m scripts.run_digest --fixture --approve
	python -m scripts.publish_episode 2026-W37
	@echo 'Demo generated. Start the site with: python -m app.web.server'

demo-aws:
	@test -n "$$BEDROCK_MODEL_ID" -a -n "$$S3_BUCKET" -a -n "$$DYNAMODB_TABLE" || (echo 'Set BEDROCK_MODEL_ID, S3_BUCKET, and DYNAMODB_TABLE' && exit 2)
	python -m scripts.run_digest --aws --approve

check-aws:
	./scripts/check_aws_setup.sh

test:
	python -m pytest -q
