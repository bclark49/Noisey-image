# System libs
import os
import yaml
import json
import xml.etree.ElementTree as ET

# PyQt5
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

# import utilities:
from src.yamlDialog import Ui_Dialog

def read_yaml(self, filePath):
    filePaths = []

    # Parse user-created YAML file to dataset
    with open(filePath) as file:
        documents = yaml.full_load(file)

    # Track what needs to be trained, validated, and tested
    trainVT = []        
    if("train" in documents):
        trainVT.append("train")
    if("val" in documents):
        trainVT.append("val")
    if("test" in documents):
        trainVT.append("test")
    
    if(len(trainVT) > 1):
        dialogUI = Ui_Dialog()
        dialog = QtWidgets.QDialog()
        dialogUI.setupUi(dialog)

        for x in trainVT:
            item = QtWidgets.QListWidgetItem()
            item.setText(x)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            dialogUI.listWidget.addItem(item)

        dialog.exec_()

        if(dialog.result() == 0):
            return []

        checkedItems = []
        for index in range(dialogUI.listWidget.count()):
            if dialogUI.listWidget.item(index).checkState() == Qt.Checked:
                checkedItems.append(dialogUI.listWidget.item(index).text())
    else:
        checkedItems = trainVT

    # Adds file paths to files within folders specified
    for x in checkedItems:
        if(isinstance(documents[x], list)):
            filePaths.extend(documents[x])
        else:
            filePaths.append(documents[x])

    # Assign root path to dataset specified
    if "root" in documents:
        root = documents["root"]
    else: 
        root = filePath[:filePath.rfind('/') + 1]

    # Append root to include specific path
    if "path" in documents:
        root = os.path.join(root, documents["path"])

    filePaths = list(map(lambda path: root + path, filePaths))

    # Stores path to files stored in directories
    for file in filePaths:
        if(os.path.isdir(file)):
            onlyfiles = [f for f in os.listdir(file) if os.path.isfile(os.path.join(file, f))]
            onlyfiles = list(map(lambda path: os.path.join(file, path), onlyfiles))
    
            filePaths.remove(file)
            filePaths.extend(onlyfiles)

    # Parses label files according to dataset type (currently accepts .txt, .xml) -> Future: .json
    if "labels" in documents:
        labels_folder = os.path.join(root, documents["labels"])
        onlylabels = [f for f in os.listdir(labels_folder) if os.path.isfile(os.path.join(labels_folder, f))]
        labels = list(map(lambda path: os.path.join(labels_folder, path), onlylabels))
        labels_dic = {}

        # Parses .xml annotation files and stores in dictionary as the following:
        # { filename: [width, height, [objects]] }
        if documents["type"] == "voc":
            for label in labels:
                file_content = []
                with open(label) as f:
                    tree_root = ET.parse(f).getroot()
                
                objects = []
                for x in tree_root.findall("object"):
                    obj_class = [x[i].text for i in range(4)]
                    coords = [x[4][i].text for i in range(len(x[4]))]
                    obj_class.append(coords)
                    objects.append(obj_class)
                    
                file_content = [tree_root[4][0].text, tree_root[4][1].text, objects]
                labels_dic[tree_root[1].text] = file_content
        # elif documents["type"] == "coco" -> parses .json files for this COCO dataset -> SKYLAR
        elif documents["type"] == "coco":
           for label in labels:
               with open(label) as f:
                   instances = json.load(f)
                   for i in instances['images']:
                       name = i['file_name']
                       labels_dic[name] = {}
                       labels_dic[name]['height'] = i['height']
                       labels_dic[name]['width'] = i['width']
                   for i in instances['annotations']:
                       findid = i['image_id']
                       fix_string = str(findid).zfill(12)
                       fix_string = fix_string + '.jpg'
                       labels_dic[fix_string]['category_id'] = i['category_id']
                       labels_dic[fix_string]['bbox'] = i['bbox']
           f.close()    
        else:
            # Parses .txt annotation files
            for label in labels:
                file_content = []
                with open(label) as f:
                    for line in f:
                        _list = line.split()
                        if type(_list) == list:
                            _list = list(map(float, _list))
                        file_content.append(_list)
                base=os.path.basename(label)
                labels_dic[os.path.splitext(base)[0]] = file_content

        self.labels = labels_dic

    return filePaths