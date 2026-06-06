"""
SageMaker Training Job script: blood demand forecasting model.

Input:  s3://<bucket>/data/Dataset.csv
Output: s3://<bucket>/models/demand_model.pkl

Trains a GradientBoostingRegressor to predict units_needed
given blood_group + day_of_week + days_since_epoch.
"""
import os
import io
import json
import argparse
import logging
from datetime import date, timedelta
from collections import defaultdict

import boto3
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bloodbridge.sagemaker")

BLOOD_GROUPS = [
    "O Positive", "O Negative", "A Positive", "A Negative",
    "B Positive", "B Negative", "AB Positive", "AB Negative",
]


def load_data(s3_bucket: str, s3_key: str) -> pd.DataFrame:
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    df = pd.read_csv(io.BytesIO(obj["Body"].read()))
    logger.info(f"Loaded {len(df)} rows from s3://{s3_bucket}/{s3_key}")
    return df


def build_demand_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each patient record, extract:
    - blood_group (encoded)
    - day_of_week from expected_next_transfusion_date
    - days_since_epoch
    - quantity_required (target)
    """
    patients = df[df["role"] == "Patient"].copy()
    patients = patients.dropna(subset=["expected_next_transfusion_date"])

    records = []
    epoch = date(2020, 1, 1)

    for _, row in patients.iterrows():
        try:
            transfusion_date = pd.to_datetime(row["expected_next_transfusion_date"]).date()
            days_since_epoch = (transfusion_date - epoch).days
            day_of_week = transfusion_date.weekday()
            blood_group = str(row.get("bridge_blood_group") or row.get("blood_group", "O Positive"))
            qty = int(row.get("quantity_required") or 1)
            freq = int(row.get("frequency_in_days") or 21)

            records.append({
                "blood_group": blood_group,
                "day_of_week": day_of_week,
                "days_since_epoch": days_since_epoch,
                "frequency_in_days": freq,
                "quantity_required": qty,
            })
        except Exception:
            continue

    features_df = pd.DataFrame(records)
    logger.info(f"Feature rows: {len(features_df)}")
    return features_df


def train(df: pd.DataFrame, output_dir: str):
    le = LabelEncoder()
    df["blood_group_enc"] = le.fit_transform(df["blood_group"])

    X = df[["blood_group_enc", "day_of_week", "days_since_epoch", "frequency_in_days"]].values
    y = df["quantity_required"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    logger.info(f"Model MAE: {mae:.3f}")

    os.makedirs(output_dir, exist_ok=True)
    joblib.dump(model, os.path.join(output_dir, "demand_model.pkl"))
    joblib.dump(le, os.path.join(output_dir, "label_encoder.pkl"))

    metrics = {"mae": round(float(mae), 4), "n_train": len(X_train), "n_test": len(X_test)}
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f)

    logger.info(f"Model saved to {output_dir}")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-bucket", default=os.environ.get("S3_BUCKET", "bloodbridge-data"))
    parser.add_argument("--s3-key", default=os.environ.get("S3_KEY", "data/Dataset.csv"))
    parser.add_argument("--output-dir", default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    args = parser.parse_args()

    df = load_data(args.s3_bucket, args.s3_key)
    features = build_demand_features(df)
    metrics = train(features, args.output_dir)
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
