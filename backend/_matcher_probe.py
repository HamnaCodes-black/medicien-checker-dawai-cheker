import cv2, numpy as np
from PIL import Image
a=np.array(Image.open('demo_data/reference/fevra-plus/front.png').convert('L'))
orb=cv2.ORB_create(nfeatures=1800)
kp1,d1=orb.detectAndCompute(a,None)
kp2,d2=orb.detectAndCompute(a,None)
print(cv2.__version__, type(kp1[0]), type(d1))
m=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d2,d1,k=2)
print(type(m), type(m[0]), len(m[0]), type(m[0][0]), m[0][0])
print(dir(m[0][0])[:20])
