import cv2
from PIL import Image
import os
import numpy as np

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

def convert_pixels_to_millimeters(pixel_count, dpi=300):
    pass


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