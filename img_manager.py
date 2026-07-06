import cv2
from PIL import Image
import os
import numpy as np
import math
import yaml
import cv2

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

def load_grayscale_image(image_path):
    """
    Acquires the grayscale image from a specific path.
    """
    i = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if i is None:
        raise FileNotFoundError(f"Can't read image from path: {image_path}")
    return i


def is_black_and_white(image):
    """
    Checks if the image is black and white by verifying that all pixel values are either 0 or 255.
    """
    val = np.unique(image)
    is_bw = np.all(np.isin(val, [0, 255]))

    return is_bw


def calculate_and_downsample(image_array, target_size):
    """
    Calculates the scale factor and resizes the image.
    """
    # Calculation logic kept exactly as the original
    scale_factor = min(target_size[0] / image_array.shape[0], target_size[1] / image_array.shape[1])
    new_width = int(image_array.shape[0] * scale_factor)
    new_height = int(image_array.shape[1] * scale_factor)
    dim = (new_width, new_height)
    
    return cv2.resize(image_array, dim, interpolation=cv2.INTER_AREA)

def apply_thresholding(image_array, threshold):
    """
    Applies a fixed threshold to binarize the image.
    """
    return cv2.threshold(image_array, int(threshold * 255), 255, cv2.THRESH_BINARY)[1]

def save_opencv_image(image_array, output_filename):
    """
    Saves an OpenCV array to disk.
    """
    # Folder path imgs_modified
    folder_path = os.path.join(os.getcwd(), "imgs_modified") 
    path = os.path.join(folder_path, output_filename)
    cv2.imwrite(path, image_array)

def convert_array_to_pil(image_array):
    """
    Converts an OpenCV array to a PIL.Image object.
    """
    return Image.fromarray(image_array)

def process_image(image_path, target_size, threshold):
    """
    Wrapper: orchestrates the functions to read an image, resize it, 
    binarize it and save it, returning the final PIL object.
    """
    # 1. Image reading
    i = load_grayscale_image(image_path)

    # 2. Check if the image is black and white
    if is_black_and_white(i):
        binarized_array = cv2.resize(i, target_size, interpolation=cv2.INTER_NEAREST)
    else:
        # 3. Downsampling
        downsampled = calculate_and_downsample(i, target_size)
        
        # 4. Binarization
        binarized_array = apply_thresholding(downsampled, threshold)
    
    # 5. Save to disk
    #filename = os.path.basename(image_path)
    #save_opencv_image(binarized_array, filename)
    
    return binarized_array

def countours_extraction(image_array):
    """
    Extracts contours from a binary image (numpy array).
    """
    
    # It extracts contours from a binary image using OpenCV's findContours function.
    contours, _ = cv2.findContours(image_array, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    return contours


def create_contours_only_image(image_array, contours, pixelized = False):
    """
    Creates an image containing only the contours on a black background.
    """
    contour_image = np.zeros_like(image_array)
    cv2.drawContours(contour_image, contours, -1, 255, 1)

    contour_image = cv2.bitwise_not(contour_image)

    if pixelized:   # If pixelized is True, the resulting image will be enlarged and a grid will be drawn over it.
        enlarged = cv2.resize(
            contour_image,
            (contour_image.shape[1] * 10, contour_image.shape[0] * 10),
            interpolation=cv2.INTER_NEAREST
        )

        h, w = enlarged.shape
        grid_color = 180  # light gray

        # Vertical grid lines
        for x in range(0, w, 10):
            cv2.line(enlarged, (x, 0), (x, h - 1), grid_color, 1)

        # Horizontal grid lines
        for y in range(0, h, 10):
            cv2.line(enlarged, (0, y), (w - 1, y), grid_color, 1)

        return enlarged

    return contour_image


def draw_contours(contours):
    """
    Transform coordinates of contours in a path.
    """
    path = []

    for contour in contours:
        if len(contour) < 2:
            continue  # Skip contours with less than 2 points
        
        # Go on the first point of contour
        first_point = contour[0][0]
        x, y = first_point[0], first_point[1]
        path.append({"x": x, "y": y, "state":False})

        path.append({"x": x, "y": y, "state":True})

        # Start tracking the contour
        for i in range(1, len(contour)):
            point = contour[i][0]
            x, y = point[0], point[1]
            path.append({"x": x, "y": y, "state":True})

        
        # Once the contour is finished, lift the pen
        last_point = contour[-1][0]
        x, y = last_point[0], last_point[1]
        path.append({"x": x, "y": y, "state":False})

    return path



def convert_pixels_to_millimeters(path, img_width, img_height):
    """
    Converts the pixel coordinates in the path to millimeter coordinates based on the drawing area (sheet) dimensions.
    """
    # Parameters of the drawing area
    MAX_X = config["sheet_config"]["MAX_X"]
    MIN_X = config["sheet_config"]["MIN_X"]
    MAX_Y = config["sheet_config"]["MAX_Y"]
    MIN_Y = config["sheet_config"]["MIN_Y"]
    

    sheet_path = []
    for p in path:
        x = -((p["x"] / img_width) * (MAX_X - MIN_X) + MIN_X)
        y = (p["y"] / img_height) * (MAX_Y - MIN_Y) + MIN_Y

        if not (MIN_X <= x <= MAX_X and MIN_Y <= y <= MAX_Y):
            continue

        sheet_path.append({"x": x, "y": y, "state": p["state"]})

    return sheet_path


def compute_kinematics(x ,y):
    """
    Compute the angles for the servos based on the desired x and y coordinates of the pen.
    """

    L1 = config["giotto_config"]["servo_distance"]  # Distance between the two servos (mm)
    L2 = config["giotto_config"]["L1"]  # Length of the first arm connected to the servo (mm)
    L3 = config["giotto_config"]["L2"]  # Length of the second arm connected to the pen (mm)

    # 4. Offset per la posizione dei due motori sulla base
    x1 = x + L1 / 2
    x2 = x - L1 / 2

    # 5. Distanza in linea retta dal punto target ai motori
    D1 = math.sqrt(x1**2 + y**2)
    D2 = math.sqrt(x2**2 + y**2)

    # 6. Controllo di estensione massima/minima delle braccia
    if D1 > (L2 + L3) or D2 > (L2 + L3) or D1 < abs(L2 - L3) or D2 < abs(L2 - L3):
        return None, None # Il target supera l'estensione meccanica delle braccia

    # 7. Calcolo cinematica inversa per motore sinistro
    gamma1 = math.atan2(x1, y)
    theta1 = math.acos((L2**2 + D1**2 - L3**2) / (2 * L2 * D1))
    angolo_sinistro = math.degrees(theta1 - gamma1)

    # 8. Calcolo cinematica inversa per motore destro
    gamma2 = math.atan2(x2, y)
    theta2 = math.acos((L2**2 + D2**2 - L3**2) / (2 * L2 * D2))
    angolo_destro = 180 - math.degrees(gamma2 + theta2)


    return int(angolo_destro), int(angolo_sinistro)
    #return int(angle_R), int(angle_L)



'''
if __name__ == "__main__":
    image_path = "imgs_source/cat.png"

    # 1. Modify the image
    binarized = process_image(image_path, (100, 100), 0.5)

    # 2. Extract contours
    contours = countours_extraction(binarized)

    print(f"Number of contours found: {len(contours)}")
    print(contours[0].shape)
    print(contours[1].shape)

    # 3. Create image with only contours
    contours_only = create_contours_only_image(binarized, contours)


    # 4. Save and show result
    filename = os.path.basename(image_path)
    save_opencv_image(contours_only, filename)'''