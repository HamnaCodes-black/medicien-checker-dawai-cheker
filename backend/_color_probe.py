import cv2, numpy as np
from PIL import Image

def dist(a,b):
    ra=np.array(Image.open(a).convert('RGB')); rb=np.array(Image.open(b).convert('RGB'))
    ha=cv2.cvtColor(ra,cv2.COLOR_RGB2HSV); hb=cv2.cvtColor(rb,cv2.COLOR_RGB2HSV)
    ma=((ha[:,:,1]>90)&(ha[:,:,2]>40)).astype(np.uint8)*255
    mb=((hb[:,:,1]>90)&(hb[:,:,2]>40)).astype(np.uint8)*255
    hista=cv2.calcHist([ha],[0,1],ma,[30,32],[0,180,0,256]); histb=cv2.calcHist([hb],[0,1],mb,[30,32],[0,180,0,256])
    cv2.normalize(hista,hista,0,1,cv2.NORM_MINMAX); cv2.normalize(histb,histb,0,1,cv2.NORM_MINMAX)
    c=cv2.compareHist(hista,histb,cv2.HISTCMP_CORREL)
    return 1-max(0,min(1,c)), ma.mean()/255, mb.mean()/255
pairs=[
("demo_data/reference/fevra-plus/front.png","demo_data/reference/fevra-plus/front.png"),
("demo_data/reference/fevra-plus/front.png","demo_data/tampered/fevra-plus__wrong-color/front.png"),
("demo_data/reference/allerfree/front.png","demo_data/tampered/allerfree__wrong-color/front.png"),
("demo_data/reference/coughcalm/front.png","demo_data/tampered/coughcalm__blurry-text/front.png"),
("demo_data/reference/fevra-plus/front.png","demo_data/tampered/fevra-plus__typo-name/front.png"),
]
for a,b in pairs: print(b, dist(a,b))
