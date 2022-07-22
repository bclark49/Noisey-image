from cv2 import cvtColor, COLOR_BGR2RGB, rectangle, LINE_AA, getTextSize, putText
from PyQt6 import QtGui
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

def convertCV2QT(cv_img, display_width, display_height):
    """Convert from an opencv image to QPixmap"""
    rgb_image = cvtColor(cv_img, COLOR_BGR2RGB)
    h, w, ch = rgb_image.shape
    bytes_per_line = ch * w
    convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
    p = convert_to_Qt_format.scaled(display_width, display_height, Qt.KeepAspectRatio)
    return QPixmap.fromImage(p)

# Converts opencv image to RGB first then to qt image
def convert_cvimg_to_qimg(cv_img):
    cv_img = cvtColor(cv_img, COLOR_BGR2RGB)

    height, width, channel = cv_img.shape
    bytesPerLine = 3 * width

    qt_img = QtGui.QImage(cv_img.data, width, height, bytesPerLine, QtGui.QImage.Format.Format_RGB888)
    return qt_img

def box_label(self, box, label='', color=(128, 128, 128), txt_color=(255, 255, 255)):
    # Add one xyxy box to image with label
    p1, p2 = (int(box[0]), int(box[1])), (int(box[2]), int(box[3]))
    rectangle(self.im, p1, p2, color, thickness=self.lw, lineType=LINE_AA)
    if label:
        tf = max(self.lw - 1, 1)  # font thickness
        w, h = getTextSize(label, 0, fontScale=self.lw / 3, thickness=tf)[0]  # text width, height
        outside = p1[1] - h - 3 >= 0  # label fits outside box
        p2 = p1[0] + w, p1[1] - h - 3 if outside else p1[1] + h + 3
        rectangle(self.im, p1, p2, color, -1, LINE_AA)  # filled
        putText(self.im, label, (p1[0], p1[1] - 2 if outside else p1[1] + h + 2), 0, self.lw / 3, txt_color,
                    thickness=tf, lineType=LINE_AA)