import cv2
import torch
import numpy as np
from picamera2 import Picamera2

# Load the model
model = torch.hub.load('ultralytics/yolov5', 'custom', path='VehiPlus/driver_monitoring/yolov5n.pt')  # Adjust model path

# Define the function to process each frame
def process_frame(frame):
    # Convert frame from BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Make detections
    results = model(frame_rgb)

    # Filter out detections below the threshold
    confidence_scores = results.xyxy[0][:, 4]  # Extract confidence scores
    keep_indices = confidence_scores >= 0.4  # Get indices where confidence >= 0.4
    results.xyxy[0] = results.xyxy[0][keep_indices]  # Filter out low-confidence detections

    # Render results onto the frame
    frame_result = results.render()[0]
    return frame_result


# Initialize video capture from the first camera device
picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": (1640, 1232)}, lores={"size": (1640, 1232)}, display="lores")
try:
    # Configure and start the camera
    picam2.configure(config)
    picam2.start()
    print("Camera is ready.")
    while True:
        # Capture a frame
        frame = picam2.capture_array()
        if frame is None:
            print("Error: Failed to capture image")
            break
        # Process the frame
        frame_output = process_frame(frame)

        # Display the frame
        cv2.imshow('YOLOv5 Detection', frame_output)

        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
except Exception as e:
    print(f"Error: Could not open video device. {e}")
    
finally:
    picam2.stop()
    cv2.destroyAllWindows()  # Destroy all the windows
