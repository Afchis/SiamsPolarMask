# -*- coding: utf-8 -*-
"""Untitled6.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/176rmbUbafjmSZgDX6SZ_dgLkR0cfD2Fl
"""

def transform_one_point_cords(self, original, bbox, cords_of_one_point):
  bbox_xywh =  np.array([bbox[0] + bbox[2] // 2, bbox[1] + bbox[3] // 2, bbox[2], bbox[3]],np.float32)  # 将标注ann中的bbox从左上点的坐标+bbox长宽 -> 中心点的坐标+bbox的长宽

  original_image_w, original_image_h = original.size
  cx, cy, tw, th = bbox_xywh

  p = round((tw + th) / 2, 2)
  template_square_size = int(np.sqrt((tw + p) * (th + p)))  # a
  detection_square_size = int(template_square_size * 2)  # A = 2a

  detection_lt_x, detection_lt_y = cx - detection_square_size // 2, cy - detection_square_size // 2
  detection_rb_x, detection_rb_y = cx + detection_square_size // 2, cy + detection_square_size // 2

  x, y = cords_of_one_point[0], cords_of_one_point[1]

  x_in_detection_before_resize, y_in_detection_before_resize = x - detection_lt_x, y - detection_lt_y
  x_in_detection_after_resize,  y_in_detection_before_resize = (x_in_detection_before_resize/detection_square_size*255), (y_in_detection_before_resize/detection_square_size*255)

  return (x_in_detection_after_resize,  y_in_detection_before_resize)