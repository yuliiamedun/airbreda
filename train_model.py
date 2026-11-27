"""Train the NO2 regression on training_data.csv and save model.pkl."""

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

df = pd.read_csv("training_data.csv")
X = df[["total_intensity_veh_per_hr", "hour_of_day"]]
y = df["no2_ug_m3"]

model = LinearRegression()
model.fit(X, y)

pred = model.predict(X)
print("Rows:", len(df))
print("R2:", r2_score(y, pred))
print("MAE:", mean_absolute_error(y, pred))
print("Coefficients:", dict(zip(X.columns, model.coef_)))
print("Intercept:", model.intercept_)

joblib.dump(model, "model.pkl")