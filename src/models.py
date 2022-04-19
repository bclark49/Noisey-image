import abc
import os
from pathlib import Path
from pyexpat import model
from PyQt5.QtCore import QObject
import os, csv, torch, scipy.io
import numpy as np

if __name__ == '__main__':
    import sys
    sys.path.append('./')

from src.predict_img import new_visualize_result, process_img, predict_img, load_model_from_cfg, visualize_result, transparent_overlays, get_color_palette
from src.mit_semseg.utils import AverageMeter, accuracy, intersectionAndUnion

# import yolov3 stuff:
import src.obj_detector.detect as detect
from src.obj_detector.models import load_model
from src.obj_detector.utils.utils import load_classes

# import efficientNetV2
from src.effdet import create_model, create_evaluator, create_dataset, create_loader
from src.effdet.data import resolve_input_config
from timm.utils import AverageMeter, setup_default_logging
from timm.models.layers import set_layer_config
from torchvision import transforms

# import detr stuff:
from PIL import Image
from src.detr.model import DETRdemo

# import yolov4 stuff:
import src.yolov4.detect as detect_v4
from src.yolov4.models.models import Darknet
from src.yolov4.models.models import load_darknet_weights
import src.yolov4.utils.utils as utils_v4
from src.transforms import letterbox_image
from src.yolov4.utils.general import (check_img_size, non_max_suppression, apply_classifier, scale_coords, xyxy2xywh, strip_optimizer)

currPath = str(Path(__file__).parent.absolute()) + '/'

class Model(abc.ABC):
    """
    Creates and adds models. 
    Requirment: The network needs to be fitted in four main funtions: run, initialize, deinitialize, and draw.   
    """
    def __init__(self, *network_config) -> None:
        self.complexOutput = False
    
    @abc.abstractclassmethod
    def run(self, input):
        raise NotImplementedError

    @abc.abstractclassmethod
    def initialize(self, *kwargs):
        raise NotImplementedError

    @abc.abstractclassmethod
    def deinitialize(self):
        raise NotImplementedError

    @abc.abstractclassmethod
    def draw(self, pred):
        raise NotImplementedError

    @abc.abstractclassmethod
    def draw_single_class(self, pred):
        raise NotImplementedError

    @abc.abstractclassmethod
    def report_accuracy(self):
        raise NotImplementedError

    @abc.abstractproperty
    def outputFormat(self):
        raise NotImplementedError


    def __call__(self):
        pred = self.run()
        return pred

class Segmentation(Model):
    """
    Segmentation Model that inherits the Model class
    It specifies its four main functions: run, initialize, deinitialize, and draw. 
    """
    def __init__(self, *network_config) -> None:
        super().__init__(network_config)
        
        self.complexOutput = True
        self.cfg, self.colors = network_config
        #self.cfg = str(Path(__file__).parent.absolute()) + "/config/ade20k-hrnetv2.yaml"
        # colors
        #self.colors = scipy.io.loadmat(str(Path(__file__).parent.absolute()) + '/data/color150.mat')['colors']
        self.names = {}
        self.complexOutput = True # output is a large matrix. Saving output is a little different than object detector

        with open(str(Path(__file__).parent.absolute()) + '/data/object150_info.csv') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                self.names[int(row[0])] = row[5].split(";")[0]

    def run(self, input):
        if torch.cuda.is_available():
            self.segmentation_module.cuda()
        else:
            self.segmentation_module.cpu()

        img_original, singleton_batch, output_size = process_img(frame = input)

        try:
            # predict
            img_original, singleton_batch, output_size = process_img(frame = input)
            pred = predict_img(self.segmentation_module, singleton_batch, output_size)
        except:
            self.segmentation_module.cpu()

            print("Using cpu")

            # predict
            img_original, singleton_batch, output_size = process_img(frame = input, cpu = 1)
            pred = predict_img(self.segmentation_module, singleton_batch, output_size)
        return pred

    def initialize(self, *kwargs):
        # Network Builders
        print("parsing {}".format(self.cfg))
        self.segmentation_module = load_model_from_cfg(self.cfg)
        
        self.segmentation_module.eval()
        return 0

    def deinitialize(self):
        return -1

    def draw(self, pred, img):
        detectedNames = {"all": [255,255,255]}
        pred_color, org_pred_split = visualize_result(img, pred, self.colors)

        color_palette = get_color_palette(pred, org_pred_split.shape[0], self.names, self.colors, detectedNames)

        # transparent pred on org
        dst = transparent_overlays(img, pred_color, alpha=0.6)

        return {"dst": dst, 
        "segmentation": pred_color, 
        "listOfNames":detectedNames
                }

    def draw_single_class(self, pred, img, selected_class):
        imgs = new_visualize_result(pred, img, selected_class)
        return {"segmentation": imgs[0], "overlay": imgs[1]}

    def report_accuracy(self, pred, pred_truth):
        acc_meter = AverageMeter()
        intersection_meter = AverageMeter()
        union_meter = AverageMeter()

        acc, pix = accuracy(pred, pred_truth)
        intersection, union = intersectionAndUnion(pred, pred_truth, 150)
        acc_meter.update(acc, pix)
        intersection_meter.update(intersection)
        union_meter.update(union)
        
        class_ious = {}
        iou = intersection_meter.sum / (union_meter.sum + 1e-10)
        for i, _iou in enumerate(iou):
            class_ious[i] = _iou
        return iou.mean(), acc_meter.average(), class_ious

    def outputFormat(self):
        return "{}" # hex based output?

    def calculateRatios(self, dets):
        values, counts = np.unique(dets, return_counts=True)
        total_idx = [i for i in range(150)]
        for idx in total_idx:
            if not idx in values:
                counts = np.insert(counts, idx, 0)
        return counts

class YOLOv3(Model):
    """
    YOLO Model that inherits the Model class
    It specifies its four main functions: run, initialize, deinitialize, and draw. 
    """
    def __init__(self, *network_config) -> None:
        super(YOLOv3, self).__init__()
        # network_config: CLASSES, CFG, WEIGHTS
        self.CLASSES, self.CFG, self.WEIGHTS = network_config
        # self.CLASSES = os.path.join(currPath, 'obj_detector/cfg', 'coco.names')
        # self.CFG = os.path.join(currPath, 'obj_detector/cfg', 'yolov3.cfg')
        # self.WEIGHTS = os.path.join(currPath,'obj_detector/weights','yolov3.weights')
        print(self.CLASSES, self.CFG, self.WEIGHTS)
        self.classes = load_classes(self.CLASSES)

    def run(self, input):
        pred = detect.detect_image(self.yolo, input)
        print('PRED YO', pred)
        return pred #[x1,y1,x2,y2,conf,class] <--- box

    def initialize(self, *kwargs):
        self.yolo = load_model(self.CFG, self.WEIGHTS)
        return 0
    
    def deinitialize(self):
        return -1
    
    def draw(self, pred, img):
        np_img, detectedNames = detect._draw_and_return_output_image(img, pred, 416, self.classes)
        return {"dst": np_img,
                "listOfNames":detectedNames}

    def draw_single_class(self, pred, img, selected_class):
        np_img = detect._draw_and_return_output_image_single_class(img, pred, selected_class, self.classes)
        return {"overlay": np_img}

    def report_accuracy(self, pred, pred_truth):
        print('pred comparison', pred, pred_truth)
        return

    def outputFormat(self):
        return "{5:.0f} {4:f} {0:.0f} {1:.0f} {2:.0f} {3:.0f}"

class EfficientDetV2(Model):
    def __init__(self, *network_config) -> None:
        super(EfficientDetV2, self).__init__()

        # network_config: CLASSES, CFG, WEIGHTS
        self.CLASSES, self.CFG = network_config
        self.numClasses = len(self.CLASSES)
        print(self.CLASSES, self.CFG)
        self.classes = load_classes(self.CLASSES)
        self.inputTrans = {
            'efficientdetv2_dt': (768, 768),
            'efficientdet_d1': (640, 640),
            'efficientdet_d2': (768, 768),
            'tf_efficientdetv2_ds': (1024, 1024),
            'efficientdetv2_dt': (768, 768),
            'tf_efficientdet_d7x': (1536, 1536),
            'tf_efficientdet_d4': (1024, 1024)
        }

    def initialize(self, *kwargs):
        self.bench = create_model(
            self.CFG,
            bench_task='predict',
            num_classes=len(self.CLASSES),
            pretrained=True,
        )
        self.bench.eval()

    def run(self, input):
        # input_config = resolve_input_config(None)
        self.transforms = transforms.Compose([
            transforms.ToTensor(),
            transforms.Resize(size=self.inputTrans[self.CFG]),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
        # print('~~~~~~~~~~~~~~INPUT ', np.array([input]))
        scores = self.bench(self.transforms(input).unsqueeze(0))
        print('PRINT',scores[0])
        # resize to match original image
        scores = scores[0].detach().numpy()

        print('BEFORE~~~~~~~~~~~~~~~~~~~~~~~~\n\n', scores)
        print('inputshape: ', input.shape)
        print('transformshape: ', self.inputTrans[self.CFG])
        print('try: ', scores[:, 0], self.inputTrans[self.CFG][1], input.shape[1])
        scores[:, 0] = scores[:, 0] / self.inputTrans[self.CFG][1] * input.shape[1]
        scores[:, 1] = scores[:, 1] / self.inputTrans[self.CFG][0] * input.shape[0]
        scores[:, 2] = scores[:, 2] / self.inputTrans[self.CFG][1] * input.shape[1]
        scores[:, 3] = scores[:, 3] / self.inputTrans[self.CFG][0] * input.shape[0]
        print('AFTER~~~~~~~~~~~~~~~~~~~~~~~~~\n\n', scores)
        return scores[np.where(scores[:,5] > 60)]

    def deinitialize(self):
        return -1

    def draw(self, pred, img):
        np_img, detectedNames = detect._draw_and_return_output_image(img, pred, 416, self.classes)
        return {"dst": np_img,
                "listOfNames":detectedNames}

    def draw_single_class(self, pred, img, selected_class):
        np_img = detect._draw_and_return_output_image_single_class(img, pred, selected_class, self.classes)
        return {"overlay": np_img}

    def report_accuracy(self, pred, pred_truth):
        acc_meter = AverageMeter()
        intersection_meter = AverageMeter()
        union_meter = AverageMeter()

        acc, pix = accuracy(pred, pred_truth)
        intersection, union = intersectionAndUnion(pred, pred_truth, 150)
        acc_meter.update(acc, pix)
        intersection_meter.update(intersection)
        union_meter.update(union)
        
        class_ious = {}
        iou = intersection_meter.sum / (union_meter.sum + 1e-10)
        for i, _iou in enumerate(iou):
            class_ious[i] = _iou
        return iou.mean(), acc_meter.average(), class_ious

    def outputFormat(self):
        return "{5:.0f} {4:f} {0:.0f} {1:.0f} {2:.0f} {3:.0f}"

class DETR(Model):
    """
    DETR Model that inherits the Model class
    It specifies its four main functions: run, initialize, deinitialize, and draw.
    """
    def __init__(self, *network_config) -> None:
        super(DETR, self).__init__()
        self.CLASSES, self.WEIGHTS = network_config[0], network_config[1]
        print(self.CLASSES, self.WEIGHTS)
        self.classes = load_classes(self.CLASSES)
    
    def initialize(self, *kwargs):
        self.model = DETRdemo(num_classes=len(self.classes))
        self.model.load_state_dict(torch.load(self.WEIGHTS))
        self.model.eval()
        if torch.cuda.is_available():
            self.model.cuda()
            self.on_gpu = True
        else:
            self.model.cpu()
            self.on_gpu = False
        self.transform = transforms.Compose([
            transforms.Resize(800),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        return 0

    def run(self, input):
        tfms = transforms.ToPILImage()
        img = tfms(input)
        if self.on_gpu: img = img.cuda()
        scores, boxes = self.model.detect(img, self.model, self.transform)
        _confidences, _classes = torch.max(scores, axis=1)
        _cls_conf = torch.cat((torch.unsqueeze(_confidences, axis=0), torch.unsqueeze(_classes, axis=0)))
        _cls_conf = torch.transpose(_cls_conf, 0,1)
        pred = torch.cat((boxes, _cls_conf), axis=1) #[x1,y1,x2,y2,conf,class] <--- box
        return pred

    def deinitialize(self):
        return -1

    def draw(self, pred, img):
        np_img, detectedNames = detect._draw_and_return_output_image(img, pred, 416, self.classes)
        return {"dst": np_img,
                "listOfNames":detectedNames}

    def draw_single_class(self, pred, img, selected_class):
        np_img = detect._draw_and_return_output_image_single_class(img, pred, selected_class, self.classes)
        return {"overlay": np_img}

    def report_accuracy(self, pred, pred_truth):
        print('pred comparison', pred, pred_truth)
        return

    def outputFormat(self):
        return "{5:.0f} {4:f} {0:.0f} {1:.0f} {2:.0f} {3:.0f}"

class YOLOv4(Model):
    """
    YOLOv4 Model that inherits the Model class
    It specifies its four main functions: run, initialize, deinitialize, and draw. 
    """
    def __init__(self, *network_config) -> None:
        super(YOLOv4, self).__init__()
        # network_config: CLASSES, CFG, WEIGHTS
        self.CLASSES, self.CFG, self.WEIGHTS = network_config
        self.img_size = (416,416)
        print(self.CLASSES, self.CFG, self.WEIGHTS)
        self.classes = load_classes(self.CLASSES)
        self.conf_threshold = 0.25

    def run(self, input):
        im0 = np.copy(input)
        img = letterbox_image(input, self.img_size)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3x416x416
        img = np.ascontiguousarray(img)
        if torch.cuda.is_available():
            img = torch.from_numpy(img).cuda()
        else:
            img = torch.from_numpy(img).cpu()
        img = img.float()
        img /= 255.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)
        pred = self.yolo(img, augment=False)[0]
        pred = non_max_suppression(pred, self.conf_threshold, 0.6, classes=None, agnostic=False)
        #return pred #[x1,y1,x2,y2,conf,class] <--- box
        for i, det in enumerate(pred):  # detections per image
            if det is not None and len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()
        if torch.cuda.is_available():
            pred = pred.cpu()
        pred = pred[0].detach().numpy()
        #print(self.yolo.training)
        return pred

    def initialize(self, *kwargs):
        self.yolo = Darknet(self.CFG, self.img_size)
        if torch.cuda.is_available():
            self.yolo = self.yolo.cuda()
        else:
            self.yolo = self.yolo.cpu()
        load_darknet_weights(self.yolo, self.WEIGHTS)
        self.yolo.eval()
    
    def deinitialize(self):
        return -1
    
    def draw(self, pred, img):
        np_img, detectedNames = detect._draw_and_return_output_image(img, pred, 416, self.classes)
        return {"dst": np_img,
                "listOfNames":detectedNames}

    def draw_single_class(self, pred, img, selected_class):
        np_img = detect._draw_and_return_output_image_single_class(img, pred, selected_class, self.classes)
        return {"overlay": np_img}

    def report_accuracy(self, pred, pred_truth):
        print('pred comparison', pred, pred_truth)
        return

    def outputFormat(self):
        return "{5:.0f} {4:f} {0:.0f} {1:.0f} {2:.0f} {3:.0f}"


_registry = {
    'Semantic Segmentation': Segmentation(
        str(Path(__file__).parent.absolute()) + "/mit_semseg/config/ade20k-hrnetv2.yaml",
        scipy.io.loadmat(str(Path(__file__).parent.absolute()) + '/data/color150.mat')['colors']
    ),
    'Object Detection (YOLOv3)': YOLOv3(
        os.path.join(currPath, 'obj_detector', 'cfg', 'coco.names'),
        os.path.join(currPath, 'obj_detector', 'cfg', 'yolov3.cfg'),
        os.path.join(currPath,'obj_detector', 'weights', 'yolov3.weights')
    ),
    'EfficientDetV2': EfficientDetV2(
        os.path.join(currPath, 'obj_detector/cfg', 'coco.names'),
        'efficientdetv2_dt'
    ),
    'Object Detection (DETR)': DETR(
        os.path.join(currPath, 'detr', 'cfg', 'coco.names'),
        os.path.join(currPath, 'detr', 'weights', 'detr.weights')
    ),
    'Object Detection (YOLOv4)': YOLOv4(
        os.path.join(currPath, 'yolov4', 'data', 'coco.names'),
        os.path.join(currPath, 'yolov4', 'cfg', 'yolov4.cfg'),
        os.path.join(currPath,'yolov4', 'weights', 'yolov4.weights')
    )
}


if __name__ == '__main__':
    import cv2
    model = _registry['Object Detection (YOLOv4)']
    model.initialize()
    img = cv2.imread('imgs/default_imgs/original.png')
    assert type(img) != None # image path wrong
    preds = model.run(img)
    print(preds) # right format if last is 0<x<1 and first 4 are large numbers