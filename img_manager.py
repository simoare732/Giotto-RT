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
    scale_factor = min(target_size[0] / image_array.shape[1], target_size[1] / image_array.shape[0])
    new_width = int(image_array.shape[1] * scale_factor)
    new_height = int(image_array.shape[0] * scale_factor)
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

    h, w = image_array.shape

    filtered_contours = []

    for contour in contours:
        x,y,cw,ch = cv2.boundingRect(contour)

        if cw < w-2 and ch < h-2:  # Filter out contours that are too large
            filtered_contours.append(contour)

    return filtered_contours


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



def convert_pixels_to_millimeters(path):
    """
    Converts pixel coordinates from an image into physical millimeters for the robot's workspace.
    It calculates a bounding box around the actual drawing, determines the optimal scaling factor 
    to fit the safe drawing area, and applies offsets to center the image on the physical paper.
    """
    if not path:
        return []
        
    # Dynamically read the safe drawing area parameters
    MIN_X = config["sheet_config"]["MIN_X"]
    MAX_X = config["sheet_config"]["MAX_X"]
    MIN_Y = config["sheet_config"]["MIN_Y"]
    MAX_Y = config["sheet_config"]["MAX_Y"]
    
    safe_width = MAX_X - MIN_X
    safe_height = MAX_Y - MIN_Y
    
    # 1. Calculate the Bounding Box limited only to the pixels containing the contours
    min_px_x = min(p["x"] for p in path)
    max_px_x = max(p["x"] for p in path)
    min_px_y = min(p["y"] for p in path)
    max_px_y = max(p["y"] for p in path)
    
    path_w = max_px_x - min_px_x
    path_h = max_px_y - min_px_y
    
    if path_w == 0 or path_h == 0:
        return []
    
    # 2. Calculate the scale excluding the white margins of the original image
    scale = min(safe_width / path_w, safe_height / path_h)
    
    final_w = path_w * scale
    final_h = path_h * scale
    
    # 3. Apply offset to center the lines in the physical area
    offset_x = -(final_w / 2)
    offset_y = MIN_Y + (safe_height - final_h) / 2
    
    sheet_path = []
    for p in path:
        # Subtract the minimum point to ignore the preceding empty space in the image
        norm_x = p["x"] - min_px_x
        norm_y = p["y"] - min_px_y
        
        x = (norm_x * scale) + offset_x
        y = offset_y + final_h - (norm_y * scale)
        
        sheet_path.append({"x": x, "y": y, "state": p["state"]})
        
    return sheet_path


def densify_path(path_mm, max_step=0.5):
    """
    Densifies a given path by adding intermediate points between existing points 
    if the distance between them exceeds the specified max_step.
    This segmentation ensures smoother movements during the drawing process.
    """
    if not path_mm:
        return []

    # Start the new list with the first point
    densified_path = [path_mm[0]]
    
    # Iterate over all subsequent points
    for i in range(1, len(path_mm)):
        p1 = densified_path[-1]
        p2 = path_mm[i]
        
        dx = p2["x"] - p1["x"]
        dy = p2["y"] - p1["y"]
        distance = math.hypot(dx, dy)
        
        # If the distance exceeds the limit, fragment the segment
        if distance > max_step:
            # Calculate the number of necessary subdivisions (rounded up)
            steps = math.ceil(distance / max_step)
            
            for step in range(1, steps + 1):
                t = step / steps
                inter_x = p1["x"] + (t * dx)
                inter_y = p1["y"] + (t * dy)
                
                # Add the intermediate point.
                # The pen state (Up/Down) remains the same as the target p2.
                densified_path.append({"x": inter_x, "y": inter_y, "state": p2["state"]})
        else:
            # If the segment is already short enough, add it as is
            densified_path.append(p2)
            
    return densified_path


def compute_kinematics(x, y):
    """
    Computes the inverse kinematics for a five-bar linkage SCARA robot.
    It applies Cosin Theorem (or Carnot Theorem).
    It calculates the required angles for the left and right servo motors 
    to reach the desired (x, y) coordinates, applying software trims to correct mechanical skew.
    """ 
    L1 = config["giotto_config"]["servo_distance"]  # Distance between the two servos (mm)
    L2 = config["giotto_config"]["L1"]              # Length of the first arm connected to the servo (mm)
    L3 = config["giotto_config"]["L2"]              # Length of the second arm connected to the pen (mm)

    x1 = x + L1 / 2
    x2 = x - L1 / 2

    D1 = math.hypot(x1, y)
    D2 = math.hypot(x2, y)

    # Check if the target is within the physical reach of the arms
    if D1 > (L2 + L3) or D2 > (L2 + L3) or D1 < abs(L2 - L3) or D2 < abs(L2 - L3):
        return None, None

    # Apply the Law of Cosines
    c1 = (L2**2 + D1**2 - L3**2) / (2 * L2 * D1)
    c2 = (L2**2 + D2**2 - L3**2) / (2 * L2 * D2)

    # Clamp the values to prevent math domain errors due to floating point inaccuracies
    c1 = max(-1.0, min(1.0, c1))
    c2 = max(-1.0, min(1.0, c2))

    gamma1 = math.atan2(x1, y)
    gamma2 = math.atan2(x2, y)

    theta1 = math.acos(c1)
    theta2 = math.acos(c2)

    # Calculate final angles in degrees
    angle_Sx = math.degrees(theta1 - gamma1)
    angle_Rx = 180 - math.degrees(gamma2 + theta2)

    # Software trim configuration to correct mechanical skew
    skew_sx = config["giotto_config"]["skew_sx"]
    skew_dx = config["giotto_config"]["skew_dx"]

    tempAngle_Sx = angle_Sx + skew_sx
    tempAngle_Rx = angle_Rx + skew_dx

    if tempAngle_Sx < 0:
        angle_Sx = 0
    elif tempAngle_Sx > 180:
        angle_Sx = 180
    else:
        angle_Sx = tempAngle_Sx

    if tempAngle_Rx < 0:
        angle_Rx = 0
    elif tempAngle_Rx > 180:
        angle_Rx = 180
    else:
        angle_Rx = tempAngle_Rx

    return angle_Rx, angle_Sx



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