# 2025ASK : LSTM 기반 고객 이탈 예측 분석  
(Customer Churn Prediction Analysis Using an LSTM-Based Model)

본 연구는 전자상거래 고객 행동 데이터를 시계열 관점에서 분석하여  
**LSTM(Long Short-Term Memory) 기반 고객 이탈 예측 모델을 구축하고,  
기존 머신러닝 기법과 성능을 비교·분석한 연구**입니다.

고객 이탈을 단순 정적 분류 문제가 아닌  
**시간에 따라 변화하는 행동 패턴의 문제로 정의**하고,  
이를 효과적으로 모델링할 수 있는 딥러닝 접근의 유효성을 검증하는 것을 목표로 합니다.

---

## 📄 논문 정보

- **논문명**: LSTM 기반 모델을 이용한 고객 이탈 예측 분석  
- **학술대회**: ASK 2025 학술발표대회 논문집 (32권 1호)  
- **저자**: 이수민 외  
- **주제 분야**: CRM · 고객 이탈 예측 · 시계열 분석 · 딥러닝  
- **RISS 링크**: https://www.riss.kr/link?id=A109772476

---

## 🔍 연구 배경 및 문제 정의

- 기업의 고객 확보 비용(CAC)은 지속적으로 증가
- 기존 고객 유지가 비용·수익 측면에서 더욱 중요
- 고객 행동 데이터는 **시간 의존적(시계열) 특성**을 가짐

### 기존 접근의 한계
- Logistic Regression, Random Forest, XGBoost 등 전통적 모델은  
  고객 행동의 **연속성·장기 의존성 학습에 한계**
- 이탈 징후가 누적되는 과정을 충분히 반영하지 못함

➡️ **시계열 특성을 직접 학습할 수 있는 딥러닝 모델 필요**

---

## 🧠 연구 방법

### 1️⃣ 데이터셋

- **출처**: Kaggle  
  *E-commerce Customer Data For Behavior Analysis*
- **규모**
  - 총 249,736개 행
  - 49,673명의 고객
  - 12개 기본 변수

### 2️⃣ 데이터 전처리 및 특징 공학

- 범주형 변수: Label Encoding
- 연속형 변수: StandardScaler 적용
- 고객별 거래 내역을 **시퀀스 데이터**로 변환
- 클래스 불균형 문제 해결을 위해 **SMOTE 적용**

#### 파생 변수 생성
- Last Purchase (마지막 구매 이후 경과 시간)
- Cumulative Purchase (누적 구매 금액)
- Total Purchases (총 구매 횟수)
- Recent Activity (최근 구매 여부)

---

## 🤖 모델 구성

### 비교 모델

| 구분 | 모델 |
|----|----|
| 전통적 ML | Logistic Regression |
| 전통적 ML | XGBoost |
| 딥러닝 | LSTM |

---

### 🔹 LSTM 모델 선택 이유

- RNN의 **기울기 소실(Vanishing Gradient)** 문제를 해결
- Gate 구조를 통해 **장기 의존성 학습 가능**
- 고객 행동의 누적·반복 패턴을 효과적으로 반영

---

## 📈 실험 결과 및 성능 비교

### 분류 성능 비교

- **LSTM 모델**
  - Accuracy, Precision, F1-score에서 가장 우수
  - 이탈 고객(True Positive)을 안정적으로 식별
- **XGBoost**
  - Recall은 높으나 전반적 성능은 LSTM 대비 낮음
- **Logistic Regression**
  - 모든 지표에서 가장 낮은 성능

---

### ROC-AUC 비교

| 모델 | AUC |
|----|----|
| LSTM | **0.84** |
| XGBoost | 0.81 |
| Logistic Regression | 0.64 |

- LSTM의 ROC 곡선이 가장 좌상단에 위치
- 전반적인 분류 성능 우수성 확인

---

## 🔎 결과 해석 및 인사이트

- 고객 이탈 예측은 **정적 속성보다 시간 흐름이 핵심**
- 시계열 정보를 직접 학습하는 모델이 실질적으로 유리
- CRM 데이터 분석에서 딥러닝 기반 접근의 실효성 검증

---

## 🧑‍💻 연구 기여 및 의의

- 고객 이탈을 **시계열 예측 문제로 재정의**
- LSTM의 CRM 데이터 적용 가능성 실증
- 마케팅 비용 절감 및 고객 유지 전략 수립에 기여

---

## 🚀 향후 연구 방향

- 웹 로그, 장바구니 이력 등 **비정형 데이터 결합**
- Transformer 기반 시계열 모델과 성능 비교
- 실시간 이탈 예측을 위한 온라인 학습 구조 확장
- 멀티모달 고객 행동 분석으로 확장

---

## 🧰 사용 기술 스택

- Python
- pandas, numpy
- scikit-learn
- TensorFlow / Keras
- SMOTE
- Deep Learning (LSTM)

---

## 📎 참고

- ASK 2025 학술발표대회 논문집  
- Kaggle E-commerce Customer Dataset  
- CRM & Churn Prediction 관련 선행 연구

