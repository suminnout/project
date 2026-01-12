# 라이브러리
library(tidyverse)
library(data.table)
library(readxl)
library(PerformanceAnalytics)
library(geosphere)
library(glmnet)
library(ggplot2)
library(scatterplot3d)

setwd("C:/Users/Desktop/데이터")
list.files()

# Data Load
pop <- read_excel("춘천시 인구수 .xlsx") %>% as.data.frame
senior <- read.csv("춘천시 노인복지관.csv", fileEncoding = 'euc-kr') %>% as.data.frame
house <- read_excel("춘천시 공동주택 세대수.xlsx") %>% as.data.frame
one_room <- read.csv("춘천시 원룸 및 오피스텔 현황.csv", fileEncoding = 'euc-kr') %>% as.data.frame
bus_stops <- read_excel("춘천시 버스정류장.xlsx") %>% as.data.frame
health_center <- read_excel("춘천시 보건지소 위치.xlsx") %>% as.data.frame
empty_house <- read.csv("춘천시 빈집 현황.csv", fileEncoding = 'euc-kr') %>% as.data.frame
park <- read_excel("춘천시 공원 최종.xlsx") %>% as.data.frame
farm <- read.csv("춘천시 양식장.csv", fileEncoding = 'euc-kr') %>% as.data.frame
garbage_dump <- read_excel("춘천시 위치기반 생활쓰레기 배출장소 현황.xlsx") %>% as.data.frame
pharmacy <- read.csv("춘천시 의료기관약국.csv", fileEncoding = 'euc-kr') %>% as.data.frame
medical_box <- read.csv("춘천시 의료수거함 현황.csv", fileEncoding = 'euc-kr') %>% as.data.frame
train <- read_excel("춘천시 철도 위치.xlsx") %>% as.data.frame
river <- read.csv("춘천시 하천현황.csv", fileEncoding = 'euc-kr') %>% as.data.frame
household_members <- read_excel("춘천시 행정동별 세대원수.xlsx") %>% as.data.frame
age_population <- read.csv("춘천시 행정동별 연령별 성별 간 인구현황.csv", fileEncoding = 'euc-kr') %>% as.data.frame
center <- read.csv("춘천시 행정복지센터.csv", fileEncoding = 'euc-kr') %>% as.data.frame
mart <- read.csv("춘천시_대규모점포.csv", fileEncoding = 'euc-kr') %>% as.data.frame
drug_store <- read_excel("안전상비의약품읍변동추가.xlsx") %>% as.data.frame
waste_medicine <- read_excel("폐의약품 수거함 위치 현황.xlsx") %>% as.data.frame
resident <- read.csv("행정동별 세대원수별 주민등록 세대수.csv", fileEncoding = 'euc-kr') %>% as.data.frame
area <- read.csv("강원특별자치도_춘천시_행정동 및 법정동별 면적_20240307.csv", fileEncoding = 'euc-kr') %>% as.data.frame

# ---------------------------------------
## 행정동별 데이터 전처리
# ---------------------------------------

## 1. 공동주택 & 원룸 및 오피스텔
head(house)
head(one_room)

house_1 <- house
one_room_1 <- one_room

str(house_1) # 층수 변수가 문자형으로 되어 있음.
str(one_room_1)

table(house_1$읍면동)
table(one_room$읍면동)

house_1$층수 <- as.numeric(house_1$층수)
colSums(is.na(house_1)) # 층수 NA 3개
(na_floor <- house_1 %>% filter(is.na(층수))) # NA 처리 방법 고민 필요

# 읍면동 처리
house_1$읍면동 <- ifelse(house_1$읍면동 == "영서로 2920", "신사우동", house_1$읍면동)

# 읍면동, 세대수, 동수, 층수 추출
house_1 <- house_1 %>% select(c(읍면동, 세대수, 동수, 층수))
one_room_1 <- one_room_1 %>% select(c(읍면동, 다가구주택.가구수, 지상층수)) %>% 
  mutate(세대수= 다가구주택.가구수,
         동수 = 1,
         층수 = 지상층수) %>% select(-다가구주택.가구수, -지상층수)

# 데이터 합치기
house_tt <- rbind(house_1, one_room_1)

# 세대 밀집도 변수 생성
house_tt$세대_밀집도 <- (house_tt$세대수 / house_tt$동수 / house_tt$층수)
head(house_tt)

# 행정동별 세대수 합계, 세대 밀집도 평균 집계
house_df <- house_tt %>% group_by(읍면동) %>% 
  summarise(주택수 = sum(세대수),
            주택가구_밀집도 = mean(세대_밀집도, na.rm = T))


## 2. 노인복지관 합계
total_data <- house_df
table(house_df$읍면동)
total_data$노인복지관 <- ifelse(total_data$읍면동 %in% c("동면", "강남동", "신사우동", "신북읍"), 1, 0)

## 3. 행정복지센터 합계
# 공동주택과 가장 가까운 행정복지센터 행정동별 평균 거리
closest_distances3 <- numeric(nrow(house))

# 각 주택에 대해 가장 가까운 행정복지센터과의 거리를 계산
for (i in 1:nrow(house)) {
  # 현재 주택의 위도와 경도
  house_location <- c(house$경도[i], house$위도[i])
  
  # 행정복지센터에 대한 위도와 경도 추출
  center_locations <- cbind(center$경도, center$위도)
  
  # 주택과 모든 행정복지센터 간의 거리를 계산
  distances3 <- distHaversine(house_location, center_locations)
  
  # 가장 가까운 행정복지센터까지의 거리 저장
  closest_distances3[i] <- min(distances3)
}

house_1$행정복지센터_거리 <- closest_distances3

house_center <- house_1 %>% group_by(읍면동) %>% 
  summarise(주택_센터_평균거리 = mean(행정복지센터_거리, na.rm = T))

## 4. 빈집 합계
table(empty_house$읍면동)
empty_house$읍면동 <- as.character(empty_house$읍면동)
empty_house$읍면동 <- ifelse(empty_house$읍면동 %in% c("낙원동", "봉의동", "소양로2가", 
                                                 "소양로3가", "소양로4가", "옥천동", "요선동"), "소양동",
                          ifelse(empty_house$읍면동 %in% c("사농동", "신동", "우두동"), "신사우동", 
                                 ifelse(empty_house$읍면동 %in% c("삼천동", "송암동", "온의동"), "강남동",
                                        ifelse(empty_house$읍면동 %in% c("약사동", "죽림동", "중앙로3가"), "약사명동", 
                                               ifelse(empty_house$읍면동 %in% c("소양로1가"), "근화동",
                                                      ifelse(empty_house$읍면동 %in% c("운교동", "조양동"), 
                                                             "조운동", empty_house$읍면동))))))
empty_df <- empty_house %>% group_by(읍면동) %>% 
  summarise(빈집 = n())

## 5. 보건지소 
health_center_df <- health_center %>% select(읍면동)
health_center_df$보건지소 <- 1

## 6. 의료수거함 
table(medical_box$읍면동)
medical_box$읍면동 <- as.character(medical_box$읍면동)

medical_box$읍면동 <- ifelse(medical_box$읍면동 %in% c("옥천동"), "소양동",
                          ifelse(medical_box$읍면동 %in% c("사농동", "신동", "우두동"), "신사우동", 
                                 ifelse(medical_box$읍면동 %in% c("온의동", "칠전동"), "강남동",
                                        ifelse(medical_box$읍면동 %in% c("약사동", "죽림동"), "약사명동",
                                               ifelse(medical_box$읍면동 %in% c("운교동", "조양동"),
                                                      "조운동", medical_box$읍면동)))))

medical_box_df <- medical_box %>% group_by(읍면동) %>% 
  summarise(의료수거함 = n())

## 7. 병원과 약국 데이터 분리
hospital <- pharmacy %>% filter(!str_detect(종류, '약국'))
pharmacy <- pharmacy %>% filter(str_detect(종류, '약국'))

# 병원 개수
hospital_df <- hospital %>% group_by(읍면동) %>% 
  summarise(병원 = n())

# 약국 밀집도
pharmacy_df <- pharmacy %>% group_by(읍면동) %>% 
  summarise(약국 = n())

pharmacy_df <- left_join(pharmacy_df, area[1:25,], by = "읍면동")
pharmacy_df$약국밀집도 <- pharmacy_df$약국 / pharmacy_df$면적
pharmacy_df <- pharmacy_df[, c(1, 4)]

# 공동주택과 가장 가까운 약국 행정동별 평균 거리
closest_distances <- numeric(nrow(house))

# 각 주택에 대해 가장 가까운 약국과의 거리를 계산
for (i in 1:nrow(house)) {
  # 현재 주택의 위도와 경도
  house_location <- c(house$경도[i], house$위도[i])
  
  # 약국에 대한 위도와 경도 추출
  pharmacy_locations <- cbind(pharmacy$경도, pharmacy$위도)
  
  # 주택과 모든 약국 간의 거리를 계산
  distances <- distHaversine(house_location, pharmacy_locations)
  
  # 가장 가까운 약국까지의 거리 저장
  closest_distances[i] <- min(distances)
}

house_1$약국_거리 <- closest_distances

house_pharmacy <- house_1 %>% group_by(읍면동) %>% 
  summarise(주택_약국_평균거리 = mean(약국_거리, na.rm = T))

## 8. 세대원수별 주민등록 세대수(1/2/3/4~)
resident <- resident %>% filter(시군구명 == "춘천시")
names(resident)[5] <- c("읍면동")

x1_x3_resident_df <- resident %>% select(c(읍면동, X1인세대, X2인세대, X3인세대))
summ <- rowSums(resident[,10:16])
resident_df <- data.frame(x1_x3_resident_df, 
                          X4인이상세대 = summ)

resident_df <- data.frame(읍면동 = resident$읍면동,
                          x4인이상세대_비율 = resident_df$X4인이상세대 / resident$전체세대수)


## 9. 버스정류장 개수
table(bus_stops$읍면동)
sum(is.na(bus_stops$읍면동)) # NA 47개

bus_stops_df <- bus_stops %>% group_by(읍면동) %>% 
  summarise(버스정류장_개수 = n()) %>% filter(!is.na(읍면동))

# 공동주택과 가장 가까운 버스정류장 행정동별 평균 거리
closest_distances2 <- numeric(nrow(house))

# 각 주택에 대해 가장 가까운 버스정류장과의 거리를 계산
for (i in 1:nrow(house)) {
  
  house_location <- c(house$경도[i], house$위도[i])
  
  busstops_locations <- cbind(bus_stops$경도, bus_stops$위도)
  
  # 주택과 모든 버스정류장 간의 거리를 계산
  distances2 <- distHaversine(house_location, busstops_locations)
  
  # 가장 가까운 버스정류장까지의 거리 저장
  closest_distances2[i] <- min(distances2)
}

house_1$버스정류장_거리 <- closest_distances2

house_busstops <- house_1 %>% group_by(읍면동) %>% 
  summarise(주택_버스정류장_평균거리 = mean(버스정류장_거리, na.rm = T))

## 10. 연령별 인구현황 데이터 연령 구분
# # 읍면동 분리
# age_population$읍면동 <- substr(age_population$행정구역, 13, length(age_population$행정구역))
# dong <- data.frame(do.call('rbind', strsplit(as.character(age_population$읍면동), split = '(', fixed = T)))
# age_population$읍면동 <- dong$X1
# 
# str(age_population)
# 
# # 인구수 쉼표 제거
# for (i in 2:40) {
#   age_population[,i] <- as.numeric(gsub(",", "", age_population[,i]))
# }
# 
# str(age_population)
# 
# #엑셀 파일로 저장
# write.csv(age_population, "춘천시 행정동별 연령별 성별 간 인구현황.csv", fileEncoding = 'euc-kr',
#           row.names = F, na = "")

# 아동 및 청소년 : 0~19 / 청년 : 20~29 / 중년 : 30~49 / 장년 : 50~69 / 노년 : 70~
age_population <- age_population%>% filter(읍면동 != "")

age_df <- data.frame(읍면동 = age_population$읍면동,
                     아동_및_청소년 = rowSums(age_population[,4:5]),
                     청년 = age_population[,6],
                     중년 = rowSums(age_population[,7:8]),
                     장년 = rowSums(age_population[,9:10]),
                     노년 = rowSums(age_population[,11:14]))

olderly <-  data.frame(읍면동 = age_population$읍면동,
                       고령자_비율 = age_df$노년 / age_population$총인구수) 

## 11. 마트 & 의약품 판매업소 
mart_1 <- mart %>% select(c(읍면동, 사업장명))
store_1 <- drug_store %>% select(c(읍면동, 사업장명))

# 데이터 합치기
store_tt <- rbind(mart_1, store_1)

store_df <- store_tt %>% group_by(읍면동) %>% 
  summarise(마트_판매업소 = n()) %>% filter(!is.na(읍면동))

## 12. 공원 개수
park_df <- park %>% group_by(읍면동) %>% 
  summarise(공원 = n()) %>% filter(!is.na(읍면동))

## 13. 생활쓰레기 배출장소 
garbage_df <- garbage_dump %>% group_by(읍면동2) %>% 
  summarise(쓰레기_배출장소 = n()) %>% filter(!is.na(읍면동2))

names(garbage_df)[1] <- "읍면동"

## 14. 하천
river <- river %>% filter(소재지 == "춘천시")
dong1 <- data.frame(do.call('rbind', strsplit(as.character(river$주소), split = ' ', fixed = T)))
river$읍면동 <- dong1$X3
river$읍면동 <- as.character(river$읍면동)

# 행정동명 정해진 행정구역으로 바꾸기
river$읍면동 <- ifelse(river$읍면동 == "효자동", "효자1동", 
                    ifelse(river$읍면동 == "온의동", "강남동", 
                           ifelse(river$읍면동 == "약사동", "약사명동", river$읍면동)))

table(river$읍면동)

river_df <- river %>% group_by(읍면동) %>% 
  summarise(하천 = n())

## 15. 인구수 -> 인구밀집도, 전월대비 인구수 차이
pop <- pop[1:25,]
# 띄어쓰기 삭제
pop$읍면동 <- gsub(" ", "", pop$읍면동)

area <- area[1:25, c(2,3)]

# 데이터 합치기
pop_area <- cbind(pop, area[,2])
names(pop_area)[8] <- "면적"

pop_area$인구_밀집도 <- pop_area$`인구수(총계)` / pop_area$면적
pop_area$전월대비_인구수 <- pop_area$`인구수(총계)` - pop_area$`전월 인구수`
pop_area <- pop_area[,c(1, 9, 10)]



# ---------------------------------------
## 최종 데이터셋 생성(PCA)
# ---------------------------------------

# 데이터 합치기
total_data <- total_data %>% 
  full_join(health_center_df, by = "읍면동") %>% 
  full_join(medical_box_df, by = "읍면동") %>% 
  full_join(hospital_df, by = "읍면동") %>% 
  full_join(pharmacy_df, by = "읍면동") %>% 
  full_join(empty_df, by = "읍면동") %>% 
  full_join(house_center, by = "읍면동") %>% 
  full_join(house_pharmacy, by = "읍면동") %>%
  full_join(resident_df, by = "읍면동") %>% 
  full_join(bus_stops_df, by = "읍면동") %>% 
  full_join(house_busstops, by = "읍면동") %>%
  full_join(olderly, by = "읍면동") %>% 
  full_join(store_df, by = "읍면동") %>%
  full_join(park_df, by = "읍면동") %>% 
  full_join(garbage_df, by = "읍면동") %>% 
  full_join(river_df, by = "읍면동") %>% 
  full_join(pop_area, by = "읍면동") 

total_data <- total_data[c(1:24, 29),]
names(total_data)
# NA 0으로 대체
total_data[is.na(total_data)] <- 0

# # 엑셀파일로 저장
# write.csv(total_data, "PCA_최종데이터.csv", fileEncoding = 'euc-kr',
#           row.names = F, na = "")

#-------------------------------------------
## PCA (주성분 분석)
# ------------------------------------------
## 값이 클수록 좋은 변수, 작을수록 좋은 변수 구분해서 변환 필요
# 값이 클수록 좋은 변수 : 주택수, 주택가구_밀집도, 노인복지관, 행정복지센터, 
#                         보건지소, 의료수거함, 병원, 약국, X1인세대, X2인세대,
#                         X3인세대, X4인이상세대, 버스정류장_개수, 아동_및_청소년, 청년
#                         중년, 장년, 노년, 마트_판매업소, 쓰레기_배출장소, 인구_밀집도,전월대비_인구수
# 값이 작을수록 좋은 변수 : 빈집, 공원, 하천

## 상관관계 확인
(corr <- cor(total_data[,-1]))
chart.Correlation(total_data[,-1], histogram = T,cex = 1, cex.cor = 10)

# # 값이 작을수록 좋은 변수에 역수 변환해서 의미 맞춰주기
# ttotal_data <- total_data
# ttotal_data$빈집 <- ifelse(ttotal_data$빈집 == 0, 0, 1/ttotal_data$빈집)
# ttotal_data$공원 <- ifelse(ttotal_data$공원 == 0, 0, 1/ttotal_data$공원)
# ttotal_data$하천 <- ifelse(ttotal_data$하천 == 0, 0, 1/ttotal_data$하천)
# ttotal_data$주택_약국_평균거리 <- ifelse(ttotal_data$주택_약국_평균거리 == 0, 0, 1/ttotal_data$주택_약국_평균거리)
# ttotal_data$주택_버스정류장_평균거리 <- ifelse(ttotal_data$주택_버스정류장_평균거리 == 0, 
#                                     0, 1/ttotal_data$주택_버스정류장_평균거리)

# 값이 작을수록 좋은 변수에 '-'를 붙여서 의미 맞춰주기
ttotal_data <- total_data
ttotal_data$빈집 <- -ttotal_data$빈집
ttotal_data$공원 <- -ttotal_data$공원
ttotal_data$하천 <- -ttotal_data$하천
ttotal_data$주택_약국_평균거리 <- -ttotal_data$주택_약국_평균거리
ttotal_data$주택_버스정류장_평균거리 <- -ttotal_data$주택_버스정류장_평균거리

# # Min-Max 정규화 함수
# minmax_func <- function(x) {
#   result = (x - min(x)) / (max(x) - min(x))
#   return(result)
# }

# minmax 정규화
scaled_data <- as.data.frame(lapply(ttotal_data[,-1], scale))

# 읍면동을 행이름으로 변환
scaled_data <- data.frame(scaled_data, ttotal_data$읍면동)
names(scaled_data)[20] <- "읍면동"

scaled_data <- column_to_rownames(scaled_data, var = "읍면동")

## PCA
pca <- prcomp(scaled_data)
summary(pca)
screeplot(pca, type = "l", main = "Scree Plot") # 성분 4개(70%)

# 각 개체에 대한 첫 번째, 두 번째 주성분 점수 및 행렬도(biplot)
biplot(pca, main = "Biplot") # 화살표가 축과 평행일수록 대응되는 변수와 성분이 서로 밀접한 상관관계를 갖음

# PC1, PC2의 로딩값
pca$rotation # 절댓값 0.5 이상일수록 큰 영향을 미치는 변수 / 계수를 가중치로 적용

# PCA 주성분 점수
(pca_scores <- pca$x)

# 3차원 주성분 점수 분포 시각화(Score Plot)

scatterplot3d(pca$x[,1], pca$x[,2], pca$x[,3],
              xlab = "PC1", ylab = "PC2", zlab = "PC3",
              main = "3D Score Plot (PC1, PC2, PC3)",
              pch = 19)  # 점 스타일

## 2D 주성분 점수 분포 시각화
# PC1 vs PC2
plot(pca$x[,1], pca$x[,2],
     pch = 19, xlab = "PC1", ylab = "PC2",
     main = "Score Plot (PC1 vs PC2)")

# PC1 vs PC3
plot(pca$x[,1], pca$x[,3],
     pch = 19, xlab = "PC1", ylab = "PC3",
     main = "Score Plot (PC1 vs PC3)")

# PC2 vs PC3
plot(pca$x[,2], pca$x[,3],
     pch = 19, xlab = "PC2", ylab = "PC3",
     main = "Score Plot (PC2 vs PC3)")
# 그래프 분포가 흩어져 있을수록 좋음.

# 폐의약품수거함_여부 항목 추가
waste_medicine_df <- waste_medicine %>% group_by(읍면동) %>% 
  summarise(폐의약품_개수 = n())

waste_medicine_df$폐의약품수거함_여부 <- ifelse(waste_medicine_df$폐의약품_개수 >= 1, "1", "0")
waste_medicine_df <- waste_medicine_df[,-2]

lm_data <- total_data %>% full_join(waste_medicine_df, by = "읍면동")

# NA 0으로 대체
lm_data[is.na(lm_data)] <- "0"

# 주성분을 새로운 변수로 추가
pca_data <- data.frame(pca_scores[,1:4], 폐의약품수거함_여부 = lm_data$폐의약품수거함_여부)
names(pca_data)[5] <- "폐의약품수거함_여부"

pca_data$폐의약품수거함_여부 <- as.factor(pca_data$폐의약품수거함_여부)

# PCA 결과의 주성분 이용해서 로지스틱 회귀분석(glm)
glm_model1 <- glm(폐의약품수거함_여부 ~ ., data = pca_data, family = 'binomial')

# 모델 확인
summary(glm_model1)



# ----------------------------------------
## 중요도 평가 (lm)
# ----------------------------------------
## 변수 중요도 파악
# 높은 가중치 : 주택수, 주택가구_밀집도, 인구_밀집도, 보건지소, 의료수거함, 
#               병원, 약국, 노년, X4인이상세대, 노인복지관
# 중간 가중치 : 행정복지센터, 전월대비_인구수, 중년, 장년, X3인세대, 쓰레기_배출장소, 마트_판매업소
# 낮은 가중치 : 버스정류장_개수, 빈집, 공원, 아동_및_청소년, 청년, X1인세대, X2인세대, 하천

## 회귀분석 데이터셋
# waste_medicine_df <- waste_medicine %>% group_by(읍면동) %>% 
#   summarise(폐의약품_개수 = n())
# 
# waste_medicine_df$폐의약품수거함_여부 <- ifelse(waste_medicine_df$폐의약품_개수 >= 1, "1", "0")
# waste_medicine_df <- waste_medicine_df[,-2]
# 
# lm_data <- total_data %>% full_join(waste_medicine_df, by = "읍면동")
# 
# # NA 0으로 대체
# lm_data[is.na(lm_data)] <- "0"
# 
# 
# # Min-Max 정규화
# minmax_func <- function(x) {
#   result = (x - min(x)) / (max(x) - min(x))
#   return(result)
# }
# 
# lm_data[,-c(1, 19)] <- lapply(lm_data[,-c(1, 19)], minmax_func)
# lm_data <- lm_data[,-1]
# 
# str(lm_data)
# 
# ## 회귀분석 모델
# lm_data$노인복지관 <- as.factor(lm_data$노인복지관)
# lm_data$보건지소 <- as.factor(lm_data$보건지소)
# lm_data$폐의약품수거함_여부 <- as.factor(lm_data$폐의약품수거함_여부)
# 
# lm_model <- glm(폐의약품수거함_여부 ~ ., data = lm_data, family = binomial(link = "logit"))
# 
# summary(lm_model)
# 
# 
# ## Lasso 회귀



