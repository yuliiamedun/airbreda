"""Train the NO2 regression on training_data.csv and save model.pkl."""

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

df = pd.read_csv("training_data.csv")
X = df[["total_intensity_veh_per_hr", "hour_of_day"]]
y = df["no2_ug_m3"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = LinearRegression().fit(X_train, y_train)

print("Rows:", len(df), "| train:", len(X_train), "| test:", len(X_test))
print("TRAIN  R2:", r2_score(y_train, model.predict(X_train)),
      "MAE:", mean_absolute_error(y_train, model.predict(X_train)))
print("TEST   R2:", r2_score(y_test, model.predict(X_test)),
      "MAE:", mean_absolute_error(y_test, model.predict(X_test)))
print("Coefficients:", dict(zip(X.columns, model.coef_)))

# Refit on all rows for the deployed model, since the test score is already recorded
final = LinearRegression().fit(X, y)
joblib.dump(final, "model.pkl")