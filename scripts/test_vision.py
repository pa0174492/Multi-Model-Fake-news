import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import numpy as np

print("Testing ResNet18 image feature extractor...")
try:
    weights = models.ResNet18_Weights.DEFAULT
    model = models.resnet18(weights=weights)
    model.eval()
    
    # Strip final classification layer to use as 512-dim feature extractor
    feature_extractor = torch.nn.Sequential(*list(model.children())[:-1])
    feature_extractor.eval()
    
    transform = weights.transforms()
    
    # Create a dummy image
    dummy_img = Image.fromarray(np.uint8(np.random.rand(224, 224, 3) * 255))
    tensor = transform(dummy_img).unsqueeze(0)
    
    with torch.no_grad():
        feat = feature_extractor(tensor)
        feat = torch.flatten(feat, 1)
        print("Image feature shape:", feat.shape)
    print("ResNet18 feature extractor test PASSED!")
except Exception as e:
    print("Error with ResNet18:", e)
