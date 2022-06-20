# System libs
import os
from pathlib import Path
from tkinter import E
import PIL.Image
import numpy as np

# Sementic segmentation
from src.predict_img import new_visualize_result

# PyQt5
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QMessageBox
from src.window import Ui_MainWindow
from PyQt5.QtCore import Qt
from src.yamlDialog import Ui_Dialog

import cv2
from functools import partial
import yaml

# import utilities:
from src.utils.images import convert_cvimg_to_qimg
from src.transforms import AugDialog, AugmentationPipeline, Augmentation, mainAug
from src.experimentDialog import ExperimentConfig, ExperimentDialog
from src import models
from src.utils.qt5extra import CheckState
from src.utils.weights import Downloader
from src.dataParser import *

CURRENT_PATH = str(Path(__file__).parent.absolute()) + '/'
TEMP_PATH = CURRENT_PATH + 'src/tmp_results/'
DEFAULT_PATH = CURRENT_PATH + 'imgs/default_imgs/'

class Worker(QtCore.QObject):
    finished = QtCore.pyqtSignal(tuple)
    progress = QtCore.pyqtSignal(int)

    def setup(self, files, ifDisplay, model_type, listWidgets):
        self.files = files
        self.ifDisplay = ifDisplay
        self.listWidgets = listWidgets
        #assert model_type == 'segmentation' or model_type == 'yolov3', "Model Type %s is not a defined term!"%(model_type)
        self.model_type = model_type

    def run(self):
        model = models._registry[self.model_type]
        self.progress.emit(1)

        model.initialize()
        self.progress.emit(2)

        result = []
        for img in self.files:
            pred = model.run(img)
            temp = model.draw(pred, img)
            temp["pred"] = pred
            result.append(temp)
            self.progress.emit(3)

        self.progress.emit(4)
        model.deinitialize()

        self.finished.emit((result, self.listWidgets))


class mainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.addWindow = AugDialog(self.ui.listAugs)
        self.addWindow.setModal(True)
        self.addWindow.demoAug()

        # Check status of configurations:
        weight_dict = {'mit_semseg':"ade20k-hrnetv2-c1", 'yolov3':"yolov3.weights", 'detr':"detr.weights", 'yolov4':"yolov4.weights", "yolov3-face":"yolov3-face_last.weights", "yolox":"yolox_m.pth"}
        self.labels = []

        if Downloader.check(weight_dict):
            self.downloadDialog = Downloader(weight_dict)
            self.downloadDialog.setModal(True)
            self.downloadDialog.show()

        self.ui.listAugs.setMaximumSize(400,100) # quickfix for sizing issue with layouts
        self.ui.deleteListAug.setMaximumWidth(30)
        self.ui.upListAug.setMaximumWidth(30)
        self.ui.downListAug.setMaximumWidth(30)

        self.ui.progressBar.hide()
        self.ui.progressBar_2.hide()

        self.ui.comboBox.addItems(list(models._registry.keys()))

        # QActions
        # Default values (images, noise, etc.) are set up here:
        self.default_img()

        # Buttons
        self.ui.pushButton.clicked.connect(self.run_model)  
        self.ui.pushButton_2.clicked.connect(self.startExperiment)
        self.ui.pushButton_4.clicked.connect(quit)
        #self.ui.compoundAug.setChecked(True)

        # Augmentation Generator:
        self.ui.addAug.clicked.connect(self.addWindow.show)
        self.ui.demoAug.clicked.connect(self.addWindow.demoAug)
        self.ui.loadAug.clicked.connect(self.addWindow.__loadFileDialog__)
        self.ui.saveAug.clicked.connect(self.addWindow.__saveFileDialog__)
        self.ui.deleteListAug.clicked.connect(self.addWindow.__deleteItem__)
        self.ui.downListAug.clicked.connect(self.addWindow.__moveDown__)
        self.ui.upListAug.clicked.connect(self.addWindow.__moveUp__)
        self.ui.listAugs.itemChanged.connect(self.changePreviewImage)
        # access model of listwidget to detect changes
        self.addWindow.pipelineChanged.connect(self.changePreviewImage)
        #self.ui.runOnAug.stateChanged.connect(self.runAugOnImage)

        # Menubar buttons
        #self.ui.actionOpen.triggered.connect(lambda: self.open_file())
        self.ui.actionOpen.triggered.connect(self.parseData)
        self.ui.actionIncrease_Size.triggered.connect(self.increaseFont)
        self.ui.actionDecrease_Size.triggered.connect(self.decreaseFont)

        # Qlistwidget signals
        self.ui.listWidget.currentItemChanged.connect(self.change_seg_selection)
        self.ui.fileList.currentItemChanged.connect(self.change_file_selection)

        # Font
        font = self.font()
        font.setPointSize(10)
        self.ui.centralwidget.setFont(font)

        # Drag and drop
        self.ui.original.imageDropped.connect(self.open_file)

        self.ui.fileList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.fileList.customContextMenuRequested.connect(self.listwidgetmenu)
        self.ui.fileList.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection
        )
        self.ui.listAugs.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.label_eval = None

        # yaml stuff:
        self.yamlThread = QThread()
        self.yamlProgress = ReadYAMLProgressWindow()
        self.yamlQueue = Queue()
        self.yamlWorker = yamlWorker(self.yamlQueue)

    def listwidgetmenu(self, position):
        """menu for right clicking in the file list widget"""
        right_menu = QtWidgets.QMenu(self.ui.fileList)
        remove_action = QtWidgets.QAction("close", self, triggered = self.close)

        right_menu.addAction(self.ui.actionOpen)

        if self.ui.fileList.itemAt(position):
            right_menu.addAction(remove_action)

        right_menu.exec_(self.ui.fileList.mapToGlobal(position))

    def close(self):
        """Remoes a file from the file list widget"""
        items = self.ui.fileList.selectedItems()

        for item in items:
            row = self.ui.fileList.row(item)
            self.ui.fileList.takeItem(row)

    def increaseFont(self):
        """Increses the size of font across the whole application"""
        self.ui.centralwidget.setFont(QtGui.QFont('Ubuntu', self.ui.centralwidget.fontInfo().pointSize() + 1))
        #print(self.ui.centralwidget.fontInfo().pointSize())

    def decreaseFont(self):
        """Decreses the size of font across the whole application"""
        self.ui.centralwidget.setFont(QtGui.QFont('Ubuntu', self.ui.centralwidget.fontInfo().pointSize() - 1))
        
    def apply_augmentations(self, img):
        for aug in mainAug:
            img = aug(img, example=True)
        return img

    def changePreviewImage(self, *kwargs):
        #print(kwargs)
        print("recreating noisey image")
        current_item = self.ui.fileList.currentItem()
        image = cv2.imread(current_item.data(QtCore.Qt.UserRole)['filePath'])
        #if image is not None:
        image = self.apply_augmentations(image)
        qt_img = convert_cvimg_to_qimg(image)
        self.ui.preview.setPixmap(QtGui.QPixmap.fromImage(qt_img))


    def default_img(self):
        #print(CURRENT_PATH + "imgs/" + fileName)
        if(os.path.isdir(DEFAULT_PATH)):
            onlyfiles = [f for f in os.listdir(DEFAULT_PATH) if os.path.isfile(os.path.join(DEFAULT_PATH, f))]
    
        for file in onlyfiles:
            if(Path(file).stem == "original"):
                original = os.path.join(DEFAULT_PATH, file)
                self.open_file(original)

            if(Path(file).stem == "segmentation"):
                print(Path(file).stem)
                segmentation = os.path.join(DEFAULT_PATH, file)
                qt_img = convert_cvimg_to_qimg(cv2.imread(segmentation))
                self.ui.original_2.setPixmap(QtGui.QPixmap.fromImage(qt_img))

            if(Path(file).stem == "segmentation_overlay"):
                segmentation_overlay = os.path.join(DEFAULT_PATH, file)
                qt_img = convert_cvimg_to_qimg(cv2.imread(segmentation_overlay))
                self.ui.preview_2.setPixmap(QtGui.QPixmap.fromImage(qt_img))

        self.changePreviewImage()

    def open_file(self, filePaths):
        if(isinstance(filePaths, list) == 0):
            filePaths = [filePaths]

        new_item = None

        for filePath in filePaths:
            fileName = os.path.basename(filePath)
            items = self.ui.fileList.findItems(fileName, QtCore.Qt.MatchExactly)
            if len(items) > 0:
                self.ui.statusbar.showMessage("File already opened", 3000)

            new_item = QtWidgets.QListWidgetItem()
            new_item.setText(fileName)
            new_item.setData(QtCore.Qt.UserRole, {'filePath':filePath})
        
            self.ui.fileList.addItem(new_item)


        if(new_item is not None):
            self.ui.original.setPixmap(QtGui.QPixmap(filePath))
            self.ui.fileList.setCurrentItem(new_item)
            self.ui.original_2.clear()
            self.ui.preview_2.clear()
            
    def parseData(self):
        filePaths = QtWidgets.QFileDialog.getOpenFileNames(self, "Select image", filter="Image files (*.jpg *.png *.bmp *.yaml)")
        filePath = filePaths[0][0]

        if filePath.endswith(".yaml"):
            # create read_yaml progress:
            self.yamlProgress.show()

            # disable controls here:

            # run read_yaml on a worker thread:
            self.yamlWorker.filePath = filePath
            self.yamlWorker.moveToThread(self.yamlThread)
            self.yamlThread.started.connect(self.yamlWorker.run)
            self.yamlWorker.finished.connect(self.postParseData)
            self.yamlWorker.finished.connect(self.yamlWorker.deleteLater)
            self.yamlWorker.finished.connect(self.yamlThread.quit)
            self.yamlWorker.finished.connect(self.yamlThread.wait)

            self.yamlThread.start()
        else:
            new_item = None
            fileName = os.path.basename(filePath)
            items = self.ui.fileList.findItems(fileName, QtCore.Qt.MatchExactly)
            if len(items) > 0:
                self.ui.statusbar.showMessage("File already opened", 3000)

            new_item = QtWidgets.QListWidgetItem()
            new_item.setText(fileName)
            new_item.setData(QtCore.Qt.UserRole, {'filePath':filePath})

            self.ui.fileList.addItem(new_item)


            if(new_item is not None):
                self.ui.original.setPixmap(QtGui.QPixmap(filePath))
                self.ui.fileList.setCurrentItem(new_item)
                self.ui.original_2.clear()
                self.ui.preview_2.clear()

    def postParseData(self):
        if self.yamlQueue.qsize() > 0:
            self.yamlProgress.hide()
            res = self.yamlQueue.get()
            filePaths, label = res
            self.labels, self.label_eval = label
            self.ui.fileList.clear()
            self.open_file(filePaths)
            self.yamlThread = QThread()
            self.yamlWorker = yamlWorker(self.yamlQueue)
        else:
            assert False
        return 0

    def reportProgress2(self, n):
        if(n == 3):
            self.ui.progressBar_2.setValue(self.ui.progressBar_2.value() + 1)

    def reportProgress(self, n):
        self.ui.progressBar.setValue(n)

    def change_file_selection(self, qListItem):
        if not qListItem is None:
            originalImg = cv2.imread(qListItem.data(QtCore.Qt.UserRole)['filePath'])

            self.ui.listWidget.clear()
            self.ui.original_2.clear()
            self.ui.preview_2.clear()

            originalQtImg = convert_cvimg_to_qimg(originalImg)
            self.ui.original.setPixmap(QtGui.QPixmap.fromImage(originalQtImg))

            self.changePreviewImage()
        else:
            print("INFO: qListItem was None (was it cleared by YAML read function?)")

    def change_seg_selection(self, current):
        if(current == None):
            return

        qListItem = self.ui.fileList.currentItem()
        originalImg = cv2.imread(qListItem.data(QtCore.Qt.UserRole)['filePath'])

        predictedImg = qListItem.data(QtCore.Qt.UserRole).get('predictedImg')
        predictedColor = qListItem.data(QtCore.Qt.UserRole).get('predictedColor')
        
        if(predictedImg is None):
            return

        predictedQtImg = convert_cvimg_to_qimg(predictedImg)

        if(predictedColor is not None):
            predictedQtColor = convert_cvimg_to_qimg(predictedColor)

        if(current.text() == "all"):
            self.ui.preview_2.setPixmap(QtGui.QPixmap.fromImage(predictedQtImg))

            if(predictedColor is not None):
                self.ui.original_2.setPixmap(QtGui.QPixmap.fromImage(predictedQtColor))

        else:
            pred = qListItem.data(QtCore.Qt.UserRole)['pred']
            model = models._registry[self.ui.comboBox.currentText()]
            imgs = model.draw_single_class(pred, originalImg, current.text())
            qImg_overlay = convert_cvimg_to_qimg(imgs["overlay"])
            self.ui.preview_2.setPixmap(QtGui.QPixmap.fromImage(qImg_overlay))

            if "segmentation" in imgs:
                qImg_segmentation= convert_cvimg_to_qimg(imgs["segmentation"])
                self.ui.original_2.setPixmap(QtGui.QPixmap.fromImage(qImg_segmentation))
        
    def display_result(self, result):
        qListItems = result[1]
        model_results = result[0]

        # Code to display the original image with detections
        self.ui.original_2.clear()
        originalImg = model_results[0]
        self.ui.original_2.setPixmap(QtGui.QPixmap.fromImage(convert_cvimg_to_qimg(originalImg['dst'])))

        for i, result in enumerate(model_results):
            qListItem = qListItems[0]
            temp = qListItem.data(QtCore.Qt.UserRole)

            temp['pred'] = result["pred"]
            temp['predictedImg'] = result["dst"]

            #if "segmentation" in result:
            #    temp['predictedColor'] = result["segmentation"]

            #    if(self.ui.fileList.currentItem() == qListItem):
            #        predictedQtColor = convert_cvimg_to_qimg(result["segmentation"])
            #        self.ui.original_2.setPixmap(QtGui.QPixmap.fromImage(predictedQtColor))
            #else:
            self.ui.preview_2.clear()

            predictedQtImg = convert_cvimg_to_qimg(result["dst"])
            self.ui.preview_2.setPixmap(QtGui.QPixmap.fromImage(predictedQtImg))
            qListItem.setData(QtCore.Qt.UserRole, temp)

    def display_items(self, results):
        qListItems = results[1]
        seg_results = results[0]

        for i, result in enumerate(seg_results):
            qListItem = qListItems[0]
            names = result["listOfNames"]
            if(self.ui.fileList.currentItem() == qListItem):
                for x in names:
                    i = QtWidgets.QListWidgetItem(x)
                    i.setBackground(QtGui.QColor(names[x][0], names[x][1], names[x][2]))
                    self.ui.listWidget.addItem(i)

            temp = qListItem.data(QtCore.Qt.UserRole)
            temp['items'] = names
            qListItem.setData(QtCore.Qt.UserRole, temp)
 
    def run_model(self):
        qListItem = self.ui.fileList.currentItem()
        img = cv2.imread(qListItem.data(QtCore.Qt.UserRole).get('filePath'))

        if img is None:
            self.ui.statusbar.showMessage("Import an image first!", 3000)
            return

        noiseImg = self.apply_augmentations(img)

        self.ui.pushButton_2.setEnabled(False)
        self.ui.progressBar.show()
        self.ui.listWidget.clear()
        self.ui.original_2.clear()
        self.ui.preview_2.clear()

        self.thread = QtCore.QThread()
        self.worker = Worker()

        #detectedNames = {"all": [255,255,255]}
        display_sep = self.ui.checkBox_2.isChecked()
        comboModelType = self.ui.comboBox.currentText()

        self.worker.setup([img,noiseImg], display_sep, comboModelType, [qListItem])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.finished.connect(self.ui.progressBar.hide)
        self.worker.finished.connect(self.display_result)
        #if(comboModelType == "Semantic Segmentation"):
        self.worker.finished.connect(self.display_items)
        self.worker.finished.connect(lambda: self.ui.pushButton_2.setEnabled(True))
        self.worker.progress.connect(self.reportProgress)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def startExperiment(self):
        # fill image paths with dummy inputs for now
        comboModelType = self.ui.comboBox.currentText()

        # check augmentation setup:
        if self.ui.compoundAug.isChecked():
            ret, msg = mainAug.checkArgs()
            if not ret:
                print(msg) # create dialog box saying something is wrong 
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(msg)
                msg_box.setWindowTitle("Compound Error")
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec_()
                return -1

        # initialize model (temp; move to thread worker):
        _model = models._registry[comboModelType]
        _model.initialize()
        
        # replace preset list with variable list:
        # assemble active image path list:
        lw = self.ui.fileList
        items = [lw.item(x) for x in range(lw.count())]
        imgPaths = []
        if self.label_eval == 'coco':
            # ask coco api:
            imgPaths = self.labels['coco'].getImgIds()
        else:
            for qListItem in items:
                file_path = qListItem.data(QtCore.Qt.UserRole).get('filePath')
                if(file_path is None):
                    self.ui.statusbar.showMessage("Import an image first!", 3000)
                    return -1
                imgPaths.append(file_path)

        config = ExperimentConfig(mainAug, self.ui.compoundAug.isChecked(), imgPaths, _model, comboModelType, labels=self.labels, labelType=self.label_eval)
        self.experiment = ExperimentDialog(config)
        self.experiment.startExperiment()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])

    window = mainWindow()
    window.show()
    window.showMaximized()

    app.exec_()