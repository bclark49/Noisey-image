import os
import yaml
import argparse
from pathlib import Path

import numpy as np
import torch
#import torch.nn as nn
#from torch.utils.data import DataLoader
from src.cae.src.data_loader import preprocess_single
from src.cae.src.utils import save_imgs

from src.cae.src.namespace import Namespace
from src.cae.src.logger import Logger

from src.cae.src.models.cae_32x32x32_zero_pad_bin import CAE
import cv2

ROOT_EXP_DIR = Path(__file__).resolve().parents[1] / "experiments"

logger = Logger(__name__, colorize=True)


def main(config, image, patch_size, size) -> None:
    with open(config, "rt") as fp:
        cfg = Namespace(**yaml.safe_load(fp))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    img = detect(cfg, image, patch_size, show_stats=size)
    return img

def detect(cfg: Namespace, image, patch_size, show_stats=False, resize=False) -> None:
    assert cfg.checkpoint not in [None, ""]
    assert cfg.device == "cpu" or (cfg.device == "cuda" and torch.cuda.is_available())

    exp_dir = ROOT_EXP_DIR / cfg.exp_name
    os.makedirs(exp_dir / "out", exist_ok=True)
    cfg.to_file(exp_dir / "test_config.json")
    logger.info(f"[exp dir={exp_dir}]")

    model = CAE(cfg, check_size=show_stats)
    model.load_state_dict(torch.load(cfg.checkpoint))
    model.eval()
    if cfg.device == "cuda":
        model.cuda()
    logger.info(f"[model={cfg.checkpoint}] on {cfg.device}")

    image_shape = image.shape
    img, patches, pad_img, pad, pwh = preprocess_single(image, patch_size)

    if cfg.device == "cuda":
        patches = patches.cuda()

    #out = T.zeros(6, 10, 3, 128, 128)
    ps = patches.shape
    out = torch.zeros(ps[1], ps[2], ps[0], ps[3], ps[4])

    for i in range(pad[1]):
        for j in range(pad[0]):
            x = patches[:, i, j, :, :]
            x = torch.unsqueeze(x, axis=0)
            if resize:
                x = nn.functional.interpolate(x, size=(128,128), mode='bilinear')
            if cfg.device == "cuda":
                x.cuda()
            y = model(x)
            if resize:
                y = nn.functional.interpolate(y, size=(patch_size,patch_size), mode='bilinear')
            y = y[0]
            out[i, j] = y.data
    
    # save output
    out = np.transpose(out, (0, 3, 1, 4, 2))
    out = np.reshape(out, (pad_img[0], pad_img[1], 3))
    #out = np.transpose(out, (2, 0, 1))

    #y = torch.cat((img, out), dim=2)

    if show_stats:
        print("Original size (bytes): %i"%(model.original_file_size))
        print("Compressed size (bytes): %i"%(model.compressed_file_size))

    '''
    save_imgs(
        imgs=out,
        to_size=(3, pad_img[0], 2 * pad_img[1]),
        name=exp_dir / f"out/custom.png",
        img_shape=image_shape
    )
    '''
    #print(out)
    #print(image)
    out *= 255.0
    out = out.clamp(0,255.0)
    out = out.cpu().numpy()
    out = out.astype(np.uint8)
    out = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    out = out[pwh[0][1]:image.shape[0]+pwh[0][1], pwh[0][0]:image.shape[1]+pwh[0][0],:]

    _name1 = str(exp_dir/f"out/custom_pre.png")
    _name2 = str(exp_dir/f"out/custom.png")

    cv2.imwrite(_name1, image)
    cv2.imwrite(_name2, out)

    return out