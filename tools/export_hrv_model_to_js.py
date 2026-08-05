from __future__ import annotations

import json
from pathlib import Path

import joblib


ROOT = Path(__file__).resolve().parents[3]
APP_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "hrv_stress_classifier_mean_hr_bundle.pkl"
OUTPUT_PATH = APP_DIR / "hrv_stress_model.js"


def tree_to_dict(tree):
    return {
        "children_left": tree.children_left.tolist(),
        "children_right": tree.children_right.tolist(),
        "feature": tree.feature.tolist(),
        "threshold": tree.threshold.tolist(),
        "value": tree.value.squeeze(axis=1).tolist(),
    }


def main() -> None:
    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    payload = {
        "modelName": bundle.get("model_name", "Random Forest with mean_hr"),
        "task": bundle.get("task", "WESAD baseline vs stress classification"),
        "featureCols": bundle["feature_cols"],
        "classes": model.classes_.tolist(),
        "trees": [tree_to_dict(estimator.tree_) for estimator in model.estimators_],
    }

    js = (
        "window.HRV_STRESS_MODEL = "
        + json.dumps(payload, separators=(",", ":"))
        + ";\n"
    )
    OUTPUT_PATH.write_text(js, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    print(f"trees: {len(payload['trees'])}")
    print(f"classes: {payload['classes']}")
    print(f"features: {payload['featureCols']}")


if __name__ == "__main__":
    main()
