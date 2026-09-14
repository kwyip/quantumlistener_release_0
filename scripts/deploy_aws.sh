#!/bin/sh
set -eu
: "${EC2_HOST:?Set EC2_HOST after manually provisioning the documented stack}"
: "${EC2_USER:=ec2-user}"
rsync -az --exclude .git --exclude .env ./ "$EC2_USER@$EC2_HOST:/opt/quantumlistener/"
ssh "$EC2_USER@$EC2_HOST" 'cd /opt/quantumlistener && docker compose -f docker-compose.production.yml up -d --build'
