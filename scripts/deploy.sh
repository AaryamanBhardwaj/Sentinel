#!/usr/bin/env bash
set -euo pipefail

# Full deploy: package Lambda, apply Terraform, build frontend, upload to S3.
# Usage: GEMINI_API_KEY=your-key ./scripts/deploy.sh
#
# Required:
#   GEMINI_API_KEY     — passed to Lambda via Terraform
#   AWS credentials    — via env vars or ~/.aws/credentials

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================="
echo " RootCause — Deploy to AWS"
echo "=========================================="

# 1. Package Lambda
echo ""
echo "[1/4] Packaging Lambda..."
"$PROJECT_ROOT/scripts/package-lambda.sh"

# 2. Terraform apply
echo ""
echo "[2/4] Applying Terraform..."
cd "$PROJECT_ROOT/infra"
terraform init -upgrade -input=false
terraform apply -var="gemini_api_key=$GEMINI_API_KEY" -auto-approve

API_URL=$(terraform output -raw api_url)
BUCKET=$(terraform output -raw frontend_bucket)
CF_URL=$(terraform output -raw cloudfront_url)
CF_ID=$(terraform output -raw cloudfront_distribution_id)
echo "    API URL:       $API_URL"
echo "    S3 Bucket:     $BUCKET"
echo "    CloudFront:    $CF_URL"

# 3. Build frontend (no VITE_API_URL needed — CloudFront proxies /analyze)
echo ""
echo "[3/4] Building frontend..."
cd "$PROJECT_ROOT/frontend"
npm run build

# 4. Upload to S3 and invalidate CloudFront cache
echo ""
echo "[4/4] Uploading to S3..."
aws s3 sync dist/ "s3://$BUCKET/" --delete
aws cloudfront create-invalidation --distribution-id "$CF_ID" --paths "/*" --no-cli-pager

echo ""
echo "=========================================="
echo " Deploy complete!"
echo ""
echo " Live site: $CF_URL"
echo " API:       $API_URL"
echo ""
echo " To tear down:"
echo "   cd infra && terraform destroy -var=\"gemini_api_key=\$GEMINI_API_KEY\""
echo "=========================================="
