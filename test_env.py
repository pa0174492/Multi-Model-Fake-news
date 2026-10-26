import sys
print("Python:", sys.version)

try:
    import torch
    print("Torch:", torch.__version__, "CUDA:", torch.cuda.is_available())
except Exception as e:
    print("Torch error:", e)

try:
    import torchvision
    print("Torchvision:", torchvision.__version__)
except Exception as e:
    print("Torchvision error:", e)

try:
    import transformers
    print("Transformers:", transformers.__version__)
except Exception as e:
    print("Transformers error:", e)

try:
    import xgboost
    print("XGBoost:", xgboost.__version__)
except Exception as e:
    print("XGBoost error:", e)

try:
    import shap
    print("SHAP:", shap.__version__)
except Exception as e:
    print("SHAP error:", e)

try:
    import sklearn
    print("Scikit-learn:", sklearn.__version__)
except Exception as e:
    print("Scikit-learn error:", e)

print("Environment check completed successfully!")
