from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision import models, transforms
from torchvision.models import (
    EfficientNet_B0_Weights,
    MobileNet_V3_Small_Weights,
    ResNet18_Weights,
)


IMAGE_NET_MEAN = (0.485, 0.456, 0.406)
IMAGE_NET_STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class DefectTypeMetadata:
    architecture: str
    taxonomy: str
    image_size: int
    label_names: list[str]


def build_model(architecture: str, num_classes: int, pretrained: bool = True) -> nn.Module:
    architecture = architecture.lower()

    if architecture == "mobilenet_v3_small":
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        try:
            model = models.mobilenet_v3_small(weights=weights)
        except Exception:
            model = models.mobilenet_v3_small(weights=None)
        in_features = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(in_features, num_classes)
        return model

    if architecture == "resnet18":
        weights = ResNet18_Weights.DEFAULT if pretrained else None
        try:
            model = models.resnet18(weights=weights)
        except Exception:
            model = models.resnet18(weights=None)
        in_features = model.fc.in_features
        model.fc = nn.Linear(in_features, num_classes)
        return model

    if architecture == "efficientnet_b0":
        weights = EfficientNet_B0_Weights.DEFAULT if pretrained else None
        try:
            model = models.efficientnet_b0(weights=weights)
        except Exception:
            model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
        return model

    raise ValueError(f"Unsupported architecture: {architecture}")


def build_image_transform(image_size: int, train: bool) -> transforms.Compose:
    if train:
        return transforms.Compose(
            [
                transforms.Resize((image_size + 24, image_size + 24)),
                transforms.RandomResizedCrop(image_size, scale=(0.82, 1.0), ratio=(0.9, 1.1)),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomRotation(degrees=8),
                transforms.RandomAutocontrast(p=0.25),
                transforms.ColorJitter(brightness=0.12, contrast=0.12, saturation=0.12, hue=0.03),
                transforms.RandomApply([transforms.GaussianBlur(kernel_size=3)], p=0.15),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGE_NET_MEAN, std=IMAGE_NET_STD),
            ]
        )

    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGE_NET_MEAN, std=IMAGE_NET_STD),
        ]
    )


def load_checkpoint(checkpoint_path: str | Path, device: str | torch.device = "cpu") -> tuple[nn.Module, DefectTypeMetadata]:
    # weights_only=False: checkpoint là file cục bộ đáng tin cậy, chứa metadata
    # (numpy scalar) không nằm trong whitelist mặc định của torch.load (PyTorch >= 2.6).
    payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    metadata = DefectTypeMetadata(
        architecture=str(payload["architecture"]),
        taxonomy=str(payload["taxonomy"]),
        image_size=int(payload["image_size"]),
        label_names=list(payload["label_names"]),
    )
    model = build_model(metadata.architecture, len(metadata.label_names), pretrained=False)
    model.load_state_dict(payload["state_dict"])
    model.to(device)
    model.eval()
    return model, metadata


def predict_pil(
    model: nn.Module,
    image: Image.Image,
    image_size: int,
    device: str | torch.device = "cpu",
) -> dict[str, Any]:
    transform = build_image_transform(image_size=image_size, train=False)
    tensor = transform(image.convert("RGB")).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1)[0]
        confidence, class_id = torch.max(probs, dim=0)
    return {
        "class_id": int(class_id.item()),
        "confidence": float(confidence.item()),
        "probabilities": probs.detach().cpu().tolist(),
    }


def top_k_predictions(probs: torch.Tensor, label_names: list[str], top_k: int = 3) -> list[dict[str, Any]]:
    values, indices = torch.topk(probs, k=min(top_k, probs.shape[-1]))
    results: list[dict[str, Any]] = []
    for value, index in zip(values.tolist(), indices.tolist()):
        results.append({"label": label_names[index], "confidence": float(value)})
    return results


def make_label_display(label: str, taxonomy: str) -> str:
    if taxonomy == "composite" and "__" in label:
        return label.split("__", 1)[1]
    return label
