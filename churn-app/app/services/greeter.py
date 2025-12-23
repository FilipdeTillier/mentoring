from churn_lib.preprocessing import preprocess


def say_hello() -> dict:
    df = preprocess()

    return {
        "message": "Hello from churn-app!",
        "dataframe": {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "data": df.to_dict(orient="records")
        }
    }
