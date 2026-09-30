# BustGuard results: ECMWF HRES vs IMD gridded rainfall, IMD subdivisions, JJAS

Split by year: train [2018, 2019], calibration [2020], **test [2021, 2022] (fully unseen)**. Generated 2026-09-30T16:14:25+00:00. Every number below is computed on the test years; thresholds were frozen on the calibration year.

- Rain truth: IMD 0.25 deg gridded rainfall, subdivision area means. Forecast: ECMWF HRES (WeatherBench 2, 1.5 deg), 00 UTC runs.
- Spread = lagged-ensemble spread (std of the last three HRES runs for the same valid day), a proxy: the 50-member ECMWF ensemble was not downloaded. No spread exists for Day 10.
- Primary metric: PR-AUC (busts are rare). False-alarm rate = share of non-bust forecasts flagged.

## Bust definition `imd_category`

Test forecasts: 82,960; busts: 700 (base rate 0.84%).

| Metric | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|
| **PR-AUC (primary)** | **0.292** | **0.031** | **0.033** |
| PR-AUC 95% CI (bootstrap over issue dates) | 0.244-0.343 | 0.027-0.037 | 0.027-0.039 |
| ROC-AUC | 0.952 | 0.796 | 0.796 |
| Brier score (lower is better) | 0.00699 | 0.00826 | 0.00835 |
| Brier skill vs climatology | 0.164 | 0.013 | 0.002 |
| Busts caught at 5% false-alarm rate (ROC) | 79.0% | 27.7% | 25.4% |
| Busts caught at 10% false-alarm rate (ROC) | 87.0% | 43.9% | 44.7% |
| Busts caught at 20% false-alarm rate (ROC) | 91.0% | 62.7% | 62.3% |
| Operating point (threshold frozen at 10% FAR on calibration): recall / realised FAR | 84.9% / 6.7% | 35.7% / 6.8% | 37.7% / 7.6% |
| Precision at operating point | 9.7% | 4.3% | 4.1% |
| CSI at operating point | 0.096 | 0.040 | 0.038 |

### Confidently wrong: busts the spread said were safe (headline)

25 of 700 test busts (4%) happened when the lagged-ensemble spread was in its lowest third for the regime and month.

| | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|
| Recall on **low-spread** busts | 88.0% | 0.0% | 0.0% |
| Recall on other busts | 84.7% | 41.2% | 43.5% |

CONFIDENTLY-WRONG ALERTS on the test years: 13 raised, 5 verified as busts (precision 38.5% vs 0.1% bust rate among all low-spread forecasts).

### Per lead day (PR-AUC)

| Lead | busts | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|---|
| Day 1 | 72 | 0.367 | 0.046 | 0.054 |
| Day 2 | 70 | 0.334 | 0.037 | 0.041 |
| Day 3 | 72 | 0.338 | 0.038 | 0.042 |
| Day 4 | 68 | 0.307 | 0.032 | 0.035 |
| Day 5 | 71 | 0.311 | 0.036 | 0.036 |
| Day 6 | 72 | 0.294 | 0.030 | 0.035 |
| Day 7 | 71 | 0.323 | 0.027 | 0.031 |
| Day 8 | 69 | 0.284 | 0.041 | 0.050 |
| Day 9 | 67 | 0.245 | 0.022 | 0.025 |
| Day 10 | 68 | 0.271 | 0.008 | 0.008 |

### Early warning (72 events: region-days whose Day-1 forecast busted)

| | mean warning lead (days) | warned at all | warned >= 3 days ahead |
|---|---|---|---|
| BustGuard | 7.68 | 90.3% | 81.9% |
| Lagged-ensemble spread | 1.29 | 50.0% | 13.9% |
| Logistic (spread + lead day) | 1.14 | 40.3% | 13.9% |

### Cost-loss value (relative economic value; illustrative user cost/loss ratios)

| User (C/L) | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|
| Disaster manager (0.02) | 0.680 | 0.218 | 0.070 |
| Power utility (0.05) | 0.542 | -0.005 | -0.014 |
| Farmer (0.15) | 0.221 | -0.002 | -0.012 |

### Ablation: drop one feature family, retrain, test PR-AUC

| Dropped family | features | PR-AUC | change |
|---|---|---|---|
| none (full model) | 42 | 0.292 | +0.000 |
| ONLY context (location, season, lead, amount, recent error, analogs) | 16 | 0.250 | -0.043 |
| context | 16 | 0.217 | -0.076 |
| drift | 4 | 0.292 | -0.001 |
| moisture | 3 | 0.294 | +0.002 |
| pressure_wind | 4 | 0.281 | -0.011 |
| regime | 7 | 0.279 | -0.013 |
| spread | 3 | 0.289 | -0.004 |
| upstream | 5 | 0.285 | -0.008 |

### Regime x lead: PR-AUC improvement of BustGuard over the best baseline (cells with >= 8 busts)

| Regime | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Active monsoon | +0.28 | +0.28 | +0.28 | +0.26 | +0.23 | +0.30 | +0.41 | +0.43 | +0.30 | +0.34 |
| Break monsoon | · | · | · | · | · | · | · | · | · | · |
| Cyclone / deep low | · | · | · | · | · | · | · | · | · | · |
| Heavy rainfall | · | · | · | · | · | · | · | · | · | · |
| Monsoon depression | +0.39 | · | +0.31 | · | +0.51 | +0.38 | +0.29 | +0.22 | · | · |
| Normal | +0.54 | +0.41 | +0.41 | +0.38 | +0.35 | +0.26 | +0.29 | +0.21 | +0.21 | +0.25 |
| Western disturbance | · | · | · | · | · | · | · | · | · | · |

Reliability (test, BustGuard):

| forecast bin | mean forecast | observed | n |
|---|---|---|---|
| 0.0-0.1 | 0.004 | 0.004 | 81,520 |
| 0.1-0.2 | 0.137 | 0.244 | 1,204 |
| 0.2-0.3 | 0.265 | 0.477 | 132 |
| 0.3-0.4 | 0.359 | 0.410 | 83 |
| 0.6-0.7 | 0.643 | 0.462 | 13 |
| 0.7-0.8 | 0.714 | 0.750 | 8 |

## Bust definition `p95_error`

Test forecasts: 82,960; busts: 3,551 (base rate 4.28%).

| Metric | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|
| **PR-AUC (primary)** | **0.433** | **0.179** | **0.178** |
| PR-AUC 95% CI (bootstrap over issue dates) | 0.407-0.456 | 0.162-0.195 | 0.161-0.195 |
| ROC-AUC | 0.911 | 0.780 | 0.771 |
| Brier score (lower is better) | 0.02987 | 0.03800 | 0.03882 |
| Brier skill vs climatology | 0.271 | 0.073 | 0.052 |
| Busts caught at 5% false-alarm rate (ROC) | 64.3% | 31.5% | 31.6% |
| Busts caught at 10% false-alarm rate (ROC) | 76.4% | 44.6% | 44.0% |
| Busts caught at 20% false-alarm rate (ROC) | 83.5% | 59.6% | 58.8% |
| Operating point (threshold frozen at 10% FAR on calibration): recall / realised FAR | 73.0% / 7.8% | 38.0% / 7.4% | 39.9% / 8.0% |
| Precision at operating point | 29.6% | 18.8% | 18.3% |
| CSI at operating point | 0.266 | 0.144 | 0.143 |

### Confidently wrong: busts the spread said were safe (headline)

219 of 3551 test busts (6%) happened when the lagged-ensemble spread was in its lowest third for the regime and month.

| | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|
| Recall on **low-spread** busts | 47.0% | 6.8% | 6.4% |
| Recall on other busts | 75.5% | 45.2% | 47.4% |

CONFIDENTLY-WRONG ALERTS on the test years: 138 raised, 64 verified as busts (precision 46.4% vs 0.9% bust rate among all low-spread forecasts).

### Per lead day (PR-AUC)

| Lead | busts | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|---|
| Day 1 | 378 | 0.413 | 0.192 | 0.204 |
| Day 2 | 353 | 0.428 | 0.185 | 0.198 |
| Day 3 | 349 | 0.402 | 0.173 | 0.186 |
| Day 4 | 347 | 0.435 | 0.186 | 0.204 |
| Day 5 | 356 | 0.430 | 0.180 | 0.188 |
| Day 6 | 356 | 0.485 | 0.175 | 0.194 |
| Day 7 | 361 | 0.453 | 0.167 | 0.178 |
| Day 8 | 345 | 0.466 | 0.208 | 0.228 |
| Day 9 | 345 | 0.425 | 0.187 | 0.198 |
| Day 10 | 361 | 0.430 | 0.044 | 0.044 |

### Early warning (378 events: region-days whose Day-1 forecast busted)

| | mean warning lead (days) | warned at all | warned >= 3 days ahead |
|---|---|---|---|
| BustGuard | 4.88 | 72.5% | 55.0% |
| Lagged-ensemble spread | 1.29 | 44.7% | 18.5% |
| Logistic (spread + lead day) | 1.09 | 34.7% | 14.6% |

### Cost-loss value (relative economic value; illustrative user cost/loss ratios)

| User (C/L) | BustGuard | Lagged-ensemble spread | Logistic (spread + lead day) |
|---|---|---|---|
| Disaster manager (0.02) | 0.493 | 0.184 | 0.000 |
| Power utility (0.05) | 0.652 | 0.332 | 0.355 |
| Farmer (0.15) | 0.458 | 0.126 | 0.111 |

### Regime x lead: PR-AUC improvement of BustGuard over the best baseline (cells with >= 8 busts)

| Regime | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Active monsoon | +0.21 | +0.24 | +0.19 | +0.19 | +0.21 | +0.27 | +0.27 | +0.31 | +0.26 | +0.43 |
| Break monsoon | +0.18 | +0.37 | +0.27 | +0.35 | +0.35 | +0.39 | +0.24 | +0.19 | +0.16 | +0.45 |
| Cyclone / deep low | +0.24 | +0.18 | +0.34 | · | +0.19 | +0.39 | +0.06 | +0.14 | · | · |
| Heavy rainfall | · | -0.09 | -0.09 | -0.01 | -0.05 | -0.05 | +0.04 | +0.11 | -0.02 | +0.18 |
| Monsoon depression | +0.22 | +0.11 | +0.09 | +0.18 | +0.30 | +0.35 | +0.36 | +0.22 | · | · |
| Normal | +0.22 | +0.23 | +0.26 | +0.23 | +0.19 | +0.22 | +0.22 | +0.18 | +0.21 | +0.28 |
| Western disturbance | · | · | · | · | · | · | · | · | · | · |

Reliability (test, BustGuard):

| forecast bin | mean forecast | observed | n |
|---|---|---|---|
| 0.0-0.1 | 0.011 | 0.012 | 73,415 |
| 0.1-0.2 | 0.150 | 0.108 | 4,102 |
| 0.2-0.3 | 0.233 | 0.214 | 1,498 |
| 0.3-0.4 | 0.324 | 0.336 | 1,322 |
| 0.4-0.5 | 0.427 | 0.463 | 808 |
| 0.5-0.6 | 0.512 | 0.530 | 707 |
| 0.6-0.7 | 0.635 | 0.561 | 376 |
| 0.7-0.8 | 0.736 | 0.509 | 226 |
| 0.8-0.9 | 0.816 | 0.713 | 460 |
| 0.9-1.0 | 1.000 | 0.739 | 46 |

## Changelog

- v2: bust = IMD rainfall-category bust (>= 2 classes apart, or observed >= Heavy while forecast < Heavy); v1 p95 label kept as option.
- v2: regions = 34 IMD meteorological subdivisions (area means); rain truth = IMD 0.25 deg gridded rainfall (ERA5 only for atmospheric state).
- v2: split train 2018-19 / calibration 2020 / test 2021-22; replay-event windows excluded from fitting; features restricted to issue-time information.
- v2: baselines = lagged-ensemble spread (per-lead isotonic) and logistic regression (spread + lead day).
- v2: new feature families, grouped SHAP explanations, confidently-wrong alerts, pathways, analog cases, regime x lead scorecard, early-warning lead time, cost-loss value, ablation.

