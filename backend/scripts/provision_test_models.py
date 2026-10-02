"""Pre-provision tiny seeded CPU model fixtures; never download pretrained weights."""

import argparse
from pathlib import Path

import torch
from transformers import BertConfig, BertModel, CLIPConfig, CLIPModel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    destination = parser.parse_args().destination
    torch.set_num_threads(1)
    torch.manual_seed(0)
    text = BertModel(
        BertConfig(
            vocab_size=16,
            hidden_size=384,
            num_hidden_layers=1,
            num_attention_heads=6,
            intermediate_size=32,
            max_position_embeddings=16,
        )
    )
    text.save_pretrained(destination / "text")
    image = CLIPModel(
        CLIPConfig(
            projection_dim=512,
            text_config={
                "vocab_size": 16,
                "hidden_size": 32,
                "intermediate_size": 32,
                "num_hidden_layers": 1,
                "num_attention_heads": 4,
                "max_position_embeddings": 16,
                "bos_token_id": 2,
                "eos_token_id": 3,
                "pad_token_id": 0,
            },
            vision_config={
                "hidden_size": 32,
                "intermediate_size": 32,
                "num_hidden_layers": 1,
                "num_attention_heads": 4,
                "image_size": 16,
                "patch_size": 8,
            },
        )
    )
    image.save_pretrained(destination / "image")
    print("Provisioned seeded text/CLIP fixtures locally; no pretrained downloads.")


if __name__ == "__main__":
    main()
