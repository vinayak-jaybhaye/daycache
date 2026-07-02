#!/bin/bash
# LocalStack init script — runs once when LocalStack is ready.
# Creates the S3 bucket used by the DayCache API.
# This file is mounted at /etc/localstack/init/ready.d/ and executed automatically.

set -euo pipefail

BUCKET="${S3_BUCKET:-daycache-media}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

echo "[init-s3] Creating bucket: s3://${BUCKET} (region: ${REGION})"

awslocal s3api create-bucket \
  --bucket "${BUCKET}" \
  --region "${REGION}" \
  $([ "${REGION}" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=${REGION}" || true)

echo "[init-s3] Bucket s3://${BUCKET} ready."
