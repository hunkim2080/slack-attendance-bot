#!/bin/bash

# Slack Attendance Bot 배포 스크립트
# 사용법: ./deploy.sh

set -e

echo "🚀 Slack Attendance Bot 배포를 시작합니다..."

echo ""
echo "📦 1/2: slack_handler 배포 중..."
gcloud functions deploy slack_handler --gen2 --runtime python311 --trigger-http --allow-unauthenticated --entry-point slack_handler --region asia-northeast3 --source . --env-vars-file env.yaml

echo ""
echo "📦 2/2: worker_handler 배포 중..."
gcloud functions deploy worker_handler --gen2 --runtime python311 --trigger-http --allow-unauthenticated --entry-point worker_handler --region asia-northeast3 --source . --env-vars-file env.yaml

echo ""
echo "✅ 배포가 완료되었습니다!"

