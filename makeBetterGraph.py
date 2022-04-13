'''
Run this script against the folder from the experiment
at ./src/data/tmp/runs/...

example: python makeBetterGraph.py --folder src/data/tmp/runs/exp_28/
'''


import matplotlib.pyplot as plt
import argparse
import os
import numpy as np
import yaml


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', '-f', type=str,)
    args = parser.parse_args()

    map50s = np.load( os.path.join(args.folder, 'graphing.npy') )
    print(map50s)
    with open( os.path.join(args.folder, 'meta.yaml') , 'r') as f:
        metadata = yaml.safe_load(f)

    plt.figure(figsize=(7.5,5))
    for i, noise in enumerate(metadata.keys()):
        xaxis = metadata[noise]
        mAP = map50s[i]
        plt.plot(xaxis, mAP,'-o')

    plt.title('Gaussian Noise vs MTCNN mAP')
    plt.ylabel('mAP')
    plt.xlabel('Standard Deviation')
    plt.show()
    