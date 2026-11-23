# TBO InventoryIQ — Phase 4 Model Comparison & Benchmark Summary
**AI-Powered Travel Inventory & Profit Optimization Platform**  
**Date:** November 23, 2026  
**Status:** COMPLETE & BENCHMARKED  

---
## Executive Summary
This report consolidates cross-validation benchmarks and offline holdout evaluations across the four eligible travel prediction tasks. Each task was evaluated across heuristic baselines, linear/logistic models, Random Forest, XGBoost, and LightGBM.

### Hotel Cancellation
**Selected Champion Model:** `lightgbm_tuned`  
**Selection Rationale:** Selected 'lightgbm_tuned' achieving best mean f1_score=0.7922 (improvement of 0.1073 / 15.67% over logistic_regression f1_score=0.6849).  

#### Cross-Validation Benchmark Table
| model_name | n_splits | mean_fit_time_sec | mean_inference_time_sec | mean_accuracy | std_accuracy | mean_precision | std_precision | mean_recall | std_recall | mean_f1_score | std_f1_score | mean_roc_auc | std_roc_auc | mean_pr_auc | std_pr_auc | mean_log_loss | std_log_loss |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightgbm_tuned | 5 | 0.5618 | 0.044849 | 0.8518 | 0.004 | 0.8252 | 0.0101 | 0.7619 | 0.0097 | 0.7922 | 0.0054 | 0.9305 | 0.0024 | 0.9026 | 0.0038 | 0.3142 | 0.0054 |
| lightgbm | 5 | 0.4603 | 0.042088 | 0.847 | 0.0038 | 0.8271 | 0.0099 | 0.743 | 0.0119 | 0.7827 | 0.0059 | 0.924 | 0.0017 | 0.8931 | 0.0016 | 0.3268 | 0.0026 |
| xgboost | 5 | 0.3984 | 0.040413 | 0.8434 | 0.0027 | 0.8258 | 0.0091 | 0.7322 | 0.0069 | 0.7761 | 0.0031 | 0.9218 | 0.0017 | 0.8905 | 0.0011 | 0.3322 | 0.0024 |
| random_forest | 5 | 0.6164 | 0.109293 | 0.8312 | 0.0042 | 0.8688 | 0.0097 | 0.642 | 0.0136 | 0.7382 | 0.0082 | 0.9101 | 0.0022 | 0.8794 | 0.0031 | 0.3711 | 0.0033 |
| logistic_regression | 5 | 2.0809 | 0.037692 | 0.7991 | 0.0059 | 0.8182 | 0.0077 | 0.5891 | 0.016 | 0.6849 | 0.012 | 0.8645 | 0.0047 | 0.8298 | 0.0063 | 0.4151 | 0.0065 |
| dummy | 5 | 0.1645 | 0.03162 | 0.5366 | 0.0029 | 0.3754 | 0.0038 | 0.3764 | 0.0038 | 0.3759 | 0.0038 | 0.5037 | 0.003 | 0.3726 | 0.0015 | 16.7022 | 0.1031 |


### Flight Price
**Selected Champion Model:** `lightgbm_tuned`  
**Selection Rationale:** Selected 'lightgbm_tuned' achieving best mean mae=2277.6012 (improvement of 2213.9287 / 49.29% over linear_regression mae=4491.5299).  

#### Cross-Validation Benchmark Table
| model_name | n_splits | mean_fit_time_sec | mean_inference_time_sec | mean_mae | std_mae | mean_rmse | std_rmse | mean_r2 | std_r2 | mean_mape | std_mape | mean_wape | std_wape | mean_smape | std_smape | mean_forecast_bias | std_forecast_bias |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightgbm_tuned | 5 | 0.3429 | 0.03797 | 2277.6012 | 32.8044 | 3948.0152 | 19.145 | 0.9698 | 0.0006 | 16.6277 | 0.3671 | 10.8686 | 0.173 | 15.7385 | 0.2102 | 8.6029 | 49.9047 |
| random_forest | 5 | 1.288 | 0.132474 | 2477.048 | 46.7622 | 4379.408 | 67.1346 | 0.9629 | 0.001 | 17.153 | 0.1871 | 11.8194 | 0.1631 | 16.127 | 0.0871 | 20.457 | 42.8103 |
| lightgbm | 5 | 0.2794 | 0.03399 | 2541.7383 | 37.8687 | 4336.3929 | 42.0132 | 0.9636 | 0.0006 | 18.1197 | 0.2752 | 12.1283 | 0.1342 | 16.9464 | 0.1571 | -3.1971 | 57.0785 |
| xgboost | 5 | 0.2953 | 0.032756 | 2619.3145 | 28.8359 | 4453.9525 | 24.3189 | 0.9616 | 0.0006 | 18.2903 | 0.2988 | 12.499 | 0.1354 | 17.125 | 0.1635 | 6.9329 | 60.8328 |
| linear_regression | 5 | 0.1081 | 0.020485 | 4491.5299 | 61.1144 | 6818.5366 | 133.5519 | 0.91 | 0.003 | 44.2035 | 0.8227 | 21.4321 | 0.2041 | 40.4045 | 0.7222 | 0.8285 | 61.249 |
| dummy | 5 | 0.0972 | 0.02592 | 19810.4946 | 131.2263 | 22735.8928 | 175.7994 | -0.0001 | 0.0002 | 238.8182 | 1.3621 | 94.5323 | 0.4974 | 100.9645 | 0.1882 | 0.0 | 300.6938 |


### Demand Forecasting
**Selected Champion Model:** `naive`  
**Selection Rationale:** Selected 'naive' achieving best mean mae=0.4985 (improvement of 0.0000 / 0.00% over naive mae=0.4985).  

#### Cross-Validation Benchmark Table
| model_name | n_splits | mean_fit_time_sec | mean_inference_time_sec | mean_mae | std_mae | mean_rmse | std_rmse | mean_r2 | std_r2 | mean_mape | std_mape | mean_wape | std_wape | mean_smape | std_smape | mean_forecast_bias | std_forecast_bias |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| naive | 5 | 0.0151 | 0.007883 | 0.4985 | 0.1446 | 0.8207 | 0.0682 | -0.3994 | 0.0709 | 83.2986 | 37.3455 | 106.3518 | 14.2031 | 81.3057 | 26.3318 | -0.2625 | 0.3918 |
| lightgbm_tuned | 5 | 0.0548 | 0.014874 | 0.5817 | 0.0453 | 0.6977 | 0.0584 | -0.0111 | 0.0436 | 51.9188 | 3.714 | 126.975 | 10.3192 | 154.6755 | 6.5902 | 0.0623 | 0.0536 |
| lightgbm | 5 | 0.0887 | 0.014477 | 0.5834 | 0.0457 | 0.7108 | 0.0565 | -0.0508 | 0.0615 | 52.0642 | 4.999 | 127.3666 | 10.8771 | 155.2347 | 7.1923 | 0.0661 | 0.066 |
| xgboost | 5 | 0.0886 | 0.011633 | 0.5874 | 0.0488 | 0.7133 | 0.0565 | -0.058 | 0.0549 | 50.9357 | 4.8983 | 128.1677 | 10.3144 | 154.3947 | 7.3803 | 0.0802 | 0.0564 |
| linear_regression | 5 | 0.0159 | 0.006624 | 0.5937 | 0.0351 | 0.6997 | 0.0545 | -0.0183 | 0.0589 | 52.6689 | 4.1173 | 129.9742 | 13.9069 | 155.0529 | 4.629 | 0.0604 | 0.0892 |
| random_forest | 5 | 0.3643 | 0.064211 | 0.6002 | 0.0364 | 0.7143 | 0.0536 | -0.0611 | 0.0429 | 49.4732 | 1.4378 | 131.2324 | 11.882 | 153.1853 | 5.2328 | 0.1055 | 0.0554 |
| seasonal_naive | 5 | 0.0207 | 0.009007 | 0.6219 | 0.1633 | 0.9573 | 0.1941 | -1.0357 | 1.1106 | 75.8728 | 19.6903 | 135.7734 | 39.8176 | 92.3518 | 17.7967 | -0.0338 | 0.2605 |


### Inventory Forecasting
**Selected Champion Model:** `lightgbm`  
**Selection Rationale:** Selected 'lightgbm' achieving best mean mae=9.4020 (improvement of 9.1335 / 49.28% over linear_regression mae=18.5355).  

#### Cross-Validation Benchmark Table
| model_name | n_splits | mean_fit_time_sec | mean_inference_time_sec | mean_mae | std_mae | mean_rmse | std_rmse | mean_r2 | std_r2 | mean_mape | std_mape | mean_wape | std_wape | mean_smape | std_smape | mean_forecast_bias | std_forecast_bias |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightgbm | 5 | 0.0981 | 0.020196 | 9.402 | 2.4032 | 12.2863 | 2.8757 | 0.9113 | 0.0172 | 29.1379 | 3.7282 | 15.5676 | 0.3586 | 30.37 | 1.9717 | 0.5438 | 1.0171 |
| random_forest | 5 | 0.4129 | 0.080404 | 9.4375 | 2.4738 | 12.3919 | 2.9333 | 0.9099 | 0.0177 | 28.6782 | 1.9931 | 15.6043 | 0.7048 | 29.6428 | 1.6265 | -0.4148 | 0.9606 |
| lightgbm_tuned | 5 | 0.14 | 0.026825 | 9.4957 | 2.261 | 12.287 | 2.6755 | 0.9114 | 0.0131 | 31.1226 | 5.2975 | 15.7834 | 0.9057 | 30.2917 | 2.0716 | 0.3072 | 1.7331 |
| xgboost | 5 | 0.1173 | 0.015408 | 9.9066 | 2.5819 | 12.8281 | 3.0767 | 0.9036 | 0.0186 | 30.1407 | 4.3833 | 16.3859 | 0.5671 | 30.8568 | 1.938 | 0.051 | 1.5821 |
| linear_regression | 5 | 0.0291 | 0.014356 | 18.5355 | 8.278 | 22.8971 | 8.0773 | 0.6431 | 0.3087 | 65.686 | 47.9989 | 32.128 | 17.2965 | 61.998 | 30.6019 | -12.2185 | 11.2564 |
| naive | 5 | 0.0307 | 0.017413 | 65.6282 | 25.8451 | 74.7545 | 26.4872 | -2.3272 | 1.4742 | 297.9654 | 127.9445 | 107.0596 | 29.6603 | 85.6199 | 6.984 | 50.5646 | 48.4643 |

