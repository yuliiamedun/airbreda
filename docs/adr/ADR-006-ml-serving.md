# ADR-006: ML Serving Architecture

## Context

The dashboard needs to show a predicted NO2 value and an exceedance risk (0–1) for each of the four NDW sites.
I train the model using my own data: NO2 readings from Luchtmeetnet and traffic data from four NDW sites. I combine them by hour, keeping only hours where all four sites have data. On Day 4, this gave me 47 rows.

Traffic data is the main limitation because NDW only provides the latest snapshot. If a scheduled run fails, that hour is lost.

The model also needs to be small and fast because it runs on a VM with only 1 GB RAM.

## Decision

### 1. A linear regression is the right amount of model

The model predicts `no2_ug_m3` from two features: `total_intensity_veh_per_hr` (the sum of the four sites) and `hour_of_day` (Amsterdam time). That is three parameters for 47 rows. With only so many rows, I don't have enough data for a more complex model. Linear regression is simpler and less likely to overfit.

Results with an 80/20 random split (37 train rows, 10 test rows):

| | R² | MAE (µg/m³) |
|---|---|---|
| Train | 0.21 | 6.4 |
| Test | **−0.30** | **8.5** |

The negative test R2 means the model performs worse than simply predicting the average NO₂ value. So, it doesn't have reliable predictive power yet.

I retrained it on all 47 rows for deployment. An earlier result on 25 rows looked better, but dropped as more data was added, showing how unstable these results are with such a small dataset.

**What would change this answer.** After collecting several months or a year of data. I could then include weather features like wind and temperature, which probably affect NO2 more than traffic alone, and consider more complex models.

### 2. Exceedance risk: sigmoid around a threshold

```
no2_exceedance_risk = 1 / (1 + exp(−0.2 × (predicted_no2 − 25)))
```

The risk is 0.5 when the prediction equals the threshold, rises toward 1 above it and falls toward 0 below it. With these settings, a prediction of 15 gives about 0.12 and 35 gives about 0.88.

- **Threshold 25 µg/m³:** the WHO 2021 24-hour guideline for NO₂ (WHO Global Air Quality Guidelines 2021). It falls inside the observed range of roughly 9–44 µg/m³, so the risk actually varies. The EU hourly limit of 200 µg/m³ would give a risk near 0 for every hour, and the annual values (WHO 10, EU 2030 limit 20 µg/m³) would flag almost every hour.
- **Caveats:** this applies a 24-hour average guideline to single hourly predictions, and a WHO guideline is a health recommendation, not a legal limit.
- **Steepness 0.2:** the course default, not tuned.

**Why not the stretch-goal logistic classifier.** A classifier learns from labelled examples of exceedance hours, and only a few of my 47 hours are above 25 µg/m³. It would have almost nothing to learn from. The sigmoid reuses the regression's output and needs no extra labels. The cost is that the risk inherits all the regression's errors and isn't a calibrated probability.

### 3. Training-serving skew, and why the model is baked into the image

Training-serving skew happens when the model receives different inputs or uses different code or library versions during deployment than during training. I identified four possible issues:

- **Library versions.** This one actually happened. Local testing with Compose showed that the model was pickled with scikit-learn 1.7.2 while the container installed 1.9.1. Loading across versions can change predictions without raising an error. I pinned `scikit-learn==1.7.2`.
- **Feature definitions.** The model expects total traffic from all four sites, not traffic from an individual site. I make sure the API passes the same combined value used during training.
- **Time alignment.** Training uses NO2 and traffic from the same hour. However, the dashboard shows the latest available NO2 reading alongside the latest traffic prediction, so they may come from different hours.
- **Noisy inputs.** NDW traffic values are short measurements scaled to vehicles per hour. This can produce large variations that the model wasn't necessarily trained to handle.

**Why I include the model in the Docker image.**  
 `model.pkl` is trained on my laptop and copied into the dashboard image at build time. The model, the code that loads and calls it, and the pinned library versions then ship as one unit that I tested together with Compose before deploying. If the dashboard retrained live instead, the model in production would change on its own, trained on whatever data had arrived, possibly with different library versions or feature code than I tested, and with no one checking the result before users saw it. Baking it in removes that cause of skew: what runs in production is exactly what was tested. The cost is that the model only changes when I retrain and rebuild the image, so it gets older unless I do that by hand.

### 4. One station is enough for all four sites

All four NDW sites are measurement points at the same interchange (A27, hectometre 63): two on the main carriageway and two on the slip roads. They describe traffic at one location, and the model predicts one NO2 value for that location from their combined traffic. Station NL10240 provides the matching NO2 measurement for that same place, so one station gives the model a real label for every training row.

As a result, all four `/site/{id}` responses return the same actual NO2, predicted NO2 and risk. Only `intensity_veh_per_hr` differs. The prediction describes the interchange, not each road separately.

**What would force a second station.**   
A second interchange elsewhere. NO2 from traffic falls off quickly with distance from the road, so NL10240's readings would not reflect the air at a different location. Training a model for that interchange on NL10240's data would pair its traffic with NO2 that its traffic didn't cause, and the predictions there would be meaningless. The second interchange would need its own nearby station to provide real labels, and either its own model or a model that takes the location as an input.

### 5. If `predict()` fails, `/site/{id}` still answers

`predict()` is called inside a `try` block. If the call raises an error (for example, an unexpected input value), `/site/{id}` still returns HTTP 200 200 with the real `no2_ug_m3`, `intensity_veh_per_hr` and `timestamp`, and sets `no2_ug_m3_predicted` and `no2_exceedance_risk` to `null`. The dashboard then shows "n/a" for the prediction and the real values as normal.

The alternative was to let the error fail the whole request with HTTP 500. I chose partial results because the measurements come from different components (RDS and S3) than the prediction does. A broken model shouldn't hide real air-quality and traffic data that is still correct and useful.

**The downsides.** A client that expects a float for `no2_exceedance_risk` gets `null`, so it must handle that case. And a failed prediction is easy to miss, because the response still has status 200.
The fallback does not cover a missing or corrupt `model.pkl`: the model is loaded when the app starts, so in that case the dashboard fails to start at all. This is caught at build and test time rather than at request time.

## Consequences

- The predictions demonstrate a working pipeline, not a forecast anyone should act on.
- The model must be retrained as data accumulates: rerun `build_training_data.py` and `train_model.py`, then rebuild and redeploy the dashboard image.
- Any evaluation on 10 test rows is unstable. A time-based split will be fairer once there is enough data, because a random split lets neighbouring hours land in both train and test.
- `training_data.csv`, `build_training_data.py`, `train_model.py` and `model.pkl` are in the repository, so the training is reproducible.