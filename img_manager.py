import cv2
from PIL import Image
import os
import numpy as np
import math
import yaml

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
    
    # 2. Downsampling
    downsampled = calculate_and_downsample(i, target_size)
    
    # 3. Binarization
    binarized_array = apply_thresholding(downsampled, threshold)
    
    # 4. Save to disk
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
    # Parameters of the drawing area (sheet) (in millimeters)
    sheet_width= config["sheet_config"]["sheet_width"]
    sheet_height= config["sheet_config"]["sheet_height"]
    offset_y = config["sheet_config"]["offset_y"]    # How distant are the motors from the sheet

    scale = min(sheet_width / img_width, sheet_height / img_height)

    offset_x = -(img_width * scale)/2

    sheet_path = []
    for p in path:
        x = (p["x"] * scale) + offset_x
        y = (p["y"] * scale) + offset_y

        sheet_path.append({"x": x, "y": y, "state": p["state"]})

    return sheet_path


def compute_kinematics(x ,y):
    """
    Compute the angles for the servos based on the desired x and y coordinates of the pen.
    """

    d = config["giotto_config"]["servo_distance"]  # Distance between the two servos (mm)
    L1 = config["giotto_config"]["L1"]  # Length of the first arm connected to the servo (mm)
    L2 = config["giotto_config"]["L2"]  # Length of the second arm connected to the pen (mm)

    x_L = -d/2
    x_R = d/2

    # Distance from servo to the target
    D_L = math.hypot(x - x_L, y)
    D_R = math.hypot(x - x_R, y)

    # Check if the target is reachable
    if D_L > (L1 + L2) or D_R > (L1 + L2) or D_L < abs(L1 - L2) or D_R < abs(L1 - L2):
        print(f"Target ({x}, {y}) is out of reach.")
        return None, None
    
    # Compute angle of vector
    beta_L = math.atan2(y, x - x_L)
    beta_R = math.atan2(y, x - x_R)

    # Cosin theorem to find out the bend angles
    cos_a_L = (L1**2 + D_L**2 - L2**2) / (2 * L1 * D_L)
    cos_a_R = (L1**2 + D_R**2 - L2**2) / (2 * L1 * D_R)

    # Avoid approximation errors
    cos_a_L = max(-1, min(1, cos_a_L))
    cos_a_R = max(-1, min(1, cos_a_R))

    alpha_L = math.acos(cos_a_L)
    alpha_R = math.acos(cos_a_R)

    # Compute angles
    theta_L = beta_L + alpha_L
    theta_R = beta_R + alpha_R

    # Convert radiants in degrees
    angle_L = math.degrees(theta_L)
    angle_R = math.degrees(theta_R)

    return int(angle_R), int(angle_L)



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
    save_opencv_image(contours_only, filename)
    '''