# Cloud Functions Gen2 비용 구조 설명

## 기본 원칙: 서버리스는 사용할 때만 비용 발생

Cloud Functions Gen2는 **서버리스**이므로:
- ✅ **사용하지 않을 때**: 거의 비용이 발생하지 않음 (무료 할당량 포함)
- ✅ **호출할 때만**: 실행 시간과 메모리 사용량에 따라 비용 발생
- ✅ **기본 설정**: 최소 인스턴스 수 = 0 (기본값)

## 하지만 주의해야 할 항목들

### 1. 최소 인스턴스 수 (Min Instances)
만약 `--min-instances` 옵션을 설정했다면:
- 항상 지정된 개수만큼 인스턴스가 실행 중
- 사용하지 않아도 해당 인스턴스에 대한 비용 발생

**현재 배포 설정 확인:**
```bash
gcloud functions describe slack_handler --gen2 --region=asia-northeast3 --project=slack-480914 --format="get(serviceConfig.minInstanceCount)"
gcloud functions describe worker_handler --gen2 --region=asia-northeast3 --project=slack-480914 --format="get(serviceConfig.minInstanceCount)"
```

**결과 해석:**
- 결과가 **비어있거나 0**이면 정상 (사용하지 않을 때 비용 없음)
- 결과가 **1 이상**이면 해당 개수만큼 항상 실행 중 (비용 발생)

**또는 GCP 콘솔에서 확인:**
1. Cloud Functions → slack_handler 또는 worker_handler 클릭
2. "Configuration" 탭
3. "Minimum instances" 항목 확인 (0이면 정상)

### 2. Eventarc Connector (Managed Instance Group)
Cloud Functions Gen2는 내부적으로 **Eventarc Connector**를 생성합니다:
- 이것은 **Managed Instance Group**으로 나타남
- Cloud Functions가 활성화되어 있으면 항상 존재
- 이 리소스 자체가 약간의 비용을 발생시킬 수 있음
- 하지만 직접 삭제하면 안 됨 (Cloud Functions와 연동됨)

**확인 방법:**
```bash
gcloud compute instance-groups managed list --project=slack-480914
```

### 3. Cloud NAT
- **활성 상태만으로도 비용 발생** (트래픽과 무관)
- 현재 그래프에서 사용량이 거의 0이지만 비용은 발생 중
- 사용하지 않는다면 삭제 권장

### 4. Persistent Disk (스토리지)
- Cloud Functions는 디스크를 사용하지 않음
- 다른 리소스(예: Compute Engine 인스턴스)에서 사용하는 디스크 비용일 수 있음

## 현재 비용 구조 분석 (이미지 기준)

1. **Managed Instance Group (4,480.82 KRW)** ← Eventarc Connector (Cloud Functions Gen2 필요 리소스)
2. **Cloud NAT (1,648.55 KRW)** ← 사용하지 않으면 삭제 가능
3. **Other (1,297.67 KRW)** ← 상세 확인 필요
4. **Persistent Disk (295.48 KRW)** ← 다른 리소스 또는 미사용 디스크
5. **Cloud Functions (118.90 KRW)** ← 실제 함수 실행 비용 (정상)

## 결론

### 사용하지 않을 때도 비용이 발생하는 이유:
1. **Eventarc Connector** (Managed Instance Group): Cloud Functions Gen2의 필수 리소스 → 삭제 불가
2. **Cloud NAT**: 활성 상태만으로 비용 발생 → 삭제 가능
3. **기타 리소스**: 미사용 디스크 등 → 확인 후 삭제

### 비용 절감 방법:
1. ✅ Cloud NAT 삭제 (사용하지 않는 경우)
2. ✅ 미사용 디스크/스냅샷 삭제
3. ✅ 사용하지 않는 Cloud Functions 삭제
4. ❌ Eventarc Connector는 삭제 불가 (Cloud Functions Gen2 필수)

### Cloud Functions 자체 비용:
- 현재 **118.90 KRW**로 매우 낮음
- 실제 함수 호출 시에만 발생하는 정상적인 비용

