# 🏨 호텔 리뷰 감성 분류 분석(24-1 기계학습 기말 프로젝트)

본 프로젝트는 호텔 예약 사이트의 리뷰 텍스트를 분석하여 새로운 리뷰가 **긍정(Positive)** 인지 **부정(Negative)** 인지 사전에 예측하는 텍스트 감성 분류 모델을 설계·구현한 머신러닝 프로젝트

단순 모델 학습에 그치지 않고, **라벨 정의 → 텍스트 전처리(형태소/불용어) → 시퀀스화/패딩 → CNN 분류기 학습 → 성능 평가 → 문장 입력 기반 추론** 까지 전체 파이프라인을 구성

---

## 🔍 프로젝트 개요
- 프로젝트명: 호텔 리뷰 감성 분류 분석
- 프로젝트 성격: 기계학습(ML) 기말 프로젝트
- 문제 유형: 이진 분류(Binary Classification)
- 핵심 키워드: Text Classification · CNN · Tokenizer · Okt · Stopwords · ModelCheckpoint

---

## 🎯 문제 정의 (Why)
호텔 리뷰는 고객의 실제 경험이 반영된 핵심 데이터이며 신규 리뷰의 감성을 자동으로 분류할 수 있다면 다음과 같은 활용이 가능

- 고객 만족도/불만 요인 모니터링 자동화
- 부정 리뷰 조기 탐지 및 대응(운영/CS)
- 호텔/상품 개선 인사이트 도출

---

## 🧠 데이터 라벨링 기준 및 데이터 소개
<div align="center">

  <img 
    src="https://github.com/user-attachments/assets/bda0d4c4-445d-42ef-b557-fa6ac16cf9fe"
    width="366"
    height="438"
    alt="TripAdvisor Hotel Review Data Distribution"
  />

  <br/><br/>

  <strong>
    "트립어드바이저에서 서울에 위치한 호텔 리뷰 총 3,126건 수집"
  </strong>
  <br/><br/>

  사전 계획한 리뷰 수:  
  50 (호텔당 리뷰 수) × 40 (호텔 수) = <strong>2,000건</strong>
  <br/><br/>

  데이터 분석 결과, 긍정 리뷰 비율이 과도하게 높아  
  <strong>부정 리뷰 라벨 보완을 위해 추가 데이터 수집 수행</strong>

  <br/><br/>

</div>



<div align="center">
  <img 
    src="https://github.com/user-attachments/assets/d3184985-a641-42f9-a0f1-b7c0afdd2873"
    width="939"
    height="476"
    alt="Hotel Review Data Collection Result"
  />
  <br/>
  <sub>
   데이터 수집 결과
  </sub>
</div>



별점 기반으로 감성을 정의했습니다.
- **별점 4점 이상 → 긍정(1)**
- **별점 3점 이하 → 부정(0)**

---

## 🛠 데이터 전처리
### 1) 텍스트 정제
- 한글 및 공백을 제외한 문자 제거: 정규식 기반 클렌징

### 2) 형태소 분석
- `Okt` 형태소 분석기로 토큰화
- `stem=True`로 어간 추출 적용

### 3) 불용어 처리
- WordCloud 기반으로 불용어 후보 확인
- 도메인 특화 불용어(예: 서울, 호텔, 숙소, 직원, 조식 등) 추가 제거

---

## 🧩 모델링 파이프라인
### 1) 토큰 인코딩 & 패딩
- `Tokenizer()`로 단어 사전 구축 및 정수 인코딩
- `pad_sequences(..., padding='post')`로 길이 고정
- **MAX_SEQUENCE_LENGTH = 8**

### 2) CNN 분류 모델
Embedding + Multi-kernel Conv1D 구조로 문장 내 n-gram 패턴을 학습하도록 구성했습니다.

- Embedding dimension: **128**
- Conv1D: **filters=100**, kernel_size **[3,4,5]**
- Pooling: GlobalMaxPooling1D
- Dropout: **0.5**
- Dense(FC): **250 (ReLU)**
- Output: Sigmoid (이진 분류)

---

## 🧪 학습 설정
- Epochs: **10**
- Validation split: **0.1**
- EarlyStopping: `monitor='val_accuracy'`, `patience=2`
- ModelCheckpoint: `val_accuracy` 기준 best weight 저장

---

## 📈 성능 결과
- **최종 Validation Accuracy: 0.8213**
- **Test Accuracy: 0.8146** (loss: 0.4475)

---

## 🔍 데모 (문장 입력 기반 추론)
사용자 입력 문장에 대해 감성 확률을 출력하도록 구성했습니다.

예시)
- 입력: “다시는 안 오겠습니다”
- 출력: **88.68% 확률로 부정 리뷰**

---

## 🧑‍💻 프로젝트를 통해 배운 점
- 텍스트 분류에서 성능은 모델 구조뿐 아니라 **전처리(형태소/불용어/길이 설계)** 영향이 매우 큼
- CNN은 짧은 텍스트에서 **국소 패턴(n-gram) 학습**에 효과적이며 빠르게 학습 가능
- 단순 정확도 외에도, 실제 서비스 관점에서는 **입력 기반 추론 흐름(UX) 설계**가 중요함

---

## 🧰 기술 스택
- Python, Jupyter Notebook
- Pandas, NumPy
- konlpy(Okt)
- TensorFlow / Keras
- Tokenizer, pad_sequences
- CNN(Conv1D), EarlyStopping, ModelCheckpoint
