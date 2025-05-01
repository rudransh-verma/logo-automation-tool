from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageChops
import os
import io
import zipfile
import csv
import numpy as np
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, send_file, render_template  # <-- render_template import kar


app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
@app.route('/')
def index():
    return render_template('index.html')  # ye tera HTML serve karega

def trim_white_background(image):
    """Remove white background from image"""
    # Convert to RGBA if not already
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # Get image data as numpy array
    image_data = np.array(image)

    # Create a mask where white pixels (or nearly white) are False
    # and other pixels are True
    r, g, b, a = image_data.T
    white_areas = (r > 240) & (g > 240) & (b > 240)

    # Get bounding box of non-white pixels
    non_white_pixels = np.where(~white_areas.T)

    # If the image is entirely white, return the original
    if len(non_white_pixels[0]) == 0:
        return image

    # Get the bounding box
    bbox = (
        min(non_white_pixels[1]),
        min(non_white_pixels[0]),
        max(non_white_pixels[1]),
        max(non_white_pixels[0])
    )

    # Crop the image to the bounding box
    return image.crop(bbox)

def determine_aspect_ratio(image):
    """Determine if image is horizontal, vertical, or square-ish"""
    width, height = image.size
    ratio = width / height

    # Define thresholds for aspect ratio classification
    if ratio >= 1.4:  # 16:10 or wider
        return "horizontal"
    elif ratio <= 0.7:  # 10:16 or taller
        return "vertical"
    else:  # Between 0.7 and 1.4 (roughly square)
        return "square"

def position_on_canvas(image, aspect_ratio, canvas_size=(1000, 1000)):
    """Position the image on a fixed-size canvas based on aspect ratio rules"""
    # Create a new blank canvas with white background
    canvas = Image.new('RGBA', canvas_size, (255, 255, 255, 255))

    # Calculate position based on aspect ratio
    if aspect_ratio == "horizontal":
        # Padding left and right 100px, padding bottom 150px
        # This means we position the image 100px from left, and calculate top position
        # so that bottom padding is 150px
        left_position = 100
        bottom_padding = 150
        top_position = canvas_size[1] - image.height - bottom_padding

    elif aspect_ratio == "vertical":
        # Padding left 100px, padding top and bottom 100px
        left_position = 100
        top_position = 100  # 100px from top

    else:  # square
        # Padding left, bottom and top 100px, right 300px
        left_position = 100
        top_position = 100

    # Paste the image onto the canvas at the calculated position
    canvas.paste(image, (left_position, top_position), image if image.mode == 'RGBA' else None)

    return canvas

@app.route('/process-images', methods=['POST'])
def process_images():
    if 'logo' not in request.files or 'csv' not in request.files:
        return jsonify({'error': 'Missing files'}), 400

    logo_file = request.files['logo']
    csv_file = request.files['csv']

    # Get parameters
    logo_size = int(request.form.get('logoSize', 20))
    logo_position = request.form.get('logoPosition', 'bottom-right')
    logo_margin = int(request.form.get('logoMargin', 10))
    canvas_size = (1000, 1000)  # Fixed canvas size

    # Save logo temporarily
    logo_path = os.path.join(UPLOAD_FOLDER, secure_filename(logo_file.filename))
    logo_file.save(logo_path)
    logo = Image.open(logo_path)

    # Process CSV and images
    csv_data = []
    try:
        csv_content = csv_file.read().decode('utf-8')
        csv_reader = csv.reader(io.StringIO(csv_content))
        for row in csv_reader:
            if len(row) >= 2:  # Ensure we have at least image URL and product name
                csv_data.append(row)
    except Exception as e:
        return jsonify({'error': f'CSV parsing error: {str(e)}'}), 400

    # Create a zip file for processed images
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for i, row in enumerate(csv_data):
            if i == 0 and 'image' in row[0].lower():  # Skip header row
                continue

            image_url = row[0]
            product_name = row[1]

            try:
                # In a real app, you'd download from URLs:
                # import requests
                # response = requests.get(image_url)
                # product_img = Image.open(io.BytesIO(response.content))

                # For demo purposes, we'll create a sample product image
                # This would be replaced with the actual product image in a real app

                # Create different shaped images for demonstration
                if i % 3 == 0:  # Horizontal
                    product_img = Image.new('RGBA', (600, 400), (200, 200, 200, 255))
                elif i % 3 == 1:  # Vertical
                    product_img = Image.new('RGBA', (400, 600), (200, 200, 200, 255))
                else:  # Square
                    product_img = Image.new('RGBA', (500, 500), (200, 200, 200, 255))

                # 1. Trim white background
                trimmed_img = trim_white_background(product_img)

                # 2. Determine aspect ratio
                aspect_ratio = determine_aspect_ratio(trimmed_img)

                # 3. Position on canvas based on aspect ratio
                canvas = position_on_canvas(trimmed_img, aspect_ratio, canvas_size)

                # 4. Resize logo based on percentage of canvas width
                logo_width = int(canvas_size[0] * logo_size / 100)
                logo_height = int(logo_width * logo.height / logo.width)
                resized_logo = logo.resize((logo_width, logo_height), Image.LANCZOS)

                # 5. Calculate position for logo
                if logo_position == 'top-left':
                    position = (logo_margin, logo_margin)
                elif logo_position == 'top-right':
                    position = (canvas_size[0] - logo_width - logo_margin, logo_margin)
                elif logo_position == 'bottom-left':
                    position = (logo_margin, canvas_size[1] - logo_height - logo_margin)
                else:  # bottom-right
                    position = (canvas_size[0] - logo_width - logo_margin, canvas_size[1] - logo_height - logo_margin)

                # 6. Paste logo
                canvas.paste(resized_logo, position, resized_logo if resized_logo.mode == 'RGBA' else None)

                # Save to zip
                img_byte_arr = io.BytesIO()
                canvas.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)

                filename = f"{secure_filename(product_name)}_{aspect_ratio}.png"
                zf.writestr(filename, img_byte_arr.getvalue())

            except Exception as e:
                # Log error but continue processing other images
                print(f"Error processing {image_url}: {str(e)}")

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='processed_images.zip'
    )

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
