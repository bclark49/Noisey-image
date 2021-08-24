import os
import cv2
import random
import argparse
import numpy as np
import matplotlib.pyplot as plt

from src.noises import *

def add_noise_img(img, level):
    #img = cv2.imread(img)
   # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    org_img = img.copy()
    
    #frame = saltAndPapper_noise(org_img, level)
    frame = sp_noise(org_img, level)

    # frame = cv2.putText(frame, "salt & papper", (int(frame_width*0.6),50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2, cv2.LINE_AA)
    # frame = cv2.putText(frame, "amount = {:.5f}".format(amount), (int(frame_width*0.6),100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2, cv2.LINE_AA)
        
    #cv2.imshow('frame', frame)
    #cv2.imwrite(save, frame)

    #img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    #img_rgb_notext = cv2.cvtColor(frame_notext, cv2.COLOR_BGR2RGB)
    return frame

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Apply noise to an image and write to an image file")
    parser.add_argument("-i", "--img", required=True, type=str, metavar='', help="an image path")
    parser.add_argument("-l", "--level", default=0.001, type=float, metavar='', help="noise level")
    parser.add_argument("-s", "--save", default="out_img.jpg", type=str, metavar='', help="save image path")
    
    args = parser.parse_args()

    img = cv2.imread(args.img)
    # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    #cv2.imwrite(args.save, img, (cv2.IMWRITE_PNG_COMPRESSION, 0))

    frame_width = img.shape[1]
    frame_height = img.shape[0]

    amount = args.level
    
    frame = add_noise_img(img, amount)
    
    #frame = cv2.putText(frame, "salt & papper", (int(frame_width*0.80),50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2, cv2.LINE_AA)
    #frame = cv2.putText(frame, "amount = {:.5f}".format(amount), (int(frame_width*0.80),100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2, cv2.LINE_AA)

    cv2.imwrite(args.save, frame)
    # cv2.imshow('frame', frame)
    # cv2.waitKey(0)
    #cv2.destroyAllWindows()