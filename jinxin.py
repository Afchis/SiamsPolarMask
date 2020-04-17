# -*- coding: utf-8 -*-
"""jinxin.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1pqSN8z4iok1oeLH1Kkov4JL5Ha8HspgV
"""

import torch
import torch.utils.data as data
from pycocotools.coco import COCO
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageStat


class COCODataset(data.Dataset):
    def __init__(self, annFilePath, imgDir, catId=1, transform=None):
        super(COCODataset, self).__init__()
        self.annFilePath = annFilePath
        self.imgDir = imgDir
        self.catId = catId
        self.transform = transform
        # annFile = '../../504Proj/annotations/instances_val2017.json'
        self.coco = COCO(annFilePath)
        self.imgIds = self.coco.getImgIds(catIds=self.catId)

    def __getitem__(self, index):
        meta = {}

        img_info = self.coco.loadImgs(self.imgIds[index])[0]
        img = cv2.imread(self.imgDir + img_info['file_name'])

        annIds = self.coco.getAnnIds(imgIds=img_info['id'], catIds=self.catId, iscrowd=False)
        anns = self.coco.loadAnns(annIds)
        max_area_ann = max(anns, key=lambda x: x['area'])    # ann ID

        bbox = max_area_ann['bbox']
        mask = self.coco.annToMask(max_area_ann)

        c_x = np.mean(mask.nonzero()[0])            # numpy 下的x, y坐标 与opencv相反
        c_y = np.mean(mask.nonzero()[1])
        center = np.array([c_x, c_y]) #torch.Tensor([c_x, c_y])
        ##################################################
        # TODO
        # 添加中心点周围8个点坐标及其对应边界点
        # 考虑中心点在边界的情况
        # 输入与输出的坐标变换公式为 p_in = 8p_out + 31
        # 具体分为两个阶段 第一阶段 p_in = 8p_backbone + 7 第二阶段 p_backbone = p_out + 3
        ##################################################

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        contours = np.concatenate(contours)          # size: n * 1 * 2
        contours = contours.reshape(-1, 2)           # 此处为opencv的x, y坐标，后处理需要交换

        distance, new_coord = self.get_36_coordinates(c_x, c_y, contours)  # distance is a list, new_coord is a dictionary which keys are angles(0 ~ 360, 10)

        ####################################################
        # TODO
        # Transform image

        # meta['image'] = self.transform(img)
        meta['template'], meta['detection'], meta['bbox'], meta['center'], meta['distance'] = self.transform(image, bbox, center, distance)
        ####################################################

        meta['id'] = max_area_ann['id']
        meta['imgId'] = max_area_ann['image_id']
        #meta['bbox'] = bbox
        #meta['center'] = center
        #meta['distance'] = distance
        meta['coords'] = new_coord
        # meta['mask'] = torch.Tensor(mask).resize((255, 255))

        return meta


    def __len__(self):
        return len(self.imgIds)

    def get_36_coordinates(self, c_x, c_y, pos_mask_contour):
        # 输入为opencv坐标系下的contuor， 在计算时转化为Numpy下的坐标
        ct = pos_mask_contour
        x = torch.Tensor(ct[:, 1] - c_x)      # opencv x, y交换
        y = torch.Tensor(ct[:, 0] - c_y)

        angle = torch.atan2(x, y) * 180 / np.pi
        angle[angle < 0] += 360
        angle = angle.int()
        # dist = np.sqrt(x ** 2 + y ** 2)
        dist = torch.sqrt(x ** 2 + y ** 2)
        angle, idx = torch.sort(angle)
        dist = dist[idx]
        ct2 = ct[idx]

        # 生成36个角度
        new_coordinate = {}
        for i in range(0, 360, 10):
            if i in angle:
                d = dist[angle == i].max()
                new_coordinate[i] = d
            elif i + 1 in angle:
                d = dist[angle == i + 1].max()
                new_coordinate[i] = d
            elif i - 1 in angle:
                d = dist[angle == i - 1].max()
                new_coordinate[i] = d
            elif i + 2 in angle:
                d = dist[angle == i + 2].max()
                new_coordinate[i] = d
            elif i - 2 in angle:
                d = dist[angle == i - 2].max()
                new_coordinate[i] = d
            elif i + 3 in angle:
                d = dist[angle == i + 3].max()
                new_coordinate[i] = d
            elif i - 3 in angle:
                d = dist[angle == i - 3].max()
                new_coordinate[i] = d

        distances = torch.zeros(36)

        for a in range(0, 360, 10):
            if not a in new_coordinate.keys():
                new_coordinate[a] = torch.tensor(1e-6)
                distances[a // 10] = 1e-6
            else:
                distances[a // 10] = new_coordinate[a]
        # for idx in range(36):
        #     dist = new_coordinate[idx * 10]
        #     distances[idx] = dist

        return distances, new_coordinate

    def transform(self, image, bbox, center, distance):
      mean_template_and_detection = tuple(map(round, ImageStat.Stat(image).mean))
      bbox_xywh = np.array([bbox[0]+bbox[2]//2, bbox[1]+bbox[3]//2, bbox[2], bbox[3]], np.float32) # 将标注ann中的bbox从左上点的坐标+bbox长宽 -> 中心点的坐标+bbox的长宽
      bbox_x1y1x2y2 = np.array([bbox[0], bbox[1], bbox[0]+bbox[2], bbox[1]+bbox[3]], np.float32)  # 将标注ann中的bbox从左上点的坐标+bbox长宽 -> 左上点的坐标+右下点的坐标

      original_image_w, original_image_h = image.size
      cx, cy, tw, th = bbox_xywh
      p = round((tw + th)/2, 2)
      template_square_size = int(np.sqrt((tw+p)*(th+p))) # a
      detection_square_size = int(template_square_size * 2) # A = 2a

      # pad
      detection_lt_x, detection_lt_y = cx - detection_square_size//2, cy - detection_square_size//2
      detection_rb_x, detection_rb_y = cx + detection_square_size//2, cy + detection_square_size//2
      left = -detection_lt_x if detection_lt_x < 0 else 0
      top = -detection_lt_y if detection_lt_y < 0 else 0
      right = detection_rb_x - original_image_w if detection_rb_x > original_image_w else 0
      bottom = detection_rb_y - original_image_h if detection_rb_y > original_image_h else 0 
      padding = tuple(map(int, [left, top, right, bottom]))
      padding_image_w, padding_image_h = left + right + original_image_w, top + bottom + original_image_h

      template_img_padding = ImageOps.expand(image, border=padding, fill=mean_template_and_detection)
      detection_img_padding = ImageOps.expand(image, border=padding, fill=mean_template_and_detection)

      # crop
      tl = cx + left - template_square_size//2
      tt = cy + top - template_square_size//2
      tr = padding_image_w - tl - template_square_size
      tb = padding_image_h - tt - template_square_size
      template_img_crop = ImageOps.crop(template_img_padding.copy(), (tl, tt, tr, tb))

      dl = np.clip(cx + left - detection_square_size//2, 0, padding_image_w - detection_square_size)
      dt = np.clip(cy + top - detection_square_size//2, 0, padding_image_h - detection_square_size)
      dr = np.clip(padding_image_w - dl- detection_square_size, 0, padding_image_w - detection_square_size)
      db = np.clip(padding_image_h - dt - detection_square_size, 0, padding_image_h - detection_square_size)
      detection_img_crop = ImageOps.crop(detection_img_padding.copy(), (dl, dt, dr, db))

      detection_tlcords_of_original_image = (cx - detection_square_size//2, cy - detection_square_size//2)
      detection_rbcords_of_original_image = (cx + detection_square_size//2, cy + detection_square_size//2)
      
      detection_tlcords_of_padding_image = (cx - detection_square_size//2 + left, cy - detection_square_size//2 + top)
      detection_rbcords_of_padding_image = (cx + detection_square_size//2 + left, cy + detection_square_size//2 + top)

      # resize
      template_img_resized = template_img_crop.copy().resize((127, 127))
      detection_img_resized = detection_img_crop.copy().resize((256, 256))
      
      template_resized_ratio = round(127/template_square_size, 2)
      detection_resized_ratio = round(256/detection_square_size, 2)

      center_x, center_y = center # coordinates of center in original image
      center_x_of_padding_img, center_y_of_padding_img = center_x + left, center_y + top
      x11, y11 = detection_tlcords_of_padding_image
      x12, y12 = detection_rbcords_of_padding_image

      x1_of_d, y1_of_d = int(center_x_of_padding_img - x11), int(center_y_of_padding_img - y11)
      x1 = np.clip(x1_of_d, 0, x12 - x11).astype(np.float32)
      y1 = np.clip(y1_of_d, 0, y12 - y11).astype(np.float32)

      cords_of_center_in_cropped_detection = np.array((x1, y1), dtype=np.float32)
      cords_of_center_in_resized_detection = (cords_of_center_in_cropped_detection * detection_resized_ratio)

      blcords_of_bbox_in_padding_image, btcords_of_bbox_in_padding_image, brcords_of_bbox_in_padding_image, bbcords_of_bbox_in_padding_image = bbox_x1y1x2y2[0] + left, bbox_x1y1x2y2[1]+top, bbox_x1y1x2y2[2]+left, bbox_x1y1x2y2[3]+top
      blcords_of_bbox_in_detection, btcords_of_bbox_in_detection, brcords_of_bbox_in_detection, bbcords_of_bbox_in_detection = blcords_of_bbox_in_padding_image-x11, btcords_of_bbox_in_padding_image-y11, brcords_of_bbox_in_padding_image-x11, bbcords_of_bbox_in_padding_image-y11
      x1 = np.clip(blcords_of_bbox_in_detection, 0, x12 - x11).astype(np.float32)
      y1 = np.clip(btcords_of_bbox_in_detection, 0, y12 - y11).astype(np.float32)
      x2 = np.clip(brcords_of_bbox_in_detection, 0, x12 - x11).astype(np.float32)
      y2 = np.clip(bbcords_of_bbox_in_detection, 0, y12 - y11).astype(np.float32)
      cords_of_bbox_in_cropped_detection = np.array([x1, y1, x2, y2], dtype=np.float32)
      cords_of_bbox_in_resized_detection = cords_of_bbox_in_cropped_detection * detection_resized_ratio

      distances = distances * detection_resized_ratio

      return template_img_resized, detection_img_padding, cords_of_bbox_in_resized_detection, cords_of_center_in_resized_detection, distances





annFile = './Data/instances_val2017.json'
imgDir = './Data/val2017/'
train_data = COCODataset(annFilePath=annFile, imgDir=imgDir)
train_loader = data.DataLoader(dataset=train_data, batch_size=5, shuffle=False)

for i, Data in enumerate(train_loader):
    if i > 0:
        break
    print(Data['id'])