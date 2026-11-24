# Machine Learning Models Documentation

## 1. Overview
The platform integrates 5 production-grade champion machine learning models trained on leak-free temporal feature sets. Models are serialized with full feature lists, categorical encodings, hyperparameters, and evaluation metrics in `data/models/`.

---

## 2. Champion Model Catalog

### 2.1 Hotel Cancellation Risk Predictor (`hotel_cancellation`)
- **Task:** Binary classification estimating the probability that a booking cohort will cancel.
- **Algorithm:** LightGBM Classifier (`LGBMClassifier`) with Scikit-Learn preprocessing pipeline.
- **Key Features:** Lead time days, ADR, stay duration, arrival month/day-of-week, market segment, distribution channel, customer type.
- **Prototype Currency Normalization:** Converts INR selling price to EUR ADR using prototype scaling rate ($90\times$) to match European training data distribution, followed by Bayesian shrinkage ($\lambda = 0.70$) against baseline destination priors.
- **Artifacts:** `data/models/hotel_cancellation/estimator.joblib`, `preprocessor.joblib`, `metadata.json`.

### 2.2 Flight Price Predictor (`flight_price`)
- **Task:** Regression predicting consumer market clearing prices for flight itineraries.
- **Algorithm:** Gradient Boosted Regressor.
- **Key Features:** Origin-destination route, advance purchase window, airline carrier, number of stops, departure day-of-week.
- **Role in Optimization:** Establishes market ceiling price $p_{\text{market}}$ to compute price elasticity:
  $$\theta_{\text{adj}} = \theta_0 \cdot \left(\frac{p_{\text{market}}}{p_{\text{contract}}}\right)^\eta$$
- **Artifacts:** `data/models/flight_price/estimator.joblib`, `metadata.json`.

### 2.3 Search Demand Volume Forecaster (`demand_forecasting`)
- **Task:** Regression forecasting customer search demand volume per destination.
- **Algorithm:** Gradient Boosted Regressor.
- **Key Features:** Historical search rolling averages, seasonal demand indices, holiday/festival flags.
- **Role in Optimization:** Establishes destination demand absorption ceilings.
- **Artifacts:** `data/models/demand_forecasting/estimator.joblib`, `metadata.json`.

### 2.4 Inventory Depletion Forecaster (`inventory_forecasting`)
- **Task:** Regression estimating inventory burn/depletion rates across travel windows.
- **Artifacts:** `data/models/inventory_forecasting/estimator.joblib`, `metadata.json`.

### 2.5 Supplier Lead Time Predictor (`supplier_lead_time_prediction`)
- **Task:** Regression predicting supplier fulfillment latency and reliability.
- **Artifacts:** `data/models/supplier_lead_time_prediction/estimator.joblib`, `metadata.json`.
