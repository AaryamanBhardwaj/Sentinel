#!/usr/bin/env bash
set -euo pipefail

# Full deploy: package Lambda, apply Terraform, build & deploy frontend.
# Usage: ./scripts/deploy.sh
#
# Required env vars:
#   GEMINI_API_KEY     — passed to Lambda via Terraform
#   AWS credentials    — via env vars or ~/.aws/credentials
#
# Optional:
#   TF_VAR_aws_region  — defaults to us-east-1

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================="
echo " RootCause — Deploy"
echo "=========================================="

# 1. Package Lambda
echo ""
echo "[1/3] Packaging Lambda..."
"$PROJECT_ROOT/scripts/package-lambda.sh"

# 2. Terraform apply
echo ""
echo "[2/3] Applying Terraform..."
cd "$PROJECT_ROOT/infra"
terraform init -upgrade -input=false
terraform apply -var="gemini_api_key=$GEMINI_API_KEY" -auto-approve

API_URL=$(terraform output -raw api_url)
echo "    API URL: $API_URL"

# 3. Build frontend with the API URL baked in
echo ""
echo "[3/3] Building frontend..."
cd "$PROJECT_ROOT/frontend"
VITE_API_URL="$API_URL" npm run build

echo ""
echo "=========================================="
echo " Deploy complete!"
echo ""
echo " API:      $API_URL"
echo " Frontend: deploy frontend/dist/ to Vercel"
echo ""
echo " To deploy frontend to Vercel:"
echo "   cd frontend && npx vercel --prod"
echo ""
echo " To tear down:"
echo "   cd infra && terraform destroy -var=\"gemini_api_key=\$GEMINI_API_KEY\""
echo "=========================================="
