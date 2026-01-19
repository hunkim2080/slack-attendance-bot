# GCP 비용 체크 방법

## 1. 현재 리소스 확인

### Compute Engine 인스턴스 확인
```bash
gcloud compute instances list --project=slack-480914
```

### Managed Instance Groups 확인
```bash
gcloud compute instance-groups managed list --project=slack-480914
```

### Cloud NAT 확인
```bash
gcloud compute routers list --project=slack-480914
gcloud compute routers nats list --router=<router-name> --region=asia-northeast3 --project=slack-480914
```

### Cloud Functions 확인
```bash
gcloud functions list --project=slack-480914 --gen2
```

### Cloud Tasks 큐 확인
```bash
gcloud tasks queues list --location=asia-northeast3 --project=slack-480914
```

## 2. 비용 상세 분석 (GCP 콘솔)

1. **GCP Console → Billing → Reports** 접속
2. **Time range** 선택 (예: Last 7 days)
3. **Group by**: Resource type, SKU 등
4. 각 항목 클릭하여 상세 비용 확인

## 3. 비용 모니터링 설정

### 예산 및 알림 설정
1. **GCP Console → Billing → Budgets & alerts**
2. **CREATE BUDGET** 클릭
3. 예산 금액 설정 (예: 10,000원)
4. 알림 임계값 설정 (50%, 90%, 100%)
5. 알림 이메일 설정

### 리소스별 비용 확인 명령어
```bash
# 특정 날짜의 비용 확인
gcloud billing accounts list
gcloud billing budgets list --billing-account=<BILLING_ACCOUNT_ID>
```

## 4. 불필요한 리소스 제거

### 사용하지 않는 디스크 확인
```bash
gcloud compute disks list --filter="users=null" --project=slack-480914
```

### 사용하지 않는 스냅샷 확인
```bash
gcloud compute snapshots list --project=slack-480914
```

## 5. Cloud Functions Gen2 비용 최적화

Cloud Functions Gen2는 내부적으로 Eventarc Connector를 생성합니다.
이 Connector는 Managed Instance Group로 나타날 수 있습니다.

### 확인 방법
1. **GCP Console → Compute Engine → Instance groups**
2. 이름에 "connector" 또는 "eventarc"가 포함된 그룹 확인
3. 이것은 Cloud Functions Gen2의 내부 리소스이므로 직접 삭제하면 안 됩니다.

### 최적화 방법
- Cloud Functions의 최소 인스턴스 수를 0으로 설정 (기본값)
- 사용하지 않는 함수 삭제
- 메모리 할당량 최적화

## 6. Cloud NAT 비용 확인

Cloud NAT는 외부 IP를 가진 VM이 없어도 NAT 게이트웨이만으로 비용이 발생합니다.
불필요한 Cloud NAT가 있다면 제거:

### Cloud NAT 삭제 전 확인 사항

**1. Cloud NAT를 사용하는 리소스 확인**
```bash
# Router 목록 확인
gcloud compute routers list --project=slack-480914

# NAT 목록 확인
gcloud compute routers nats list --router=<router-name> --region=asia-northeast3 --project=slack-480914

# 이 NAT를 사용하는 Compute Engine 인스턴스 확인
gcloud compute instances list --project=slack-480914 --filter="networkInterfaces.accessConfigs.natIP:null"
```

**2. Cloud Functions VPC Connector 확인**
```bash
# Cloud Functions가 VPC connector를 사용하는지 확인
gcloud functions describe slack_handler --gen2 --region=asia-northeast3 --project=slack-480914 --format="get(serviceConfig.vpcConnector)"
gcloud functions describe worker_handler --gen2 --region=asia-northeast3 --project=slack-480914 --format="get(serviceConfig.vpcConnector)"
```

**3. 삭제 전 체크리스트**
- ✅ Cloud NAT 사용량 그래프에서 트래픽이 거의 없음 (0 B/s 대부분)
- ✅ Compute Engine 인스턴스가 없거나 외부 IP를 가지고 있음
- ✅ Cloud Functions가 VPC connector를 사용하지 않음
- ✅ 다른 프로젝트나 리소스가 이 NAT를 사용하지 않음

**4. 삭제 방법 (확인 후)**
```bash
# 1. NAT 이름과 Router 이름 확인
gcloud compute routers nats list --router=<router-name> --region=asia-northeast3 --project=slack-480914

# 2. 삭제 (주의: 다른 리소스가 사용 중이면 오류 발생)
gcloud compute routers nats delete <nat-name> --router=<router-name> --region=asia-northeast3 --project=slack-480914

# 3. Router도 더 이상 필요없다면 삭제 (NAT가 모두 삭제된 후)
gcloud compute routers delete <router-name> --region=asia-northeast3 --project=slack-480914
```

**주의사항:**
- Cloud Functions Gen2는 기본적으로 외부 인터넷 접근이 가능하므로 Cloud NAT가 없어도 작동합니다.
- 하지만 VPC connector를 사용하는 경우 Cloud NAT가 필요할 수 있습니다.
- 삭제 후 Cloud Functions가 정상 작동하는지 확인하세요.

